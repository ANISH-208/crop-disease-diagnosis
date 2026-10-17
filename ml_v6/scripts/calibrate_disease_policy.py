"""Choose a selective disease-result policy on validation data and report test results."""

import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

from backend.model import CLASS_NAMES, MODEL_VERSION, predict_disease


def load_samples(manifest_path: Path, project_root: Path) -> dict[str, list[tuple[Path, int, str]]]:
    with manifest_path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    required = {"image_path", "canonical_label", "split"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Manifest must contain columns: {', '.join(sorted(required))}.")
    group_key = "leaf_id" if "leaf_id" in rows[0] else "group_id" if "group_id" in rows[0] else None
    if not group_key:
        raise ValueError("Manifest must include leaf_id or group_id for split-isolation checks.")
    groups: dict[str, set[str]] = {}
    samples = {"validation": [], "test": []}
    for row in rows:
        split = row["split"].strip()
        if split not in {"train", "validation", "test"}:
            continue
        label = row["canonical_label"].strip()
        if label not in CLASS_NAMES:
            raise ValueError(f"Unknown class label: {label!r}")
        source_group_id = row[group_key].strip()
        if not source_group_id:
            raise ValueError(f"Missing {group_key} for row with image {row['image_path']!r}.")
        # The splitter scopes leaf/source IDs by canonical class because
        # upstream leaf maps may reuse the same ID in different classes.
        group_id = f"{label}:::{source_group_id}"
        groups.setdefault(group_id, set()).add(split)
        if split == "train":
            continue
        image_path = Path(row["image_path"])
        if not image_path.is_absolute():
            image_path = project_root / image_path
        if not image_path.is_file():
            raise ValueError(f"Missing image file referenced by manifest: {image_path}")
        samples[split].append((image_path, CLASS_NAMES.index(label), group_id))
    leaked = [group for group, splits in groups.items() if len(splits) > 1]
    if leaked:
        raise ValueError(f"{len(leaked)} leaf/source group(s) occur across validation and test splits.")
    if any(not samples[name] for name in samples):
        raise ValueError("The manifest must contain both validation and test examples.")
    return samples


def measure(labels: np.ndarray, predictions: np.ndarray, probabilities: np.ndarray, margins: np.ndarray, min_probability: float, min_margin: float) -> dict:
    accepted = (probabilities >= min_probability) & (margins >= min_margin)
    accepted_count = int(accepted.sum())
    error_count = int(np.sum(predictions[accepted] != labels[accepted]))
    total = int(len(labels))
    return {
        "total": total,
        "accepted": accepted_count,
        "rejected": total - accepted_count,
        "coverage": accepted_count / total if total else 0.0,
        "selective_error_rate": error_count / accepted_count if accepted_count else 0.0,
        "accepted_accuracy": 1 - error_count / accepted_count if accepted_count else 0.0,
    }


def choose_policy_for_predictions(labels: np.ndarray, predictions: np.ndarray, probabilities: np.ndarray, margins: np.ndarray, max_error_rate: float) -> tuple[float, float, dict]:
    quantiles = np.linspace(0, 1, 61)
    probability_candidates = np.unique(np.concatenate(([0.0, 1.0], np.quantile(probabilities, quantiles))))
    margin_candidates = np.unique(np.concatenate(([0.0, 1.0], np.quantile(margins, quantiles))))
    best = None
    for min_probability in probability_candidates:
        for min_margin in margin_candidates:
            report = measure(labels, predictions, probabilities, margins, float(min_probability), float(min_margin))
            if report["accepted"] and report["selective_error_rate"] <= max_error_rate:
                rank = (report["coverage"], -float(min_probability), -float(min_margin))
                if best is None or rank > best[0]:
                    best = (rank, float(min_probability), float(min_margin), report)
    if best is None:
        raise RuntimeError("No non-empty validation selection met the requested error rate.")
    return best[1], best[2], best[3]


def score_full_samples(samples: list[tuple[Path, int, str]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    labels, predictions, probabilities, margins = [], [], [], []
    for image_path, label, _group in samples:
        result = predict_disease(image_path)
        scores = np.asarray(result.get("probabilities", []), dtype=np.float64)
        if scores.shape != (len(CLASS_NAMES),) or not np.isfinite(scores).all():
            raise ValueError(f"Invalid disease model scores for {image_path.name}.")
        top_indices = np.argsort(scores)[-2:]
        predictions.append(int(top_indices[-1]))
        labels.append(label)
        probabilities.append(float(scores[top_indices[-1]]))
        margins.append(float(scores[top_indices[-1]] - scores[top_indices[-2]]))
    return np.asarray(labels), np.asarray(predictions), np.asarray(probabilities), np.asarray(margins)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-selective-error-rate", type=float, required=True)
    args = parser.parse_args()
    if not math.isfinite(args.max_selective_error_rate) or not 0 <= args.max_selective_error_rate < 1:
        parser.error("--max-selective-error-rate must be in [0, 1).")

    samples = load_samples(args.manifest, Path(__file__).resolve().parents[2])
    validation = score_full_samples(samples["validation"])
    minimum_probability, minimum_margin, validation_metrics = choose_policy_for_predictions(*validation, args.max_selective_error_rate)
    test = score_full_samples(samples["test"])
    test_metrics = measure(*test, minimum_probability, minimum_margin)
    result = {
        "schema_version": 1,
        "model_version": MODEL_VERSION,
        "class_count": len(CLASS_NAMES),
        "acceptance_policy": {
            "minimum_probability": minimum_probability,
            "minimum_margin": minimum_margin,
            "max_validation_selective_error_rate_requested": args.max_selective_error_rate,
        },
        "validation": validation_metrics,
        "test": test_metrics,
        "environment_lines": {
            "CROP_DOCTOR_DISEASE_MIN_PROBABILITY": str(minimum_probability),
            "CROP_DOCTOR_DISEASE_MIN_MARGIN": str(minimum_margin),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
