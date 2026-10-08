from pathlib import Path
import csv
import hashlib
import re

PROJECT_ROOT = Path(__file__).resolve().parents[2]

COLOR_DIR = (
    PROJECT_ROOT
    / "ml_v6"
    / "datasets"
    / "PlantVillage"
    / "raw"
    / "color"
)

MANIFEST_PATH = (
    PROJECT_ROOT
    / "ml_v6"
    / "datasets"
    / "dataset_manifest.csv"
)


def normalize_label(folder_name):
    """
    Convert PlantVillage folder names into Crop Doctor AI labels.
    """

    crop, disease = folder_name.split("___", 1)

    crop = crop.replace("_(including_sour)", "")
    crop = crop.replace("_(maize)", "")
    crop = crop.replace(",_bell", "")

    disease = disease.strip()

    disease = disease.replace(" ", "_")
    disease = disease.replace("__", "_")
    disease = disease.rstrip("_")

    # Normalize known PlantVillage naming variants
    replacements = {
        "healthy": "healthy",
        "Common_rust": "Common_rust",
        "Cercospora_leaf_spot_Gray_leaf_spot":
            "Cercospora_leaf_spot_Gray_leaf_spot",
        "Spider_mites_Two-spotted_spider_mite":
            "Spider_mites_Two-spotted_spider_mite",
        "Haunglongbing_(Citrus_greening)":
            "Haunglongbing_(Citrus_greening)",
    }

    disease = replacements.get(disease, disease)

    return crop, disease


def file_hash(path, chunk_size=1024 * 1024):
    """
    SHA256 hash used later for duplicate detection.
    """

    sha = hashlib.sha256()

    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            sha.update(chunk)

    return sha.hexdigest()


def main():

    if not COLOR_DIR.exists():
        raise FileNotFoundError(
            f"PlantVillage color directory not found:\n{COLOR_DIR}"
        )

    rows = []

    image_extensions = {".jpg", ".jpeg", ".png"}

    folders = sorted(
        p for p in COLOR_DIR.iterdir()
        if p.is_dir()
    )

    print("=" * 70)
    print("Crop Doctor AI — PlantVillage Manifest Builder")
    print("=" * 70)

    print(f"\nDataset directory:")
    print(COLOR_DIR)

    print(f"\nClass folders found: {len(folders)}")

    for folder in folders:

        crop, disease = normalize_label(folder.name)

        images = sorted(
            p for p in folder.rglob("*")
            if p.is_file()
            and p.suffix.lower() in image_extensions
        )

        print(
            f"{crop:12} | "
            f"{disease:55} | "
            f"{len(images):5} images"
        )

        for image in images:

            rows.append(
                {
                    "dataset": "PlantVillage",
                    "image_path": str(
                        image.relative_to(PROJECT_ROOT)
                    ),
                    "crop": crop,
                    "disease": disease,
                    "canonical_label": f"{crop}___{disease}",
                    "sha256": file_hash(image),
                    "split": "unassigned",
                }
            )

    with MANIFEST_PATH.open(
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "dataset",
                "image_path",
                "crop",
                "disease",
                "canonical_label",
                "sha256",
                "split",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)

    print("\n" + "=" * 70)
    print("MANIFEST CREATED")
    print("=" * 70)

    print(f"Images indexed : {len(rows):,}")
    print(f"Classes        : {len(folders)}")
    print(f"Manifest       : {MANIFEST_PATH}")

    print(
        "\nSHA256 hashes were generated for every image "
        "for future duplicate detection."
    )

    print(
        "\nSplit status: UNASSIGNED"
        "\nWe will NOT randomly split the data yet."
    )


if __name__ == "__main__":
    main()
