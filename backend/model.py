import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from PIL import Image


# ============================================================
# CROP DOCTOR AI — V6 MODEL
# EfficientNetV2-S / PlantVillage 38-class classifier
# ============================================================

MODEL_VERSION = "v6-efficientnetv2s"

# Project root:
# crop-disease-diagnosis/
BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    BASE_DIR
    / "models"
    / "crop_doctor_v6_efficientnetv2s.keras"
)

CLASS_MAPPING_PATH = (
    BASE_DIR
    / "ml_v6"
    / "outputs"
    / "class_mapping.json"
)

# ------------------------------------------------------------
# Load class mapping
# ------------------------------------------------------------

with open(CLASS_MAPPING_PATH, "r") as f:
    class_mapping = json.load(f)

CLASS_NAMES = class_mapping["classes"]


if len(CLASS_NAMES) != 38:
    raise RuntimeError(
        f"Expected 38 classes, found {len(CLASS_NAMES)}"
    )


# ------------------------------------------------------------
# Load model
# ------------------------------------------------------------

print("=" * 60)
print("Loading Crop Doctor AI V6 model...")
print(f"Model: {MODEL_PATH}")
print(f"Version: {MODEL_VERSION}")
print("=" * 60)

model = tf.keras.models.load_model(MODEL_PATH)

print("✓ Crop Doctor AI V6 model loaded successfully!")
print(f"✓ Input shape : {model.input_shape}")
print(f"✓ Output shape: {model.output_shape}")
print(f"✓ Parameters  : {model.count_params():,}")
print("=" * 60)


# ------------------------------------------------------------
# Prediction
# ------------------------------------------------------------

def predict_disease(image_path: str) -> dict:

    image = Image.open(image_path).convert("RGB")

    image = image.resize((224, 224))

    image_array = np.asarray(
        image,
        dtype=np.float32
    )

    image_array = np.expand_dims(
        image_array,
        axis=0
    )

    predictions = model.predict(
        image_array,
        verbose=0
    )[0]

    predicted_index = int(
        np.argmax(predictions)
    )

    confidence = float(
        predictions[predicted_index]
    )

    predicted_class = CLASS_NAMES[
        predicted_index
    ]

    # Top-3 predictions
    top_indices = np.argsort(
        predictions
    )[-3:][::-1]

    top_predictions = []

    for index in top_indices:
        top_predictions.append({
            "class": CLASS_NAMES[int(index)],
            "confidence": round(
                float(predictions[index]) * 100,
                2
            )
        })

    return {
        "class": predicted_class,
        "confidence": confidence,
        "model_version": MODEL_VERSION,
        "top_predictions": top_predictions
    }
