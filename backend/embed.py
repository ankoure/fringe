"""One-time script to compute and cache sentence embeddings for all shows."""

from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

_HERE = Path(__file__).parent
SHOWS_CSV = _HERE / "fringe_shows.csv"
EMBEDDINGS_NPY = _HERE / "embeddings.npy"
MODEL_NAME = "all-MiniLM-L6-v2"


def build_text(row: pd.Series) -> str:
    parts = [
        str(row.get("title", "") or ""),
        str(row.get("genre", "") or ""),
        str(row.get("description", "") or ""),
    ]
    return ". ".join(p for p in parts if p)


def main() -> None:
    print(f"Loading shows from {SHOWS_CSV}...")
    df = pd.read_csv(SHOWS_CSV)
    print(f"  {len(df)} shows loaded")

    texts = [build_text(row) for _, row in df.iterrows()]

    print(f"Loading model '{MODEL_NAME}'...")
    model = SentenceTransformer(MODEL_NAME)

    print("Computing embeddings (this takes ~30s)...")
    embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)

    np.save(EMBEDDINGS_NPY, embeddings)
    print(f"Saved {embeddings.shape} embeddings to {EMBEDDINGS_NPY}")


if __name__ == "__main__":
    main()
