"""Fail a deployment build if the Git LFS model file is missing or only a pointer."""

from pathlib import Path


MODEL_PATH = Path("models/crop_doctor_v6_efficientnetv2s.keras")
LFS_POINTER_HEADER = b"version https://git-lfs.github.com/spec/v1"


def main() -> None:
    if not MODEL_PATH.is_file():
        raise SystemExit(f"Required model file is missing: {MODEL_PATH}")
    with MODEL_PATH.open("rb") as model_file:
        header = model_file.read(len(LFS_POINTER_HEADER))
    if header == LFS_POINTER_HEADER:
        raise SystemExit(
            "The model checkout is a Git LFS pointer. Configure the deploy build to fetch Git LFS objects."
        )
    print(f"Model artifact is present: {MODEL_PATH}")


if __name__ == "__main__":
    main()
