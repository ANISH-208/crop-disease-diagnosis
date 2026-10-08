"""Runtime configuration for the Crop Doctor API."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _origins_from_env() -> list[str]:
    configured = os.getenv("CROP_DOCTOR_ALLOWED_ORIGINS")
    if not configured:
        return ["http://localhost:5173", "http://127.0.0.1:5173"]
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


ALLOWED_ORIGINS = _origins_from_env()
UPLOAD_DIR = Path(os.getenv("CROP_DOCTOR_UPLOAD_DIR", PROJECT_ROOT / "backend" / "uploads")).expanduser().resolve()
DATABASE_PATH = Path(os.getenv("CROP_DOCTOR_DATABASE_PATH", PROJECT_ROOT / "backend" / "alerts.db")).expanduser().resolve()
MODEL_PATH = Path(os.getenv("CROP_DOCTOR_MODEL_PATH", PROJECT_ROOT / "models" / "crop_doctor_v6_efficientnetv2s.keras")).expanduser().resolve()
CLASS_MAPPING_PATH = PROJECT_ROOT / "ml_v6" / "outputs" / "class_mapping.json"
MAX_UPLOAD_BYTES = int(os.getenv("CROP_DOCTOR_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
MAX_IMAGE_PIXELS = int(os.getenv("CROP_DOCTOR_MAX_IMAGE_PIXELS", str(40_000_000)))
CONFIDENCE_THRESHOLD = float(os.getenv("CROP_DOCTOR_CONFIDENCE_THRESHOLD", "80"))
