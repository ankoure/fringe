"""Fringe Swipe API — FastAPI backend."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sklearn.metrics.pairwise import cosine_similarity

SHOWS_CSV = Path(__file__).parent / "fringe_shows.csv"
EMBEDDINGS_NPY = Path(__file__).parent / "embeddings.npy"

app = FastAPI(title="Fringe Swipe API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Startup: load data once
# ---------------------------------------------------------------------------

df: pd.DataFrame = pd.DataFrame()
embeddings: Optional[np.ndarray] = None
show_id_to_idx: dict[str, int] = {}


@app.on_event("startup")
def load_data() -> None:
    global df, embeddings, show_id_to_idx

    df = pd.read_csv(SHOWS_CSV)
    # Normalise ID to string so lookups are consistent
    df["id"] = df["id"].astype(str)
    # Fill NaNs for fields used in filtering / display
    df["genre"] = df["genre"].fillna("")
    df["content_warnings"] = df["content_warnings"].fillna("")
    df["description"] = df["description"].fillna("")
    df["title"] = df["title"].fillna("")
    df["venue_name"] = df["venue_name"].fillna("")
    df["age_numeric"] = pd.to_numeric(df["age_numeric"], errors="coerce")
    df["price_min_gbp"] = pd.to_numeric(df["price_min_gbp"], errors="coerce")
    df["price_max_gbp"] = pd.to_numeric(df["price_max_gbp"], errors="coerce")
    df["duration_mins"] = pd.to_numeric(df["duration_mins"], errors="coerce")
    df["is_free"] = df["is_free"].fillna(False).astype(bool)
    df["is_pwyw"] = df["is_pwyw"].fillna(False).astype(bool)
    df["cancelled"] = df["cancelled"].fillna(False).astype(bool)
    df["sold_out_count"] = pd.to_numeric(df["sold_out_count"], errors="coerce").fillna(
        0
    )
    df["performance_count"] = pd.to_numeric(
        df["performance_count"], errors="coerce"
    ).fillna(0)
    df["wheelchair_access"] = df["wheelchair_access"].fillna(False).astype(bool)
    df["bsl_interpreted"] = df["bsl_interpreted"].fillna(False).astype(bool)
    df["captioned"] = df["captioned"].fillna(False).astype(bool)
    df["audio_enhancement"] = df["audio_enhancement"].fillna(False).astype(bool)

    show_id_to_idx = {row["id"]: i for i, row in df.iterrows()}

    if EMBEDDINGS_NPY.exists():
        embeddings = np.load(str(EMBEDDINGS_NPY))
        print(f"Loaded embeddings {embeddings.shape}")
    else:
        print(
            "WARNING: embeddings.npy not found. "
            "Run `uv run python embed.py` for NLP reranking."
        )


# ---------------------------------------------------------------------------
# In-memory session state
# ---------------------------------------------------------------------------

sessions: dict[str, dict] = {}


def get_or_create_session(session_id: str) -> dict:
    if session_id not in sessions:
        sessions[session_id] = {"liked": [], "disliked": []}
    return sessions[session_id]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_warnings(raw: str) -> list[str]:
    """Split comma-separated content warnings string into a list."""
    if not raw:
        return []
    return [w.strip() for w in raw.split(",") if w.strip()]


def _row_to_dict(row: pd.Series) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "genre": row["genre"],
        "description": row["description"],
        "venue_name": row["venue_name"],
        "space_name": str(row.get("space_name", "") or ""),
        "duration_mins": None
        if pd.isna(row["duration_mins"])
        else int(row["duration_mins"]),
        "age_restriction": str(row.get("age_restriction", "") or ""),
        "age_numeric": None if pd.isna(row["age_numeric"]) else int(row["age_numeric"]),
        "content_warnings": _parse_warnings(row["content_warnings"]),
        "is_free": bool(row["is_free"]),
        "is_pwyw": bool(row["is_pwyw"]),
        "price_min_gbp": None
        if pd.isna(row["price_min_gbp"])
        else float(row["price_min_gbp"]),
        "price_max_gbp": None
        if pd.isna(row["price_max_gbp"])
        else float(row["price_max_gbp"]),
        "url_website": str(row.get("url_website", "") or ""),
        "thumbnail_url": str(row.get("thumbnail_url", "") or ""),
        "dates_display": str(row.get("dates_display", "") or ""),
        "wheelchair_access": bool(row["wheelchair_access"]),
        "bsl_interpreted": bool(row["bsl_interpreted"]),
        "captioned": bool(row["captioned"]),
        "audio_enhancement": bool(row["audio_enhancement"]),
        "cancelled": bool(row["cancelled"]),
    }


def _rank_by_embeddings(
    indices: list[int],
    liked_ids: list[str],
    disliked_ids: list[str],
) -> list[int]:
    """Re-rank `indices` using cosine similarity to liked/disliked embeddings."""
    if embeddings is None or (not liked_ids and not disliked_ids):
        return indices

    def mean_embedding(ids: list[str]) -> Optional[np.ndarray]:
        idxs = [show_id_to_idx[sid] for sid in ids if sid in show_id_to_idx]
        if not idxs:
            return None
        return embeddings[idxs].mean(axis=0, keepdims=True)

    liked_vec = mean_embedding(liked_ids)
    disliked_vec = mean_embedding(disliked_ids)

    pool = embeddings[indices]  # shape (n, 384)

    scores = np.zeros(len(indices))
    if liked_vec is not None:
        scores += cosine_similarity(pool, liked_vec).flatten()
    if disliked_vec is not None:
        scores -= 0.5 * cosine_similarity(pool, disliked_vec).flatten()

    order = np.argsort(-scores)
    return [indices[i] for i in order]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/genres")
def get_genres() -> list[str]:
    return sorted(df["genre"].dropna().unique().tolist())


@app.get("/api/warnings")
def get_warnings() -> list[str]:
    all_warnings: set[str] = set()
    for raw in df["content_warnings"]:
        for w in _parse_warnings(raw):
            all_warnings.add(w)
    return sorted(all_warnings)


@app.post("/api/session")
def create_session() -> dict:
    session_id = str(uuid.uuid4())
    sessions[session_id] = {"liked": [], "disliked": []}
    return {"session_id": session_id}


@app.get("/api/shows")
def get_shows(
    session_id: str = "",
    genres: str = "",
    exclude_warnings: str = "",
    max_price: Optional[float] = None,
    is_free: Optional[bool] = None,
    max_age: Optional[int] = None,
    wheelchair: Optional[bool] = None,
    bsl: Optional[bool] = None,
    captioned: Optional[bool] = None,
    exclude_cancelled: bool = True,
    exclude_sold_out: bool = False,
) -> list[dict]:
    mask = pd.Series([True] * len(df), index=df.index)

    if exclude_cancelled:
        mask &= ~df["cancelled"]

    if exclude_sold_out:
        mask &= df["sold_out_count"] < df["performance_count"]

    if genres:
        selected = [g.strip() for g in genres.split(",") if g.strip()]
        if selected:
            mask &= df["genre"].isin(selected)

    if exclude_warnings:
        bad = [w.strip() for w in exclude_warnings.split("|") if w.strip()]
        for w in bad:
            mask &= ~df["content_warnings"].str.contains(w, case=False, na=False)

    if is_free is True:
        mask &= df["is_free"] | df["is_pwyw"]

    if max_price is not None:
        mask &= (df["price_min_gbp"] <= max_price) | df["is_free"] | df["is_pwyw"]

    if max_age is not None:
        mask &= (df["age_numeric"].isna()) | (df["age_numeric"] <= max_age)

    if wheelchair is True:
        mask &= df["wheelchair_access"]
    if bsl is True:
        mask &= df["bsl_interpreted"]
    if captioned is True:
        mask &= df["captioned"]

    filtered = df[mask]
    indices = filtered.index.tolist()

    # Exclude already-swiped shows
    session = (
        get_or_create_session(session_id)
        if session_id
        else {"liked": [], "disliked": []}
    )
    seen = set(session["liked"] + session["disliked"])
    indices = [i for i in indices if df.at[i, "id"] not in seen]

    # NLP re-rank
    indices = _rank_by_embeddings(indices, session["liked"], session["disliked"])

    return [_row_to_dict(df.loc[i]) for i in indices]


class SwipeRequest(BaseModel):
    session_id: str
    show_id: str
    liked: bool


@app.post("/api/swipe")
def record_swipe(body: SwipeRequest) -> dict:
    session = get_or_create_session(body.session_id)
    key = "liked" if body.liked else "disliked"
    if body.show_id not in session[key]:
        session[key].append(body.show_id)
    return {
        "liked_count": len(session["liked"]),
        "disliked_count": len(session["disliked"]),
    }


@app.get("/api/liked")
def get_liked(session_id: str) -> list[dict]:
    session = get_or_create_session(session_id)
    rows = []
    for show_id in session["liked"]:
        idx = show_id_to_idx.get(show_id)
        if idx is not None:
            rows.append(_row_to_dict(df.loc[idx]))
    return rows


# ---------------------------------------------------------------------------
# Serve frontend in production
# ---------------------------------------------------------------------------

_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="static")
