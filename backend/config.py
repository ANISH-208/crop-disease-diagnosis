"""Runtime configuration for the Crop Doctor API."""

import os
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
MAX_UPLOAD_BYTES = int(os.getenv("CROP_DOCTOR_MAX_UPLOAD_BYTES", str(4 * 1024 * 1024)))
MAX_IMAGE_PIXELS = int(os.getenv("CROP_DOCTOR_MAX_IMAGE_PIXELS", str(40_000_000)))
CONFIDENCE_THRESHOLD = float(os.getenv("CROP_DOCTOR_CONFIDENCE_THRESHOLD", "80"))
