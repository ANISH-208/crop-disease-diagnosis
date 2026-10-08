import csv
import hashlib
import json
import random
import re
from collections import defaultdict, Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MANIFEST = PROJECT_ROOT / "ml_v6/datasets/dataset_manifest.csv"
LEAF_MAP = (
    PROJECT_ROOT
    / "ml_v6/datasets/PlantVillage/leaf_grouping/leaf-map.json"
)

SEED = 42


def normalize(s):
    s = str(s).lower()
    s = s.replace("_", " ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def canonicalize_class(class_name):
    """
    Convert PlantVillage class names to the canonical class format
    used by our manifest.

    Returns None for leaf-map metadata that is not a crop___disease
    class entry.
    """

    if not class_name:
        return None

    class_name = str(class_name).strip()

    if "___" not in class_name:
        return None

    crop, disease = class_name.split("___", 1)

    crop = crop.replace("_(including_sour)", "")
    crop = crop.replace("_(maize)", "")
    crop = crop.replace(",_bell", "")

    disease = disease.replace(" ", "_")
    disease = disease.rstrip("_")

    return normalize(f"{crop}___{disease}")


def image_identifier(path):
    """
    Extract the portion after ___ from the filename.

    UUID___RS_HL 6251.JPG
    becomes:
    rs hl 6251
    """

    stem = Path(path).stem

    if "___" in stem:
        stem = stem.split("___", 1)[1]

    return normalize(stem)


def main():

    print("=" * 70)
    print("Crop Doctor AI — Leaf-Aware Dataset Split V4")
    print("=" * 70)

    # ------------------------------------------------------------
    # LOAD MANIFEST
    # ------------------------------------------------------------

    with MANIFEST.open(
        "r",
        encoding="utf-8"
    ) as f:

        rows = list(csv.DictReader(f))

    print(
        f"\nManifest images : {len(rows):,}"
    )

    # ------------------------------------------------------------
    # BUILD CLASS + IDENTIFIER INDEX
    # ------------------------------------------------------------

    image_index = defaultdict(list)

    for row in rows:

        key = (
            normalize(row["canonical_label"]),
            image_identifier(row["image_path"])
        )

        image_index[key].append(
            row["image_path"]
        )

    print(
        f"Unique class+identifier keys: "
        f"{len(image_index):,}"
    )

    # ------------------------------------------------------------
    # LOAD LEAF MAP
    # ------------------------------------------------------------

    if LEAF_MAP.is_file():
        with LEAF_MAP.open("r", encoding="utf-8") as f:
            leaf_map = json.load(f)
    else:
        leaf_map = {}
        print("Leaf grouping metadata unavailable; assigning deterministic hash-based splits.")

    print(
        f"Leaf-map entries: {len(leaf_map):,}"
    )

    # ------------------------------------------------------------
    # MATCH LEAF MAP TO IMAGES
    # ------------------------------------------------------------

    matched = {}
    unmatched = []
    ambiguous = []
    invalid_entries = 0

    for leaf_key, mappings in leaf_map.items():

        identifier = normalize(leaf_key)

        for mapping in mappings:

            if ":::" not in mapping:
                invalid_entries += 1
                continue

            source_class, leaf_id = (
                mapping.rsplit(":::", 1)
            )

            class_key = canonicalize_class(
                source_class
            )

            if class_key is None:
                invalid_entries += 1
                continue

            lookup_key = (
                class_key,
                identifier
            )

            candidates = image_index.get(
                lookup_key,
                []
            )

            if len(candidates) == 1:

                image_path = candidates[0]

                matched[image_path] = (
                    class_key,
                    leaf_id
                )

            elif len(candidates) == 0:

                unmatched.append(
                    (
                        leaf_key,
                        source_class
                    )
                )

            else:

                # The same class + identifier can occasionally
                # correspond to multiple files. The leaf-map
                # does not provide enough information to safely
                # determine which UUID belongs to the leaf group.
                #
                # Do NOT guess. These images remain unresolved
                # and will use the deterministic fallback split.

                for candidate in candidates:
                    ambiguous.append(
                        (
                            leaf_key,
                            source_class,
                            candidate
                        )
                    )

    print(
        f"\nMatched leaf images : {len(matched):,}"
    )

    print(
        f"Unmatched mappings  : {len(unmatched):,}"
    )

    print(
        f"Ambiguous mappings  : {len(ambiguous):,}"
    )

    print(
        f"Invalid metadata    : {invalid_entries:,}"
    )

    # ------------------------------------------------------------
    # AMBIGUITY MUST BE ZERO
    # ------------------------------------------------------------

    if ambiguous:

        print(
            "\nNote: unresolved duplicate leaf identifiers:"
        )

        print(
            f"  Affected image mappings: {len(ambiguous):,}"
        )

        print(
            "  These images will use the fallback split."
        )

    # ------------------------------------------------------------
    # BUILD LEAF GROUPS
    # ------------------------------------------------------------

    groups = defaultdict(list)

    for row in rows:

        path = row["image_path"]

        if path not in matched:
            continue

        class_key, leaf_id = matched[path]

        group_key = (
            f"{class_key}:::{leaf_id}"
        )

        groups[group_key].append(row)

    print(
        f"\nLeaf groups resolved: "
        f"{len(groups):,}"
    )

    # ------------------------------------------------------------
    # GROUPS BY CLASS
    # ------------------------------------------------------------

    class_groups = defaultdict(list)

    for group_key, members in groups.items():

        cls = members[0]["canonical_label"]

        class_groups[cls].append(
            (
                group_key,
                members
            )
        )

    rng = random.Random(SEED)

    assignments = {}

    # ------------------------------------------------------------
    # STRATIFIED GROUP SPLIT
    # ------------------------------------------------------------

    for cls in sorted(class_groups):

        cls_groups = class_groups[cls]

        rng.shuffle(cls_groups)

        total = sum(
            len(members)
            for _, members in cls_groups
        )

        train_target = total * 0.80
        val_target = total * 0.10

        train_count = 0
        val_count = 0

        for group_key, members in cls_groups:

            size = len(members)

            if (
                train_count + size
                <= train_target
            ):

                split = "train"
                train_count += size

            elif (
                val_count + size
                <= val_target
            ):

                split = "validation"
                val_count += size

            else:

                split = "test"

            assignments[group_key] = split

    # ------------------------------------------------------------
    # ASSIGN ROWS
    # ------------------------------------------------------------

    for row in rows:

        path = row["image_path"]

        if path in matched:

            class_key, leaf_id = matched[path]

            group_key = (
                f"{class_key}:::{leaf_id}"
            )

            row["leaf_id"] = leaf_id
            row["split"] = assignments[group_key]

        else:

            row["leaf_id"] = ""

            # Deterministic fallback split.
            digest = hashlib.sha256(
                path.encode("utf-8")
            ).hexdigest()

            value = (
                int(digest[:8], 16)
                / 0xFFFFFFFF
            )

            if value < 0.80:
                row["split"] = "train"

            elif value < 0.90:
                row["split"] = "validation"

            else:
                row["split"] = "test"

    # ------------------------------------------------------------
    # EXACT DUPLICATES
    # ------------------------------------------------------------

    hash_groups = defaultdict(list)

    for row in rows:

        hash_groups[
            row["sha256"]
        ].append(row)

    duplicate_groups = {
        h: members
        for h, members in hash_groups.items()
        if len(members) > 1
    }

    print(
        f"\nExact duplicate groups: "
        f"{len(duplicate_groups):,}"
    )

    duplicate_moves = 0

    for sha, members in duplicate_groups.items():

        counts = Counter(
            row["split"]
            for row in members
        )

        target = counts.most_common(1)[0][0]

        for row in members:

            if row["split"] != target:

                row["split"] = target
                duplicate_moves += 1

    print(
        f"Duplicate rows reassigned: "
        f"{duplicate_moves:,}"
    )

    # ------------------------------------------------------------
    # WRITE MANIFEST
    # ------------------------------------------------------------

    fields = [
        "dataset",
        "image_path",
        "crop",
        "disease",
        "canonical_label",
        "sha256",
        "leaf_id",
        "split"
    ]

    with MANIFEST.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(rows)

    # ------------------------------------------------------------
    # SPLIT COUNTS
    # ------------------------------------------------------------

    split_counts = Counter(
        row["split"]
        for row in rows
    )

    print("\n" + "=" * 70)
    print("SPLIT CREATED")
    print("=" * 70)

    for split in [
        "train",
        "validation",
        "test"
    ]:

        count = split_counts[split]

        print(
            f"{split:12}: "
            f"{count:6,} "
            f"({count / len(rows) * 100:6.2f}%)"
        )

    # ------------------------------------------------------------
    # CLASS COUNTS
    # ------------------------------------------------------------

    print("\n" + "=" * 70)
    print("CLASS DISTRIBUTION")
    print("=" * 70)

    class_split_counts = defaultdict(Counter)

    for row in rows:

        class_split_counts[
            row["canonical_label"]
        ][row["split"]] += 1

    for cls in sorted(class_split_counts):

        counts = class_split_counts[cls]

        print(
            f"{cls:65} "
            f"train={counts['train']:5} "
            f"val={counts['validation']:4} "
            f"test={counts['test']:4}"
        )

    # ------------------------------------------------------------
    # LEAF LEAKAGE CHECK
    # ------------------------------------------------------------

    leaf_splits = defaultdict(set)

    for row in rows:

        if not row["leaf_id"]:
            continue

        key = (
            row["canonical_label"],
            row["leaf_id"]
        )

        leaf_splits[key].add(
            row["split"]
        )

    leaking = {
        key: splits
        for key, splits
        in leaf_splits.items()
        if len(splits) > 1
    }

    print("\n" + "=" * 70)
    print("LEAF LEAKAGE CHECK")
    print("=" * 70)

    print(
        f"Leaf groups checked : "
        f"{len(leaf_splits):,}"
    )

    print(
        f"Leaking leaf groups : "
        f"{len(leaking):,}"
    )

    if leaking:

        for key, splits in list(
            leaking.items()
        )[:20]:

            print(
                key,
                sorted(splits)
            )

        raise RuntimeError(
            "Leaf leakage detected."
        )

    print(
        "✓ No leaf group crosses "
        "train/validation/test."
    )

    # ------------------------------------------------------------
    # DUPLICATE LEAKAGE CHECK
    # ------------------------------------------------------------

    hash_splits = defaultdict(set)

    for row in rows:

        hash_splits[
            row["sha256"]
        ].add(
            row["split"]
        )

    cross_split_duplicates = {
        sha: splits
        for sha, splits
        in hash_splits.items()
        if len(splits) > 1
    }

    print("\n" + "=" * 70)
    print("DUPLICATE LEAKAGE CHECK")
    print("=" * 70)

    print(
        f"Cross-split duplicate hashes: "
        f"{len(cross_split_duplicates):,}"
    )

    if cross_split_duplicates:

        for sha, splits in list(
            cross_split_duplicates.items()
        )[:20]:

            print(
                sha,
                sorted(splits)
            )

        raise RuntimeError(
            "Exact duplicate leakage remains."
        )

    print(
        "✓ No exact duplicate crosses splits."
    )

    # ------------------------------------------------------------
    # FINAL SUMMARY
    # ------------------------------------------------------------

    print("\n" + "=" * 70)
    print("DATASET SPLIT COMPLETE")
    print("=" * 70)

    print(
        f"Total images : {len(rows):,}"
    )

    print(
        f"Classes      : "
        f"{len(class_split_counts)}"
    )

    print(
        f"Manifest     : {MANIFEST}"
    )

    print("\nReady for dataset validation.")


if __name__ == "__main__":
    main()
