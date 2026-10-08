"""Convert the trained Keras classifier to a compact TensorFlow Lite model."""

from pathlib import Path

import tensorflow as tf


ROOT = Path(__file__).resolve().parents[1]
KERAS_MODEL = ROOT / "models" / "crop_doctor_v6_efficientnetv2s.keras"
LITE_MODEL = ROOT / "models" / "crop_doctor_v6_efficientnetv2s.tflite"


def main() -> None:
    if not KERAS_MODEL.is_file():
        raise SystemExit(f"Missing source model: {KERAS_MODEL}")

    model = tf.keras.models.load_model(KERAS_MODEL, compile=False)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    LITE_MODEL.write_bytes(converter.convert())
    print(f"Created {LITE_MODEL} ({LITE_MODEL.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
