import json
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from PIL import Image


MODEL_PATH = Path("ml_v6/outputs/crop_doctor_v6_efficientnetv2s.keras")
MANIFEST_PATH = Path("ml_v6/datasets/dataset_manifest.csv")
CLASS_MAPPING_PATH = Path("ml_v6/outputs/class_mapping.json")

print("=" * 70)
print("CROP DOCTOR AI — V6 MODEL SANITY CHECK")
print("=" * 70)

# --------------------------------------------------
# 1. Load model
# --------------------------------------------------

print("\n[1/5] Loading model...")

model = tf.keras.models.load_model(MODEL_PATH)

print("✓ Model loaded")
print(f"  Input shape : {model.input_shape}")
print(f"  Output shape: {model.output_shape}")
print(f"  Parameters  : {model.count_params():,}")


# --------------------------------------------------
# 2. Load class mapping
# --------------------------------------------------

print("\n[2/5] Loading class mapping...")

with open(CLASS_MAPPING_PATH, "r") as f:
    class_mapping = json.load(f)

# Handle the actual class_mapping.json structure
if "classes" in class_mapping:
    index_to_class = {
        i: label
        for i, label in enumerate(class_mapping["classes"])
    }
else:
    raise ValueError(
        "Unexpected class_mapping.json format. "
        "Expected a 'classes' list."
    )

print(f"✓ Classes loaded: {len(index_to_class)}")

for idx in sorted(index_to_class)[:5]:
    print(f"  {idx}: {index_to_class[idx]}")

assert len(index_to_class) == 38, "Expected exactly 38 classes."


# --------------------------------------------------
# 3. Load manifest
# --------------------------------------------------

print("\n[3/5] Loading dataset manifest...")

df = pd.read_csv(MANIFEST_PATH)

test_df = df[df["split"] == "test"].copy()

print(f"✓ Test images: {len(test_df):,}")
print(f"✓ Test classes: {test_df['canonical_label'].nunique()}")


# --------------------------------------------------
# 4. Test representative images
# --------------------------------------------------

print("\n[4/5] Running representative inference...")

# One random test image from each class
samples = (
    test_df
    .groupby("canonical_label", group_keys=False)
    .sample(n=1, random_state=42)
)

correct = 0
total = 0

for _, row in samples.iterrows():

    image_path = Path(row["image_path"])
    true_label = row["canonical_label"]

    image = Image.open(image_path).convert("RGB")
    image = image.resize((224, 224))

    image_array = np.array(image, dtype=np.float32)
    image_array = np.expand_dims(image_array, axis=0)

    predictions = model.predict(image_array, verbose=0)[0]

    predicted_index = int(np.argmax(predictions))
    predicted_label = index_to_class[predicted_index]
    confidence = float(predictions[predicted_index]) * 100

    is_correct = predicted_label == true_label

    if is_correct:
        correct += 1

    total += 1

    status = "✓" if is_correct else "✗"

    print(
        f"{status} "
        f"{true_label:<55} "
        f"→ {predicted_label:<55} "
        f"{confidence:6.2f}%"
    )


# --------------------------------------------------
# 5. Summary
# --------------------------------------------------

print("\n[5/5] Sanity-check summary")

accuracy = (correct / total) * 100

print(f"\nRepresentative accuracy: {accuracy:.2f}%")
print(f"Correct: {correct}/{total}")

print("\n" + "=" * 70)

if accuracy >= 90:
    print("✓ V6 MODEL SANITY CHECK PASSED")
else:
    print("⚠ MODEL NEEDS INVESTIGATION")

print("=" * 70)
