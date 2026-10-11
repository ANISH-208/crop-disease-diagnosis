"""Train and evaluate a separate crop/leaf suitability model.

The script requires a user-supplied, licensed image manifest. It never downloads
data or weights. See README.md for the manifest schema and evaluation contract.
"""

import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import tensorflow as tf

SEED = 42
SPLITS = {"train", "validation", "test"}
LABELS = {"not_plant": 0, "crop_or_leaf": 1}
REQUIRED_NEGATIVE_CATEGORIES = {"person", "animal", "vehicle", "document", "building", "natural", "green_confuser", "other"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path, data_root: Path) -> dict[str, list[tuple[Path, int]]]:
    required = {"image_path", "label", "group_id", "split", "category"}
    rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Manifest must contain columns: {', '.join(sorted(required))}.")
    group_split: dict[str, str] = {}
    hash_split: dict[str, str] = {}
    categories: dict[str, set[str]] = defaultdict(set)
    splits: dict[str, list[tuple[Path, int]]] = {name: [] for name in SPLITS}
    for row in rows:
        label, split = row["label"].strip(), row["split"].strip()
        group, category = row["group_id"].strip(), row["category"].strip().lower()
        if label not in LABELS or split not in SPLITS or not group or not category:
            raise ValueError("Each row needs a valid label, split, non-empty group_id, and category.")
        image_path = Path(row["image_path"])
        if not image_path.is_absolute():
            image_path = data_root / image_path
        if not image_path.is_file():
            raise ValueError(f"Missing image file referenced by manifest: {image_path}")
        previous_split = group_split.setdefault(group, split)
        if previous_split != split:
            raise ValueError(f"Group leakage: {group!r} occurs in multiple splits.")
        image_hash = sha256(image_path)
        previous_hash_split = hash_split.setdefault(image_hash, split)
        if previous_hash_split != split:
            raise ValueError("Exact duplicate image content occurs in multiple splits.")
        categories[label].add(category)
        splits[split].append((image_path, LABELS[label]))

    for split, items in splits.items():
        counts = Counter(label for _, label in items)
        if not items or any(counts[index] == 0 for index in LABELS.values()):
            raise ValueError(f"Split {split!r} must contain both classes.")
    if not REQUIRED_NEGATIVE_CATEGORIES.issubset(categories["not_plant"]):
        missing = sorted(REQUIRED_NEGATIVE_CATEGORIES - categories["not_plant"])
        raise ValueError(f"Negative examples are missing required categories: {', '.join(missing)}.")
    if len(categories["crop_or_leaf"]) < 3:
        raise ValueError("Positive examples must represent at least three crop or leaf categories.")
    return splits


def make_dataset(items: list[tuple[Path, int]], batch_size: int, shuffle: bool):
    paths = np.asarray([str(path) for path, _ in items])
    labels = np.asarray([label for _, label in items], dtype=np.int32)
    dataset = tf.data.Dataset.from_tensor_slices((paths, labels))
    if shuffle:
        dataset = dataset.shuffle(len(items), seed=SEED, reshuffle_each_iteration=True)

    def decode(path, label):
        image = tf.io.read_file(path)
        image = tf.image.decode_image(image, channels=3, expand_animations=False)
        image.set_shape([None, None, 3])
        image = tf.image.resize(image, (224, 224), method=tf.image.ResizeMethod.BILINEAR)
        return tf.cast(image, tf.float32), tf.one_hot(label, 2)

    return dataset.map(decode, num_parallel_calls=tf.data.AUTOTUNE).batch(batch_size).prefetch(tf.data.AUTOTUNE)


def choose_threshold(labels: np.ndarray, scores: np.ndarray, max_false_accept_rate: float) -> tuple[float, float]:
    negatives = scores[labels == 0]
    positives = scores[labels == 1]
    candidates = np.unique(np.concatenate(([0.0, 1.0], scores)))
    acceptable = [
        float(threshold)
        for threshold in candidates
        if float(np.mean(negatives >= threshold)) <= max_false_accept_rate
    ]
    if not acceptable:
        raise RuntimeError("Could not select a validation threshold under the requested false-acceptance limit.")
    threshold = min(acceptable)
    validation_far = float(np.mean(negatives >= threshold))
    return threshold, validation_far


def evaluate(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    predicted = scores >= threshold
    actual = labels == 1
    tn = int(np.sum(~actual & ~predicted))
    fp = int(np.sum(~actual & predicted))
    fn = int(np.sum(actual & ~predicted))
    tp = int(np.sum(actual & predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "test_precision": precision,
        "test_recall": recall,
        "test_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "test_false_accept_rate": fp / (fp + tn) if fp + tn else 0.0,
        "test_false_rejection_rate": fn / (fn + tp) if fn + tp else 0.0,
        "test_confusion_matrix": [[tn, fp], [fn, tp]],
        "test_count": int(len(labels)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset-source", required=True, help="Dataset citation or source URL")
    parser.add_argument("--dataset-license", required=True, help="Verified license identifier or statement")
    parser.add_argument("--max-validation-false-accept-rate", type=float, required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    if not 0 <= args.max_validation_false_accept_rate < 1:
        parser.error("--max-validation-false-accept-rate must be in [0, 1).")

    random.seed(SEED)
    np.random.seed(SEED)
    tf.random.set_seed(SEED)
    splits = load_manifest(args.manifest, args.data_root)
    model = tf.keras.applications.MobileNetV3Small(
        input_shape=(224, 224, 3), include_top=True, weights=None, classes=2,
        classifier_activation="softmax", include_preprocessing=True,
    )
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="categorical_crossentropy", metrics=["accuracy"])
    model.fit(
        make_dataset(splits["train"], args.batch_size, True),
        validation_data=make_dataset(splits["validation"], args.batch_size, False),
        epochs=args.epochs,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=4, restore_best_weights=True),
            tf.keras.callbacks.ReduceLROnPlateau(monitor="val_loss", patience=2, factor=0.3),
        ],
        verbose=2,
    )

    validation_probabilities = model.predict(make_dataset(splits["validation"], args.batch_size, False), verbose=0)
    validation_labels = np.asarray([label for _, label in splits["validation"]], dtype=np.int32)
    threshold, validation_far = choose_threshold(validation_labels, validation_probabilities[:, 1], args.max_validation_false_accept_rate)
    validation_metrics = evaluate(validation_labels, validation_probabilities[:, 1], threshold)
    test_probabilities = model.predict(make_dataset(splits["test"], args.batch_size, False), verbose=0)
    test_labels = np.asarray([label for _, label in splits["test"]], dtype=np.int32)
    metrics = evaluate(test_labels, test_probabilities[:, 1], threshold)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    tflite_bytes = converter.convert()
    model_version = f"crop-suitability-{hashlib.sha256(tflite_bytes).hexdigest()[:12]}"
    model_path = args.output_dir / "crop_suitability.tflite"
    model_path.write_bytes(tflite_bytes)
    metadata = {
        "schema_version": 1,
        "model_version": model_version,
        "class_order": ["not_plant", "crop_or_leaf"],
        "input_size": [224, 224],
        "input_range": "0_255",
        "acceptance_threshold": threshold,
        "training": {
            "architecture": "MobileNetV3Small",
            "weights": "trained from scratch",
            "seed": SEED,
            "epochs_requested": args.epochs,
            "dataset_source": args.dataset_source,
            "dataset_license": args.dataset_license,
            "split_counts": {name: len(items) for name, items in splits.items()},
        },
        "threshold_selection": {
            "max_validation_false_accept_rate_requested": args.max_validation_false_accept_rate,
            "validation_false_accept_rate": validation_far,
        },
        "evaluation": {
            "validation_false_accept_rate": validation_far,
            "validation_false_rejection_rate": validation_metrics["test_false_rejection_rate"],
            "validation_precision": validation_metrics["test_precision"],
            "validation_recall": validation_metrics["test_recall"],
            "validation_f1": validation_metrics["test_f1"],
            "validation_confusion_matrix": validation_metrics["test_confusion_matrix"],
            **metrics,
        },
    }
    model_path.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"model": str(model_path), "metadata": str(model_path.with_suffix('.json')), "evaluation": metrics}, indent=2))


if __name__ == "__main__":
    main()
