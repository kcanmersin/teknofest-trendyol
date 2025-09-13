import numpy as np
import polars as pl
from sklearn.metrics.pairwise import cosine_similarity

from .ml_loader import vec, X_corpus, id_list, id_to_idx, m_click, m_order, fe
from .utils import norm_query, minmax, log_with_timestamp

def tfidf_score(query: str, cid: str) -> float:
    """Calculate TF-IDF cosine similarity for single product"""
    if vec is None or X_corpus is None or cid not in id_to_idx:
        return 0.0
    q = norm_query(query)
    if not q:
        return 0.0
    qv = vec.transform([q])               
    cv = X_corpus[id_to_idx[cid]]         
    return float(cosine_similarity(qv, cv)[0][0])

def retrieve_ids(query: str, topk: int = 200):
    """Retrieve product IDs using TF-IDF"""
    if vec is None or X_corpus is None:
        return [], []
    q = norm_query(query)
    if not q:
        return [], []
    qv = vec.transform([q])
    sims = cosine_similarity(qv, X_corpus)[0]
    order = np.argsort(sims)[::-1][:topk]
    return [id_list[i] for i in order], sims[order]

def ml_search(query: str, topk_retrieval=200, topk_final=50):
    """ML-based search using TF-IDF + CatBoost"""
    if vec is None or X_corpus is None or m_click is None or m_order is None or fe is None:
        log_with_timestamp("ML models not available for search", "WARN")
        return pl.DataFrame({
            "content_id_hashed": [], "content_title": [], "image_url": [],
            "selling_price": [], "content_rate_avg": [], "content_review_count": [], 
            "score": [], "tfidf_sim": []
        })

    log_with_timestamp(f"ML Step 1: TF-IDF retrieval (top {topk_retrieval})")
    ids_ret, sims = retrieve_ids(query, topk_retrieval) 
    if not ids_ret:
        log_with_timestamp("No products found in TF-IDF retrieval")
        return pl.DataFrame({
            "content_id_hashed": [], "content_title": [], "image_url": [],
            "selling_price": [], "content_rate_avg": [], "content_review_count": [], 
            "score": [], "tfidf_sim": []
        })
    
    log_with_timestamp(f"ML Step 1 Complete: {len(ids_ret)} products retrieved")

    log_with_timestamp("ML Step 2: Computing TF-IDF similarities...")
    df = pl.DataFrame({"content_id_hashed": ids_ret}).with_columns(
        pl.col("content_id_hashed")
          .map_elements(lambda cid: tfidf_score(query, cid))
          .alias("tfidf_sim")
    )

    log_with_timestamp("ML Step 3: Joining with product features...")
    df = df.join(fe, on="content_id_hashed", how="left").with_columns([
        pl.col("selling_price").fill_null(0.0),
        pl.col("original_price").fill_null(0.0),
        pl.col("discounted_price").fill_null(0.0),
        pl.col("content_rate_avg").fill_null(0.0),
        pl.col("content_review_count").fill_null(0),
        pl.col("content_rate_count").fill_null(0),
        pl.col("merchant_count").fill_null(0.0),
        pl.col("content_title").fill_null("Ürün"),
        pl.col("level1_category_name").fill_null(""),
        pl.col("level2_category_name").fill_null(""),
        pl.col("leaf_category_name").fill_null(""),
        pl.col("image_url").fill_null("")
    ])

    log_with_timestamp("ML Step 4: Running CatBoost predictions...")
    Xq = df.select(["tfidf_sim"]).to_pandas().values
    s_click = m_click.predict(Xq)
    s_order = m_order.predict(Xq)
    
    log_with_timestamp(f"Click predictions: min={s_click.min():.4f}, max={s_click.max():.4f}")
    log_with_timestamp(f"Order predictions: min={s_order.min():.4f}, max={s_order.max():.4f}")
    
    final = 0.3 * minmax(s_click) + 0.7 * minmax(s_order)
    log_with_timestamp(f"Final combined score: min={final.min():.4f}, max={final.max():.4f}")

    order_idx = np.argsort(-final)[:topk_final]
    order_idx = order_idx.astype(int)
    
    log_with_timestamp(f"ML Step 4 Complete: Top {topk_final} products selected")

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