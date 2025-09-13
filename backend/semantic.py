from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
import polars as pl
import numpy as np
import os, json

from config import FE_PATH, SBERT_INDEX_DIR, RERANKER_MODE
from retriever_sbert import SBERTMemmapRetriever
from rerankers import CrossEncoderReranker, ColBERTReranker
from utils_text import build_doc_text

app = FastAPI(title="Semantic Search API (SBERT + Rerank)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=False
)

# --- Load FE data ---
fe = pl.read_parquet(FE_PATH).select([
    "content_id_hashed","content_title","image_url",
    "selling_price","content_rate_avg","content_review_count",
    "level2_category_name","leaf_category_name"
]).with_columns([
    pl.col("content_title").fill_null("Ürün"),
    pl.col("image_url").fill_null(""),
    pl.col("level2_category_name").fill_null(""),
    pl.col("leaf_category_name").fill_null(""),
    pl.col("selling_price").fill_null(0.0),
    pl.col("content_rate_avg").fill_null(0.0),
    pl.col("content_review_count").fill_null(0),
])

retriever = SBERTMemmapRetriever(index_dir=SBERT_INDEX_DIR)

reranker = None
if RERANKER_MODE == "cross":
    reranker = CrossEncoderReranker()
elif RERANKER_MODE == "colbert":
    reranker = ColBERTReranker()

@app.get("/healthz")
def healthz():
    meta_path = SBERT_INDEX_DIR / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    return {
        "status": "ok",
        "fe_rows": int(fe.height),
        "sbert_index": {"num": meta.get("num", 0), "dim": meta.get("dim", 0), "model": meta.get("model", "")},
        "reranker": RERANKER_MODE
    }

@app.get("/search")
def search(
    q: str = Query(..., description="Arama sorgusu"),
    topk: int = Query(24, ge=1, le=100),
    retrieve_k: int = Query(200, ge=1, le=1000),
):
    try:
        # 1) SBERT retrieval
        idxs, sims = retriever.retrieve(q, topk=retrieve_k)
        if idxs.size == 0:
            return []

        ids = retriever.ids[idxs]
        df = pl.DataFrame({"content_id_hashed": ids})
        df = df.join(fe, on="content_id_hashed", how="left")

        # --- BURADA reranker bloğu başlıyor ---
        if reranker is not None:
            doc_texts = [
                build_doc_text(r.get("content_title"), r.get("level2_category_name"), r.get("leaf_category_name"))
                for r in df.to_dicts()
            ]
            rerank_scores = reranker.score(q, doc_texts)

            order_idx = np.argsort(-rerank_scores)[:topk].astype(np.int64)
            rank_df   = pl.DataFrame({
                "__row": order_idx,
                "__rank": np.arange(len(order_idx), dtype=np.int64)
            })

            out = (
                df.with_row_index("__row")
                  .join(rank_df, on="__row", how="inner")
                  .sort("__rank")
                  .drop(["__row","__rank"])
                  .with_columns(pl.Series("score", rerank_scores[order_idx].astype(np.float32)))
            )

        else:
            order_idx = np.argsort(-sims)[:topk].astype(np.int64)
            rank_df   = pl.DataFrame({
                "__row": order_idx,
                "__rank": np.arange(len(order_idx), dtype=np.int64)
            })

            out = (
                df.with_row_index("__row")
                  .join(rank_df, on="__row", how="inner")
                  .sort("__rank")
                  .drop(["__row","__rank"])
                  .with_columns(pl.Series("score", sims[order_idx].astype(np.float32)))
            )

        return out.select([
            "content_id_hashed","content_title","image_url",
            "selling_price","content_rate_avg","content_review_count","score"
        ]).to_dicts()

    except Exception as e:
        return PlainTextResponse(str(e), status_code=500)
