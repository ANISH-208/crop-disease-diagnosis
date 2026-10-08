import csv
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = PROJECT_ROOT / "ml_v6/datasets/dataset_manifest.csv"

EXPECTED_CLASSES = 38
EXPECTED_SPLITS = {"train", "validation", "test"}


def main():

    print("=" * 70)
    print("Crop Doctor AI — Dataset Quality Validation")
    print("=" * 70)

    with MANIFEST.open(
        "r",
        encoding="utf-8"
    ) as f:

        rows = list(csv.DictReader(f))

    print(f"\nImages indexed: {len(rows):,}")

    # ------------------------------------------------------------
    # BASIC STRUCTURE
    # ------------------------------------------------------------

    classes = sorted(
        set(row["canonical_label"] for row in rows)
    )

    splits = sorted(
        set(row["split"] for row in rows)
    )

    print(f"Classes found : {len(classes)}")
    print(f"Splits found  : {splits}")

    assert len(classes) == EXPECTED_CLASSES
    assert set(splits) == EXPECTED_SPLITS

    print("✓ Dataset contains exactly 38 classes.")
    print("✓ Train/validation/test splits present.")

    # ------------------------------------------------------------
    # SPLIT COUNTS
    # ------------------------------------------------------------

    split_counts = Counter(
        row["split"] for row in rows
    )

    print("\n" + "=" * 70)
    print("SPLIT COUNTS")
    print("=" * 70)

    for split in ["train", "validation", "test"]:

        count = split_counts[split]

        print(
            f"{split:12} "
            f"{count:6,} "
            f"{count / len(rows) * 100:6.2f}%"
        )

    # ------------------------------------------------------------
    # CLASS DISTRIBUTION
    # ------------------------------------------------------------

    class_counts = defaultdict(Counter)

    for row in rows:

        class_counts[
            row["canonical_label"]
        ][row["split"]] += 1

    print("\n" + "=" * 70)
    print("CLASS DISTRIBUTION")
    print("=" * 70)

    minimums = {
        "train": float("inf"),
        "validation": float("inf"),
        "test": float("inf"),
    }

    for cls in classes:

        train = class_counts[cls]["train"]
        val = class_counts[cls]["validation"]
        test = class_counts[cls]["test"]

        minimums["train"] = min(
            minimums["train"], train
        )

        minimums["validation"] = min(
            minimums["validation"], val
        )

        minimums["test"] = min(
            minimums["test"], test
        )

        print(
            f"{cls:65} "
            f"{train:5} "
            f"{val:4} "
            f"{test:4}"
        )

    print("\nMinimum class counts:")

    for split, count in minimums.items():

        print(
            f"{split:12}: {int(count)}"
        )

    # ------------------------------------------------------------
    # MISSING CLASSES
    # ------------------------------------------------------------

    print("\n" + "=" * 70)
    print("MISSING CLASS CHECK")
    print("=" * 70)

    missing = []

    for cls in classes:

        for split in EXPECTED_SPLITS:

            if class_counts[cls][split] == 0:

                missing.append(
                    (cls, split)
                )

    if missing:

        for cls, split in missing:
            print(
                f"MISSING: {cls} -> {split}"
            )

        raise RuntimeError(
            "One or more classes are missing from a split."
        )

    print(
        "✓ Every class appears in train, validation and test."
    )

    # ------------------------------------------------------------
    # LEAF GROUP CHECK
    # ------------------------------------------------------------

    leaf_groups = defaultdict(set)

    for row in rows:

        leaf_id = row["leaf_id"]

        if not leaf_id:
            continue

        key = (
            row["canonical_label"],
            leaf_id
        )

        leaf_groups[key].add(
            row["split"]
        )

    leaking_leaf_groups = [
        key
        for key, splits_used
        in leaf_groups.items()
        if len(splits_used) > 1
    ]

    print("\n" + "=" * 70)
    print("LEAF GROUP CHECK")
    print("=" * 70)

    print(
        f"Leaf groups: {len(leaf_groups):,}"
    )

    print(
        f"Leaking groups: "
        f"{len(leaking_leaf_groups):,}"
    )

    assert not leaking_leaf_groups

    print(
        "✓ No leaf group crosses dataset splits."
    )

    # ------------------------------------------------------------
    # DUPLICATE CHECK
    # ------------------------------------------------------------

    hashes = defaultdict(set)

    for row in rows:

        hashes[
            row["sha256"]
        ].add(
            row["split"]
        )

    duplicate_leakage = [
        sha
        for sha, used_splits
        in hashes.items()
        if len(used_splits) > 1
    ]

    duplicate_groups = [
        sha
        for sha, used_splits
        in hashes.items()
        if len(used_splits) == 1
    ]

    print("\n" + "=" * 70)
    print("DUPLICATE CHECK")
    print("=" * 70)

    print(
        f"Unique SHA256 hashes: {len(hashes):,}"
    )

    print(
        f"Duplicate image groups: "
        f"{len(rows) - len(hashes):,} duplicate rows"
    )

    print(
        f"Cross-split duplicates: "
        f"{len(duplicate_leakage):,}"
    )

    assert not duplicate_leakage

    print(
        "✓ No exact duplicate crosses splits."
    )

    # ------------------------------------------------------------
    # IMAGE INTEGRITY
    # ------------------------------------------------------------

    print("\n" + "=" * 70)
    print("IMAGE INTEGRITY CHECK")
    print("=" * 70)

    bad_images = []
    modes = Counter()
    sizes = Counter()

    for i, row in enumerate(rows, 1):

        path = PROJECT_ROOT / row["image_path"]

        try:

            with Image.open(path) as img:

                img.verify()

            with Image.open(path) as img:

                modes[img.mode] += 1
                sizes[img.size] += 1

        except Exception as exc:

            bad_images.append(
                (
                    row["image_path"],
                    str(exc)
                )
            )

        if i % 5000 == 0:

            print(
                f"Checked {i:,}/{len(rows):,}"
            )

    print(
        f"\nUnreadable/corrupt images: "
        f"{len(bad_images):,}"
    )

    if bad_images:

        print("\nFirst corrupted images:")

        for path, error in bad_images[:20]:

            print(
                f"{path}\n  {error}"
            )

        raise RuntimeError(
            "Corrupt images detected."
        )

    print(
        "✓ All indexed images are readable."
    )

    # ------------------------------------------------------------
    # IMAGE MODES
    # ------------------------------------------------------------

    print("\n" + "=" * 70)
    print("IMAGE MODES")
    print("=" * 70)

    for mode, count in modes.most_common():

        print(
            f"{mode:8}: {count:6,}"
        )

    # ------------------------------------------------------------
    # IMAGE DIMENSIONS
    # ------------------------------------------------------------

    print("\n" + "=" * 70)
    print("IMAGE DIMENSIONS")
    print("=" * 70)

    for size, count in sizes.most_common(15):

        print(
            f"{str(size):15}: {count:6,}"
        )

    # ------------------------------------------------------------
    # FINAL
    # ------------------------------------------------------------

    print("\n" + "=" * 70)
    print("DATASET VALIDATION COMPLETE")
    print("=" * 70)

    print("✓ 38 classes")
    print("✓ Valid train/validation/test split")
    print("✓ No leaf leakage")
    print("✓ No exact duplicate leakage")
    print("✓ Image integrity checked")
    print("\nDataset is ready for model training.")


if __name__ == "__main__":
    main()
