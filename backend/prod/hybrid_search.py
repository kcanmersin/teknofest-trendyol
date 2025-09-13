import numpy as np
import polars as pl

from .ml_loader import sbert_model, faiss_index, sbert_ids, reranker, fe
from .config import TOPK_RECALL_DEFAULT, TOPK_RETURN_DEFAULT
from .utils import norm_text, minmax, log_with_timestamp

def sbert_recall(query: str, topk: int):
    """SBERT + FAISS semantic retrieval"""
    if sbert_model is None or faiss_index is None or sbert_ids is None:
        return [], []
    
    q = norm_text(query)
    if not q:
        return [], []
    
    qv = sbert_model.encode([q], normalize_embeddings=True).astype("float32")
    sims, idxs = faiss_index.search(qv, topk)
    ids = [sbert_ids[i] for i in idxs[0]]
    scores = sims[0]
    return ids, scores

def texts_for_reranker(ids):
    """Get product titles for reranker"""
    if fe is None:
        return []
    
    df_filtered = fe.filter(pl.col("content_id_hashed").is_in(ids)).select(
        ["content_id_hashed", "content_title"]
    )
    title_map = dict(zip(
        df_filtered.get_column("content_id_hashed").to_list(),
        df_filtered.get_column("content_title").to_list()
    ))
    return [title_map.get(cid, cid) for cid in ids]

def hybrid_semantic_search(query: str, recall_k: int = TOPK_RECALL_DEFAULT, return_k: int = TOPK_RETURN_DEFAULT):
    """Hybrid Semantic Search: SBERT + Reranker"""
    if (sbert_model is None or faiss_index is None or 
        sbert_ids is None or reranker is None or fe is None):
        log_with_timestamp("Hybrid semantic search models not available", "WARN")
        return pl.DataFrame({
            "content_id_hashed": [], "content_title": [], "image_url": [],
            "selling_price": [], "content_rate_avg": [], "content_review_count": [], 
            "score": []
        })
    
    log_with_timestamp(f"Hybrid Step 1: SBERT recall (top {recall_k})")
    ids, sbert_scores = sbert_recall(query, recall_k)
    if not ids:
        log_with_timestamp("No products found in SBERT recall")
        return pl.DataFrame({
            "content_id_hashed": [], "content_title": [], "image_url": [],
            "selling_price": [], "content_rate_avg": [], "content_review_count": [], 
            "score": []
        })
    
    log_with_timestamp(f"Hybrid Step 1 Complete: {len(ids)} products retrieved")
    
    log_with_timestamp("Hybrid Step 2: Reranking with CrossEncoder/ColBERT...")
    docs = texts_for_reranker(ids)
    reranker_scores = reranker.score(query, docs, batch_size=64)
    
    log_with_timestamp(f"Reranker scores: min={np.min(reranker_scores):.4f}, max={np.max(reranker_scores):.4f}")
    log_with_timestamp(f"SBERT scores: min={np.min(sbert_scores):.4f}, max={np.max(sbert_scores):.4f}")
    
    # Hybrid scoring: 80% reranker + 20% SBERT
    final_scores = 0.8 * minmax(reranker_scores) + 0.2 * minmax(sbert_scores)
    log_with_timestamp(f"Final hybrid scores: min={final_scores.min():.4f}, max={final_scores.max():.4f}")
    
    # Top-k selection
    order = np.argsort(-final_scores)[:return_k]
    out_ids = [ids[i] for i in order]
    
    log_with_timestamp(f"Hybrid Step 2 Complete: Top {return_k} products selected")
    
    # Join with product features
    scores_df = pl.DataFrame({
        "content_id_hashed": out_ids,
        "score": final_scores[order].astype(np.float32)
    })
    
    out = scores_df.join(fe, on="content_id_hashed", how="left").with_columns([
        pl.col("selling_price").fill_null(0.0),
        pl.col("content_rate_avg").fill_null(0.0),
        pl.col("content_review_count").fill_null(0),
        pl.col("content_title").fill_null("Ürün"),
        pl.col("image_url").fill_null("")
    ])
    
    return out