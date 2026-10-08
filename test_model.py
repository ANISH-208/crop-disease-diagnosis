"""Run one diagnosis from the command line for a local image."""

import argparse
import json
from pathlib import Path

from backend.diagnosis import diagnose_image


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Crop Doctor AI on one JPG or PNG image.")
    parser.add_argument("image", type=Path, help="Path to a crop leaf image")
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"image does not exist: {args.image}")

    result = diagnose_image(args.image)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
