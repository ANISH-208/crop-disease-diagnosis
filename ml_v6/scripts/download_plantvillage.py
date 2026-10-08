"""Download PlantVillage from Hugging Face into the local raw/color tree."""

import argparse
from pathlib import Path

from datasets import load_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = PROJECT_ROOT / "ml_v6" / "datasets" / "PlantVillage" / "raw" / "color"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default="mohanty/PlantVillage", help="Hugging Face dataset identifier")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output folder for class-organized images")
    args = parser.parse_args()

    print(f"Loading {args.dataset} …")
    dataset = load_dataset(args.dataset)
    if "train" not in dataset:
        raise RuntimeError("Expected a 'train' split with image and label fields.")
    label_feature = dataset["train"].features["label"]
    if not hasattr(label_feature, "names"):
        raise RuntimeError("Expected the dataset label column to provide class names.")

    written = 0
    for split_name, split_data in dataset.items():
        for index, sample in enumerate(split_data):
            image = sample.get("image")
            label = sample.get("label")
            if image is None or label is None:
                raise RuntimeError("Each dataset record must include image and label values.")
            class_name = label_feature.names[int(label)]
            target_dir = args.output / class_name
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / f"{split_name}_{index:07d}.jpg"
            image.convert("RGB").save(target_path, format="JPEG", quality=95)
            written += 1
            if written % 1000 == 0:
                print(f"Saved {written:,} images")

    print(f"Saved {written:,} images under {args.output}")
    print("Next: run build_manifest.py, create_leaf_split.py, and validate_dataset.py.")


if __name__ == "__main__":
    main()
