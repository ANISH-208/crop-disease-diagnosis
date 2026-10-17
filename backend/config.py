"""Runtime configuration for the Crop Doctor API."""

import os
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _origins_from_env() -> list[str]:
    configured = os.getenv("CROP_DOCTOR_ALLOWED_ORIGINS")
    if not configured:
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://crop-disease-diagnosis-three.vercel.app",
        ]
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


ALLOWED_ORIGINS = _origins_from_env()
_runtime_root = Path("/tmp/crop-doctor") if os.getenv("VERCEL") else PROJECT_ROOT / "backend"
UPLOAD_DIR = Path(os.getenv("CROP_DOCTOR_UPLOAD_DIR", _runtime_root / "uploads")).expanduser().resolve()
DATABASE_PATH = Path(os.getenv("CROP_DOCTOR_DATABASE_PATH", _runtime_root / "alerts.db")).expanduser().resolve()
MODEL_PATH = Path(os.getenv("CROP_DOCTOR_MODEL_PATH", PROJECT_ROOT / "models" / "crop_doctor_v6_efficientnetv2s.keras")).expanduser().resolve()
LITE_MODEL_PATH = Path(os.getenv("CROP_DOCTOR_LITE_MODEL_PATH", PROJECT_ROOT / "models" / "crop_doctor_v6_efficientnetv2s.tflite")).expanduser().resolve()
CLASS_MAPPING_PATH = PROJECT_ROOT / "ml_v6" / "outputs" / "class_mapping.json"
SUITABILITY_MODEL_PATH = Path(os.getenv("CROP_DOCTOR_SUITABILITY_MODEL_PATH", PROJECT_ROOT / "models" / "crop_suitability.tflite")).expanduser().resolve()
MAX_UPLOAD_BYTES = int(os.getenv("CROP_DOCTOR_MAX_UPLOAD_BYTES", str(4 * 1024 * 1024)))
MAX_IMAGE_PIXELS = int(os.getenv("CROP_DOCTOR_MAX_IMAGE_PIXELS", str(40_000_000)))
CONFIDENCE_THRESHOLD = float(os.getenv("CROP_DOCTOR_CONFIDENCE_THRESHOLD", "80"))
DISEASE_POLICY_PATH = PROJECT_ROOT / "ml_v6" / "outputs" / "disease_acceptance_policy.json"


def _bundled_disease_policy() -> dict:
    """Load calibration values only when they match the deployed classifier."""
    try:
        policy = json.loads(DISEASE_POLICY_PATH.read_text(encoding="utf-8"))
        acceptance = policy.get("acceptance_policy", {})
        if policy.get("schema_version") != 1 or policy.get("model_version") != "v6-efficientnetv2s" or policy.get("class_count") != 38:
            return {}
        probability = float(acceptance["minimum_probability"])
        margin = float(acceptance["minimum_margin"])
        if not 0 <= probability <= 1 or not 0 <= margin <= 1:
            return {}
        return {"probability": str(probability), "margin": str(margin)}
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return {}


_bundled_policy = _bundled_disease_policy()
DISEASE_MIN_PROBABILITY = os.getenv("CROP_DOCTOR_DISEASE_MIN_PROBABILITY", _bundled_policy.get("probability"))
DISEASE_MIN_MARGIN = os.getenv("CROP_DOCTOR_DISEASE_MIN_MARGIN", _bundled_policy.get("margin"))
_allow_unvalidated_default = "true" if os.getenv("VERCEL") else ""
ALLOW_UNVALIDATED_DIAGNOSIS = os.getenv(
    "CROP_DOCTOR_ALLOW_UNVALIDATED_DIAGNOSIS", _allow_unvalidated_default
).strip().lower() in {"1", "true", "yes"}
EXPERT_API_KEY = os.getenv("CROP_DOCTOR_EXPERT_API_KEY", "").strip()
REALTIME_AVAILABLE = not bool(os.getenv("VERCEL"))
