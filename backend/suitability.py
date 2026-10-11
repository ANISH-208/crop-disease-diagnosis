"""Independent, fail-closed crop/leaf suitability validation.

The service intentionally ships without a validator artifact. A trained model
and its evaluation metadata must be installed together before classification is
allowed. The metadata contract is produced by ``train_suitability.py``.
"""

import json
import logging
import math
import threading
from pathlib import Path

import numpy as np
from PIL import Image

from backend.config import SUITABILITY_MODEL_PATH
from backend.image_utils import load_normalized_rgb

logger = logging.getLogger(__name__)
IMAGE_SIZE = (224, 224)
CLASS_ORDER = ["not_plant", "crop_or_leaf"]


class CropSuitabilityValidator:
    def __init__(self, model_path: Path = SUITABILITY_MODEL_PATH):
        self.model_path = Path(model_path)
        self.metadata_path = self.model_path.with_suffix(".json")
        self._lock = threading.Lock()
        self._interpreter = None
        self._input = None
        self._output = None
        self._metadata = None
        self._load_error = None

    def _read_metadata(self) -> dict | None:
        try:
            metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            evaluation = metadata.get("evaluation", {})
            training = metadata.get("training", {})
            threshold = metadata.get("acceptance_threshold")
            metric_keys = (
                "validation_false_accept_rate",
                "test_false_accept_rate",
                "test_false_rejection_rate",
                "test_precision",
                "test_recall",
                "test_f1",
            )
            metrics_valid = all(
                isinstance(evaluation.get(key), (int, float))
                and math.isfinite(evaluation[key])
                and 0 <= evaluation[key] <= 1
                for key in metric_keys
            )
            confusion = evaluation.get("test_confusion_matrix")
            confusion_valid = (
                isinstance(confusion, list)
                and len(confusion) == 2
                and all(isinstance(row, list) and len(row) == 2 for row in confusion)
                and all(isinstance(value, int) and value >= 0 for row in confusion for value in row)
                and sum(value for row in confusion for value in row) > 0
            )
            valid = (
                metadata.get("schema_version") == 1
                and metadata.get("class_order") == CLASS_ORDER
                and metadata.get("input_size") == [224, 224]
                and metadata.get("input_range") == "0_255"
                and isinstance(metadata.get("model_version"), str)
                and bool(metadata.get("model_version"))
                and isinstance(threshold, (int, float))
                and 0 <= threshold <= 1
                and metrics_valid
                and confusion_valid
                and isinstance(training.get("dataset_source"), str)
                and bool(training.get("dataset_source"))
                and isinstance(training.get("dataset_license"), str)
                and bool(training.get("dataset_license"))
            )
            return metadata if valid else None
        except (OSError, ValueError, TypeError, AttributeError):
            return None

    def status(self) -> dict:
        """Describe readiness without exposing local paths or loading the model."""
        if self._load_error:
            return {"status": "error", "ready": False, "message": "The crop photo check is unavailable."}
        metadata = self._metadata or self._read_metadata()
        if not self.model_path.is_file() or metadata is None:
            return {
                "status": "unavailable",
                "ready": False,
                "message": "A trained and evaluated crop photo validator is not installed.",
            }
        self._metadata = metadata
        return {"status": "available", "ready": True, "version": metadata["model_version"]}

    def _load(self) -> None:
        if self._interpreter is not None:
            return
        with self._lock:
            if self._interpreter is not None:
                return
            if not self.status()["ready"]:
                raise RuntimeError("The crop photo validator is not ready.")
            try:
                from ai_edge_litert.interpreter import Interpreter

                interpreter = Interpreter(model_path=str(self.model_path), num_threads=2)
                interpreter.allocate_tensors()
                inputs = interpreter.get_input_details()
                outputs = interpreter.get_output_details()
                if (
                    len(inputs) != 1
                    or tuple(inputs[0]["shape"]) != (1, 224, 224, 3)
                    or inputs[0]["dtype"] != np.float32
                    or len(outputs) != 1
                    or tuple(outputs[0]["shape"]) != (1, 2)
                    or outputs[0]["dtype"] != np.float32
                ):
                    raise RuntimeError("Validator input/output signature does not match its metadata contract.")
                self._interpreter, self._input, self._output = interpreter, inputs[0], outputs[0]
            except Exception as exc:
                self._load_error = "validator runtime or artifact error"
                logger.exception("Crop suitability validator failed to load")
                raise RuntimeError(self._load_error) from exc

    def validate_image(self, image_path: str | Path) -> dict:
        readiness = self.status()
        if not readiness["ready"]:
            return {"status": "unavailable", "message": readiness["message"]}
        try:
            self._load()
            image = load_normalized_rgb(image_path).resize(IMAGE_SIZE, Image.Resampling.BILINEAR)
            tensor = np.expand_dims(np.asarray(image, dtype=np.float32), axis=0)
            with self._lock:
                self._interpreter.set_tensor(self._input["index"], tensor)
                self._interpreter.invoke()
                scores = np.asarray(self._interpreter.get_tensor(self._output["index"]), dtype=np.float32)[0]
            if scores.shape != (2,) or not np.isfinite(scores).all() or np.any(scores < 0) or np.any(scores > 1) or not np.isclose(float(scores.sum()), 1, atol=0.05):
                raise RuntimeError("Validator returned invalid class probabilities.")
            leaf_score = float(scores[1])
            threshold = float(self._metadata["acceptance_threshold"])
            return {
                "status": "suitable" if leaf_score >= threshold else "not_plant",
                "score": round(leaf_score, 6),
                "threshold": threshold,
                "model_version": self._metadata["model_version"],
            }
        except Exception:
            logger.exception("Crop suitability validation failed")
            return {"status": "unavailable", "message": "The crop photo check could not be completed."}


validator = CropSuitabilityValidator()
