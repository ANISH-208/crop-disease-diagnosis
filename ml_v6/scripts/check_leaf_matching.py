import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

LEAF_MAP = ROOT / "ml_v6/datasets/PlantVillage/leaf_grouping/leaf-map.json"
COLOR_DIR = ROOT / "ml_v6/datasets/PlantVillage/raw/color"

with LEAF_MAP.open("r", encoding="utf-8") as f:
    leaf_map = json.load(f)

# Build searchable filename index
files = [
    p for p in COLOR_DIR.rglob("*")
    if p.is_file()
]

print("=" * 70)
print("Crop Doctor AI — Leaf Map Filename Matching Diagnostic")
print("=" * 70)

print(f"\nRaw color images : {len(files):,}")
print(f"Leaf-map entries : {len(leaf_map):,}")

# Normalize strings for matching.
def normalize(s):
    s = s.lower()
    s = s.replace("_", " ")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Search using the distinctive suffix contained in the leaf-map key.
matched = 0
unmatched = []

for i, key in enumerate(leaf_map):

    key_norm = normalize(key)

    candidates = []

    for path in files:
        stem_norm = normalize(path.stem)

        if key_norm in stem_norm:
            candidates.append(path)

    if candidates:
        matched += 1

        if i < 20:
            print(f"\nKEY: {key}")
            print(f"MATCHES: {len(candidates)}")

            for p in candidates[:5]:
                print(" ", p.relative_to(ROOT))

    else:
        unmatched.append(key)

print("\n" + "=" * 70)
print("RESULT")
print("=" * 70)

print(f"Matched entries   : {matched:,}")
print(f"Unmatched entries : {len(unmatched):,}")

print("\nFirst unmatched keys:")

for key in unmatched[:30]:
    print(" ", key)
