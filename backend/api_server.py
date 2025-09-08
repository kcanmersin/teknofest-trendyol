from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import os, re, unicodedata, numpy as np, polars as pl
from joblib import load
from sklearn.metrics.pairwise import cosine_similarity
import traceback, logging

app = FastAPI(title="Search + Rank API")

ARTIF_DIR = os.path.expanduser("~/.cache/trendyol/artifacts_enes")
MODEL_DIR = os.path.expanduser("~/models")
FE_PATH   = "/home/jupyter/trendyol-teknofest-hackathon/hackathon_2nd_phase_data/frontend_data.parquet"

vec = load(os.path.join(ARTIF_DIR, "tfidf_vec.joblib"))
X_corpus = load(os.path.join(ARTIF_DIR, "tfidf_X.joblib"))
id_list = load(os.path.join(ARTIF_DIR, "ids.joblib"))

id_to_idx = {cid: i for i, cid in enumerate(id_list)}

fe = pl.read_parquet(FE_PATH).select([
    "content_id_hashed","content_title","image_url",
    "selling_price","content_rate_avg","content_review_count"
])

m_click = None
m_order = None
try:
    m_click = load(os.path.join(MODEL_DIR, "m_click_catboost.joblib"))
except Exception:
    pass
try:
    m_order = load(os.path.join(MODEL_DIR, "m_order_catboost.joblib"))
except Exception:
    pass

def norm_query(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s.lower().strip())
    s = re.sub(r"[_/\-\\]", " ", s)
    s = re.sub(r"[^0-9a-zçğıöşü\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def minmax(a):
    a = np.asarray(a, dtype=np.float32)
    if a.size == 0:
        return a
    mn, mx = float(np.min(a)), float(np.max(a))
    return (a - mn) / (mx - mn + 1e-12) if mx > mn else np.zeros_like(a, dtype=np.float32)

def tfidf_score(query: str, cid: str) -> float:
    """Tek ürün için TF-IDF cosine sim."""
    if cid not in id_to_idx:
        return 0.0
    q = norm_query(query)
    if not q:
        return 0.0
    qv = vec.transform([q])               
    cv = X_corpus[id_to_idx[cid]]         
    return float(cosine_similarity(qv, cv)[0][0])

def retrieve_ids(query: str, topk: int = 200):
    q = norm_query(query)
    if not q:
        return []
    qv = vec.transform([q])
    sims = cosine_similarity(qv, X_corpus)[0]
    order = np.argsort(sims)[::-1][:topk]
    return [id_list[i] for i in order], sims[order]

def rank_query(query: str, topk_retrieval=200, topk_final=50):
    ids_ret, _ = retrieve_ids(query, topk_retrieval) 
    if not ids_ret:
        return pl.DataFrame({
            "content_id_hashed": [], "content_title": [], "image_url": [],
            "selling_price": [], "content_rate_avg": [], "content_review_count": [], "score": []
        })

    df = pl.DataFrame({"content_id_hashed": ids_ret}).with_columns(
        pl.col("content_id_hashed")
          .map_elements(lambda cid: tfidf_score(query, cid))
          .alias("tfidf_sim")
    )

    df = df.join(fe, on="content_id_hashed", how="left").with_columns(
        pl.col("selling_price").fill_null(0.0),
        pl.col("content_rate_avg").fill_null(0.0),
        pl.col("content_review_count").fill_null(0)
    )

    Xq = df.select(["tfidf_sim"]).to_pandas().values
    s_click = m_click.predict(Xq)
    s_order = m_order.predict(Xq)
    final = 0.3 * minmax(s_click) + 0.7 * minmax(s_order)

    order_idx = np.argsort(-final)[:topk_final]
    order_idx = order_idx.astype(int)


    scores_df = pl.DataFrame({
        "_row": order_idx,
        "score": final[order_idx].astype(np.float32)
    })

    out = (
        df
        .with_row_index("_row")   
        .join(scores_df, on="_row", how="inner")
        .sort("_row")
        .drop("_row")
    )

    return out


@app.get("/healthz")
def healthz():
    return JSONResponse({
        "status": "ok",
        "fe_rows": int(fe.height),
        "has_click_model": m_click is not None,
        "has_order_model": m_order is not None
    })

@app.get("/search")
def search(q: str = Query(..., description="Arama sorgusu"),
           topk: int = Query(50, ge=1, le=200)):
    try:
        res = rank_query(q, topk_retrieval=max(topk*4, 100), topk_final=topk)
        return JSONResponse(res.to_pandas().to_dict(orient="records"))
    except Exception as e:
        logging.exception("Search handler failed")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "traceback": traceback.format_exc()}
        )
