from __future__ import annotations

from pathlib import Path


DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    model_root = project_root / ".models"
    model_path = model_root / DEFAULT_MODEL_NAME

    if model_path.exists():
        print(f"Model already present at {model_path}")
        return

    model_root.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {DEFAULT_MODEL_NAME} to {model_path}")

    from sentence_transformers import SentenceTransformer

    SentenceTransformer(DEFAULT_MODEL_NAME).save(str(model_path))
    print("Model download complete")


if __name__ == "__main__":
    main()
