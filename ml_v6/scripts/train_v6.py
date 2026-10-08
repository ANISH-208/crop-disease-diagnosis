import os
import json
import math
import random
from pathlib import Path

import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.metrics import classification_report, confusion_matrix, f1_score

# ============================================================
# Crop Doctor AI — V6 EfficientNetV2-S Training
# ============================================================

SEED = 42

random.seed(SEED)
np.random.seed(SEED)
tf.random.set_seed(SEED)

ROOT = Path(__file__).resolve().parents[2]
ML_ROOT = ROOT / "ml_v6"

MANIFEST_PATH = ML_ROOT / "datasets" / "dataset_manifest.csv"
OUTPUT_DIR = ML_ROOT / "outputs"
CHECKPOINT_DIR = ML_ROOT / "checkpoints"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

IMG_SIZE = (224, 224)
BATCH_SIZE = 32
NUM_CLASSES = 38

INITIAL_EPOCHS = 12
FINE_TUNE_EPOCHS = 25

AUTOTUNE = tf.data.AUTOTUNE

print("=" * 70)
print("Crop Doctor AI — V6 EfficientNetV2-S")
print("=" * 70)

print(f"TensorFlow version : {tf.__version__}")
print(f"Manifest           : {MANIFEST_PATH}")
print(f"Image size         : {IMG_SIZE}")
print(f"Batch size         : {BATCH_SIZE}")
print()

# ------------------------------------------------------------
# Load manifest
# ------------------------------------------------------------

df = pd.read_csv(MANIFEST_PATH)

required_columns = {
    "image_path",
    "canonical_label",
    "split",
}

missing = required_columns - set(df.columns)

if missing:
    raise RuntimeError(
        f"Manifest is missing required columns: {sorted(missing)}"
    )

classes = sorted(df["canonical_label"].unique())

if len(classes) != NUM_CLASSES:
    raise RuntimeError(
        f"Expected {NUM_CLASSES} classes, found {len(classes)}"
    )

class_to_index = {
    class_name: index
    for index, class_name in enumerate(classes)
}

df["class_index"] = df["canonical_label"].map(class_to_index)

print(f"Images : {len(df):,}")
print(f"Classes: {len(classes)}")

print("\nClasses:")
for i, name in enumerate(classes):
    print(f"{i:2d}  {name}")

# Save exact class mapping used by model
class_mapping_path = OUTPUT_DIR / "class_mapping.json"

with open(class_mapping_path, "w") as f:
    json.dump(
        {
            "classes": classes,
            "class_to_index": class_to_index,
        },
        f,
        indent=2,
    )

print(f"\nClass mapping saved to:")
print(class_mapping_path)

# ------------------------------------------------------------
# Split datasets
# ------------------------------------------------------------

train_df = df[df["split"] == "train"].copy()
val_df = df[df["split"] == "validation"].copy()
test_df = df[df["split"] == "test"].copy()

print("\n" + "=" * 70)
print("DATASET SPLITS")
print("=" * 70)

print(f"Train      : {len(train_df):,}")
print(f"Validation : {len(val_df):,}")
print(f"Test       : {len(test_df):,}")

# ------------------------------------------------------------
# Verify paths
# ------------------------------------------------------------

def verify_paths(dataframe, name):
    missing = []

    for path in dataframe["image_path"]:
        path = Path(path)

        if not path.is_absolute():
            path = ROOT / path

        if not path.exists():
            missing.append(str(path))

            if len(missing) >= 10:
                break

    if missing:
        print(f"\nERROR: Missing {name} image paths.")
        for path in missing:
            print(path)
        raise RuntimeError(f"{name} dataset contains missing image paths.")

    print(f"✓ {name} paths verified")


verify_paths(train_df, "train")
verify_paths(val_df, "validation")
verify_paths(test_df, "test")

# ------------------------------------------------------------
# Resolve paths
# ------------------------------------------------------------

def resolve_path(path):
    path = Path(path)

    if path.is_absolute():
        return str(path)

    return str(ROOT / path)


train_paths = train_df["image_path"].map(resolve_path).values
train_labels = train_df["class_index"].values.astype(np.int32)

val_paths = val_df["image_path"].map(resolve_path).values
val_labels = val_df["class_index"].values.astype(np.int32)

test_paths = test_df["image_path"].map(resolve_path).values
test_labels = test_df["class_index"].values.astype(np.int32)

# ------------------------------------------------------------
# Image loading
# ------------------------------------------------------------

def load_image(path, label):
    image = tf.io.read_file(path)
    image = tf.image.decode_image(
        image,
        channels=3,
        expand_animations=False,
    )

    image.set_shape([None, None, 3])

    image = tf.image.resize(
        image,
        IMG_SIZE,
        method=tf.image.ResizeMethod.BILINEAR,
    )

    image = tf.cast(image, tf.float32)

    return image, label


# ------------------------------------------------------------
# Augmentation
# ------------------------------------------------------------

augmentation = tf.keras.Sequential(
    [
        tf.keras.layers.RandomFlip(
            "horizontal"
        ),

        tf.keras.layers.RandomRotation(
            0.08
        ),

        tf.keras.layers.RandomZoom(
            height_factor=(-0.12, 0.12),
            width_factor=(-0.12, 0.12),
        ),

        tf.keras.layers.RandomTranslation(
            height_factor=0.05,
            width_factor=0.05,
        ),

        tf.keras.layers.RandomContrast(
            0.10
        ),
    ],
    name="crop_augmentation",
)


def augment(image, label):
    image = augmentation(image, training=True)
    return image, label


# ------------------------------------------------------------
# tf.data pipelines
# ------------------------------------------------------------

def make_dataset(paths, labels, training=False):
    dataset = tf.data.Dataset.from_tensor_slices(
        (paths, labels)
    )

    if training:
        dataset = dataset.shuffle(
            buffer_size=len(paths),
            seed=SEED,
            reshuffle_each_iteration=True,
        )

    dataset = dataset.map(
        load_image,
        num_parallel_calls=AUTOTUNE,
    )

    if training:
        dataset = dataset.map(
            augment,
            num_parallel_calls=AUTOTUNE,
        )

    dataset = dataset.batch(
        BATCH_SIZE,
        drop_remainder=False,
    )

    dataset = dataset.prefetch(AUTOTUNE)

    return dataset


train_ds = make_dataset(
    train_paths,
    train_labels,
    training=True,
)

val_ds = make_dataset(
    val_paths,
    val_labels,
    training=False,
)

test_ds = make_dataset(
    test_paths,
    test_labels,
    training=False,
)

print("\n✓ tf.data pipelines created")

# ------------------------------------------------------------
# Class weights
# ------------------------------------------------------------

class_counts = (
    train_df["class_index"]
    .value_counts()
    .sort_index()
)

total = len(train_df)

class_weights = {}

for class_index, count in class_counts.items():
    class_weights[int(class_index)] = (
        total / (NUM_CLASSES * count)
    )

print("\nClass weighting enabled.")
print(
    f"Weight range: "
    f"{min(class_weights.values()):.3f} - "
    f"{max(class_weights.values()):.3f}"
)

# ------------------------------------------------------------
# Model
# ------------------------------------------------------------

print("\n" + "=" * 70)
print("BUILDING EFFICIENTNETV2-S")
print("=" * 70)

base_model = tf.keras.applications.EfficientNetV2S(
    include_top=False,
    weights="imagenet",
    input_shape=(224, 224, 3),
)

base_model.trainable = False

inputs = tf.keras.Input(
    shape=(224, 224, 3),
    name="crop_image",
)

x = base_model(
    inputs,
    training=False,
)

x = tf.keras.layers.GlobalAveragePooling2D()(x)

x = tf.keras.layers.BatchNormalization()(x)

x = tf.keras.layers.Dropout(
    0.35
)(x)

x = tf.keras.layers.Dense(
    256,
    activation="relu",
)(x)

x = tf.keras.layers.Dropout(
    0.25
)(x)

outputs = tf.keras.layers.Dense(
    NUM_CLASSES,
    activation="softmax",
    name="disease_prediction",
)(x)

model = tf.keras.Model(
    inputs,
    outputs,
    name="crop_doctor_efficientnetv2s",
)

model.summary()

# ------------------------------------------------------------
# Compile
# ------------------------------------------------------------

model.compile(
    optimizer=tf.keras.optimizers.Adam(
        learning_rate=1e-3
    ),
    loss=tf.keras.losses.SparseCategoricalCrossentropy(),
    metrics=[
        tf.keras.metrics.SparseCategoricalAccuracy(
            name="accuracy"
        ),
        tf.keras.metrics.SparseTopKCategoricalAccuracy(
            k=5,
            name="top5_accuracy",
        ),
    ],
)

# ------------------------------------------------------------
# Callbacks
# ------------------------------------------------------------

best_model_path = (
    CHECKPOINT_DIR /
    "efficientnetv2s_best.keras"
)

callbacks = [
    tf.keras.callbacks.ModelCheckpoint(
        filepath=str(best_model_path),
        monitor="val_accuracy",
        save_best_only=True,
        mode="max",
        verbose=1,
    ),

    tf.keras.callbacks.EarlyStopping(
        monitor="val_accuracy",
        patience=5,
        mode="max",
        restore_best_weights=True,
        verbose=1,
    ),

    tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss",
        factor=0.3,
        patience=2,
        min_lr=1e-7,
        verbose=1,
    ),

    tf.keras.callbacks.CSVLogger(
        str(OUTPUT_DIR / "training_history.csv")
    ),
]

# ------------------------------------------------------------
# Phase 1 — classifier training
# ------------------------------------------------------------

print("\n" + "=" * 70)
print("PHASE 1 — TRANSFER LEARNING")
print("=" * 70)

history1 = model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=INITIAL_EPOCHS,
    class_weight=class_weights,
    callbacks=callbacks,
)

# ------------------------------------------------------------
# Phase 2 — fine tuning
# ------------------------------------------------------------

print("\n" + "=" * 70)
print("PHASE 2 — FINE TUNING")
print("=" * 70)

base_model.trainable = True

# Keep the earliest layers frozen.
fine_tune_from = int(len(base_model.layers) * 0.70)

for layer in base_model.layers[:fine_tune_from]:
    layer.trainable = False

print(
    f"Fine-tuning last "
    f"{len(base_model.layers) - fine_tune_from} "
    f"EfficientNetV2-S layers."
)

model.compile(
    optimizer=tf.keras.optimizers.Adam(
        learning_rate=1e-5
    ),
    loss=tf.keras.losses.SparseCategoricalCrossentropy(),
    metrics=[
        tf.keras.metrics.SparseCategoricalAccuracy(
            name="accuracy"
        ),
        tf.keras.metrics.SparseTopKCategoricalAccuracy(
            k=5,
            name="top5_accuracy",
        ),
    ],
)

history2 = model.fit(
    train_ds,
    validation_data=val_ds,
    epochs=FINE_TUNE_EPOCHS,
    class_weight=class_weights,
    callbacks=callbacks,
)

# ------------------------------------------------------------
# Load best checkpoint
# ------------------------------------------------------------

print("\nLoading best checkpoint...")

best_model = tf.keras.models.load_model(
    best_model_path
)

print("✓ Best model loaded")

# ------------------------------------------------------------
# Test evaluation
# ------------------------------------------------------------

print("\n" + "=" * 70)
print("FINAL TEST EVALUATION")
print("=" * 70)

test_results = best_model.evaluate(
    test_ds,
    verbose=1,
    return_dict=True,
)

for metric, value in test_results.items():
    print(f"{metric:20s}: {value:.4f}")

# ------------------------------------------------------------
# Predictions
# ------------------------------------------------------------

print("\nGenerating test predictions...")

probabilities = best_model.predict(
    test_ds,
    verbose=1,
)

predictions = np.argmax(
    probabilities,
    axis=1,
)

true_labels = test_labels

# ------------------------------------------------------------
# Macro F1
# ------------------------------------------------------------

macro_f1 = f1_score(
    true_labels,
    predictions,
    average="macro",
)

weighted_f1 = f1_score(
    true_labels,
    predictions,
    average="weighted",
)

print("\n" + "=" * 70)
print("CLASSIFICATION METRICS")
print("=" * 70)

print(f"Macro F1    : {macro_f1:.4f}")
print(f"Weighted F1 : {weighted_f1:.4f}")

# ------------------------------------------------------------
# Classification report
# ------------------------------------------------------------

report = classification_report(
    true_labels,
    predictions,
    target_names=classes,
    digits=4,
)

print("\n" + report)

with open(
    OUTPUT_DIR / "classification_report.txt",
    "w",
) as f:
    f.write(report)

# ------------------------------------------------------------
# Confusion matrix
# ------------------------------------------------------------

cm = confusion_matrix(
    true_labels,
    predictions,
)

np.save(
    OUTPUT_DIR / "confusion_matrix.npy",
    cm,
)

# ------------------------------------------------------------
# Save final model
# ------------------------------------------------------------

final_model_path = (
    OUTPUT_DIR /
    "crop_doctor_v6_efficientnetv2s.keras"
)

best_model.save(
    final_model_path
)

print("\n" + "=" * 70)
print("V6 TRAINING COMPLETE")
print("=" * 70)

print(f"Best checkpoint : {best_model_path}")
print(f"Class mapping   : {class_mapping_path}")
print(
    f"Classification report: "
    f"{OUTPUT_DIR / 'classification_report.txt'}"
)
print(
    f"Confusion matrix: "
    f"{OUTPUT_DIR / 'confusion_matrix.npy'}"
)

print("\nFinal metrics:")

for metric, value in test_results.items():
    print(f"{metric:20s}: {value:.4f}")

print(f"{'macro_f1':20s}: {macro_f1:.4f}")
print(f"{'weighted_f1':20s}: {weighted_f1:.4f}")

