import json
from pathlib import Path
from collections import defaultdict, Counter

PROJECT_ROOT = Path(__file__).resolve().parents[2]

LEAF_MAP = (
    PROJECT_ROOT
    / "ml_v6"
    / "datasets"
    / "PlantVillage"
    / "leaf_grouping"
    / "leaf-map.json"
)

with LEAF_MAP.open("r", encoding="utf-8") as f:
    data = json.load(f)

print("=" * 70)
print("Crop Doctor AI — PlantVillage Leaf Group Analysis")
print("=" * 70)

print(f"\nLeaf-map entries : {len(data):,}")

# Each key is an image identifier.
# Values look like:
# ["Peach___healthy:::54.0"]

leaf_groups = defaultdict(list)
classes = Counter()

for image_id, mappings in data.items():

    for mapping in mappings:

        if ":::" not in mapping:
            continue

        class_name, leaf_id = mapping.rsplit(":::", 1)

        leaf_id = leaf_id.strip()

        leaf_groups[(class_name, leaf_id)].append(image_id)
        classes[class_name] += 1


print(f"Unique leaf groups : {len(leaf_groups):,}")
print(f"Classes represented: {len(classes):,}")

print("\nImages represented by class:")
print("-" * 70)

for cls, count in sorted(classes.items()):
    print(f"{cls:60} {count:6,}")


sizes = [len(v) for v in leaf_groups.values()]

print("\n" + "=" * 70)
print("LEAF GROUP SIZE STATISTICS")
print("=" * 70)

print(f"Smallest group : {min(sizes)} image(s)")
print(f"Largest group  : {max(sizes)} image(s)")
print(f"Average group  : {sum(sizes) / len(sizes):.2f} images")

distribution = Counter(sizes)

print("\nGroup-size distribution:")

for size, count in sorted(distribution.items()):
    print(f"{size:3} image(s) : {count:,} groups")


print("\nLargest leaf groups:")
print("-" * 70)

largest = sorted(
    leaf_groups.items(),
    key=lambda x: len(x[1]),
    reverse=True
)[:20]

for (cls, leaf_id), images in largest:
    print(
        f"{cls:55} "
        f"leaf={leaf_id:>8} "
        f"images={len(images):4}"
    )

print("\nDone.")
