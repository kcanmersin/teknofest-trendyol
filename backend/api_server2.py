from fastapi import FastAPI, Query
from fastapi.responses import PlainTextResponse
import os, re, unicodedata, numpy as np, polars as pl
from joblib import load
from sentence_transformers import SentenceTransformer
import faiss

from rerankers import CrossEncoderReranker, ColBERTReranker

app = FastAPI(title="Hybrid Semantic Search (SBERT + Reranker)")

# ------------ CONFIG ------------
ART  = os.path.expanduser("~/.cache/trendyol/artifacts_enes")
FE_P = "/home/jupyter/trendyol-teknofest-hackathon/hackathon_2nd_phase_data/frontend_data.parquet"

RERANKER_MODE = os.environ.get("RERANKER_MODE", "crossencoder").lower()

TOPK_RECALL_DEFAULT = 400   # SBERT'ten çekilecek aday sayısı
TOPK_RETURN_DEFAULT = 50

def norm_text(s: str) -> str:
    if not isinstance(s, str): return ""
    s = unicodedata.normalize("NFKD", s.lower().strip())
    s = re.sub(r"[_\-/]", " ", s)
    s = re.sub(r"[^0-9a-zçğıöşü\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def minmax(a):
    a = np.asarray(a, dtype=np.float32)
    if a.size == 0:
        return a
    mn, mx = float(np.min(a)), float(np.max(a))
    return (a - mn) / (mx - mn + 1e-12) if mx > mn else np.zeros_like(a, dtype=np.float32)

# ------------ LOAD ARTS ------------
sbert = SentenceTransformer("sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
sbert_ids  = load(os.path.join(ART, "sbert_ids.joblib"))
sbert_embs = np.load(os.path.join(ART, "sbert_emb.npy"))  # [N, D], normalized
faiss_idx  = faiss.read_index(os.path.join(ART, "sbert_faiss.index"))

fe = pl.read_parquet(FE_P).select([
    "content_id_hashed","content_title","image_url",
    "selling_price","content_rate_avg","content_review_count"
])

if RERANKER_MODE == "colbert":
    reranker = ColBERTReranker()
else:
    reranker = CrossEncoderReranker()

# ------------ HELPERS ------------
def sbert_recall(query: str, topk: int):
    q = norm_text(query)
    if not q:
        return [], []
    qv = sbert.encode([q], normalize_embeddings=True).astype("float32")  # [1, D]
    sims, idxs = faiss_idx.search(qv, topk)  # cosine ~ IP because normalized
    ids  = [sbert_ids[i] for i in idxs[0]]
    scrs = sims[0]
    return ids, scrs

def texts_for(ids):
    df = fe.filter(pl.col("content_id_hashed").is_in(ids)).select(
        ["content_id_hashed","content_title"]
    ).to_dict(as_series=False)
    title_map = dict(zip(df["content_id_hashed"], df["content_title"]))
    return [title_map.get(cid, cid) for cid in ids]

def rank_pipeline(query: str, recall_k: int, return_k: int):
    ids, sbert_scores = sbert_recall(query, recall_k)
    if not ids:
        return pl.DataFrame(schema={
            "content_id_hashed": pl.Utf8, "content_title": pl.Utf8, "image_url": pl.Utf8,
            "selling_price": pl.Float64, "content_rate_avg": pl.Float64, "content_review_count": pl.Int64,
            "score": pl.Float64
        })

    docs = texts_for(ids)
    rr = reranker.score(query, docs, batch_size=64)

    final = 0.8 * minmax(rr) + 0.2 * minmax(sbert_scores)

    order = np.argsort(-final)[:return_k]
    out_ids = [ids[i] for i in order]
    out = pl.DataFrame({"content_id_hashed": out_ids}).join(fe, on="content_id_hashed", how="left").with_columns([
        pl.Series("score", final[order].astype(np.float32))
    ])
    return out

# ------------ ROUTES ------------
@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "fe_rows": fe.height,
        "recall": "sbert+faiss",
        "reranker": RERANKER_MODE,
        "embeddings": int(sbert_embs.shape[0])
    }

@app.get("/search")
def search(q: str = Query(..., description="arama terimi"),
           topk: int = Query(TOPK_RETURN_DEFAULT, ge=1, le=200),
           recall_k: int = Query(TOPK_RECALL_DEFAULT, ge=50, le=1000)):
    try:
        res = rank_pipeline(q, recall_k=recall_k, return_k=topk)
        return res.to_dicts()
    except Exception as e:
        return PlainTextResponse(str(e), status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="127.0.0.1", port=8600, reload=False)
