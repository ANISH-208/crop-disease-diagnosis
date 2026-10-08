"""Lazy, validated access to the trained EfficientNetV2-S model."""

import json
import logging
import threading
from pathlib import Path

import numpy as np
from PIL import Image

from backend.config import CLASS_MAPPING_PATH, MODEL_PATH

logger = logging.getLogger(__name__)

MODEL_VERSION = "v6-efficientnetv2s"
IMAGE_SIZE = (224, 224)
EXPECTED_CLASS_COUNT = 38

with CLASS_MAPPING_PATH.open("r", encoding="utf-8") as mapping_file:
    _class_mapping = json.load(mapping_file)

CLASS_NAMES = _class_mapping.get("classes", [])
if len(CLASS_NAMES) != EXPECTED_CLASS_COUNT or len(set(CLASS_NAMES)) != EXPECTED_CLASS_COUNT:
    raise RuntimeError("The V6 class mapping must contain 38 unique classes.")
if _class_mapping.get("class_to_index") != {name: index for index, name in enumerate(CLASS_NAMES)}:
    raise RuntimeError("The V6 class-to-index mapping does not match the model output order.")

_model = None
_model_lock = threading.Lock()
_prediction_lock = threading.Lock()
_load_error: str | None = None


def model_status() -> dict:
    """Return model readiness without triggering a heavyweight load."""
    if _model is not None:
        return {"status": "loaded", "ready": True, "version": MODEL_VERSION}
    if not MODEL_PATH.is_file():
        return {"status": "missing", "ready": False, "version": MODEL_VERSION}
    if _load_error:
        return {"status": "error", "ready": False, "version": MODEL_VERSION}
    return {"status": "available", "ready": True, "version": MODEL_VERSION}


def _load_model():
    global _model, _load_error
    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model
        try:
            if not MODEL_PATH.is_file():
                raise FileNotFoundError(f"Trained model file is missing: {MODEL_PATH.name}")
            with MODEL_PATH.open("rb") as model_file:
                if model_file.read(80).startswith(b"version https://git-lfs.github.com/spec/v1"):
                    raise RuntimeError("The model path contains a Git LFS pointer instead of model data.")

            import tensorflow as tf

            logger.info("Loading model version=%s path=%s", MODEL_VERSION, MODEL_PATH.name)
            loaded = tf.keras.models.load_model(MODEL_PATH, compile=False)
            output_shape = loaded.output_shape
            if isinstance(output_shape, list) or output_shape[-1] != EXPECTED_CLASS_COUNT:
                raise RuntimeError(f"Expected model output with {EXPECTED_CLASS_COUNT} classes; got {output_shape}.")
            input_shape = loaded.input_shape
            if isinstance(input_shape, list) or tuple(input_shape[1:]) != (224, 224, 3):
                raise RuntimeError(f"Expected model input [batch, 224, 224, 3]; got {input_shape}.")
            _model = loaded
            _load_error = None
            logger.info("Model loaded version=%s parameters=%s", MODEL_VERSION, loaded.count_params())
            return _model
        except Exception as exc:
            _load_error = str(exc)
            logger.exception("Model load failed version=%s", MODEL_VERSION)
            raise RuntimeError("The crop diagnosis model is unavailable.") from exc


def predict_disease(image_path: str | Path) -> dict:
    model = _load_model()
    with Image.open(image_path) as source:
        image = source.convert("RGB").resize(IMAGE_SIZE)

    image_array = np.expand_dims(np.asarray(image, dtype=np.float32), axis=0)
    with _prediction_lock:
        predictions = np.asarray(model.predict(image_array, verbose=0))[0]

    if predictions.shape != (EXPECTED_CLASS_COUNT,) or not np.isfinite(predictions).all():
        raise RuntimeError("The model returned an invalid prediction vector.")

    predicted_index = int(np.argmax(predictions))
    top_indices = np.argsort(predictions)[-3:][::-1]
    return {
        "class": CLASS_NAMES[predicted_index],
        "confidence": float(predictions[predicted_index]),
        "model_version": MODEL_VERSION,
        "top_predictions": [
            {
                "class": CLASS_NAMES[int(index)],
                "confidence": round(float(predictions[index]) * 100, 2),
            }
            for index in top_indices
        ],
    }
