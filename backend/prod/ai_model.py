import os
import re
import unicodedata
import numpy as np
import polars as pl
from joblib import load
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import faiss
try:
    from rerankers import CrossEncoderReranker, ColBERTReranker
except ImportError:
    try:
        from rerankers import Reranker
        CrossEncoderReranker = Reranker
        ColBERTReranker = Reranker
    except ImportError:
        CrossEncoderReranker = None
        ColBERTReranker = None
from config import ARTIF_DIR, MODEL_DIR, FE_PATH, RERANKER_MODE, TOPK_RECALL_DEFAULT, TOPK_RETURN_DEFAULT, log_with_timestamp

# ===== ML MODEL LOADING =====
vec = None
X_corpus = None
id_list = None
id_to_idx = {}
m_click = None
m_order = None

# ===== HYBRID SEMANTIC SEARCH MODELS =====
sbert_model = None
sbert_ids = None
sbert_embs = None
faiss_index = None
reranker = None

# ===== ML FEATURE DATA =====
fe = None

def load_tfidf_models():
    """Load TF-IDF models"""
    global vec, X_corpus, id_list, id_to_idx
    try:
        vec = load(os.path.join(ARTIF_DIR, "tfidf_vec.joblib"))
        X_corpus = load(os.path.join(ARTIF_DIR, "tfidf_X.joblib"))
        id_list = load(os.path.join(ARTIF_DIR, "ids.joblib"))
        id_to_idx = {cid: i for i, cid in enumerate(id_list)}
        log_with_timestamp(f"ML TF-IDF models loaded successfully (vocab: {len(vec.vocabulary_)}, corpus: {X_corpus.shape})")
    except Exception as e:
        log_with_timestamp(f"ML TF-IDF models failed to load: {e}", "WARN")

def load_click_model():
    """Load click prediction model"""
    global m_click
    try:
        m_click = load(os.path.join(MODEL_DIR, "m_click_catboost.joblib"))
        log_with_timestamp("ML Click prediction model loaded successfully")
    except Exception as e:
        log_with_timestamp(f"ML Click model failed to load: {e}", "WARN")

def load_order_model():
    """Load order prediction model"""
    global m_order
    try:
        m_order = load(os.path.join(MODEL_DIR, "m_order_catboost.joblib"))
        log_with_timestamp("ML Order prediction model loaded successfully")
    except Exception as e:
        log_with_timestamp(f"ML Order model failed to load: {e}", "WARN")

def load_sbert_models():
    """Load SBERT models for semantic search"""
    global sbert_model, sbert_ids, sbert_embs, faiss_index
    try:
        log_with_timestamp("Loading SBERT model...")
        sbert_model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
        sbert_ids = load(os.path.join(ARTIF_DIR, "sbert_ids.joblib"))
        sbert_embs = np.load(os.path.join(ARTIF_DIR, "sbert_emb.npy"))
        faiss_index = faiss.read_index(os.path.join(ARTIF_DIR, "sbert_faiss.index"))
        log_with_timestamp(f"SBERT models loaded successfully (embeddings: {sbert_embs.shape}, index size: {faiss_index.ntotal})")
    except Exception as e:
        log_with_timestamp(f"SBERT models failed to load: {e}", "WARN")
        sbert_model = None
        sbert_ids = None
        sbert_embs = None
        faiss_index = None

def load_reranker():
    """Load reranker model"""
    global reranker
    try:
        log_with_timestamp(f"Loading reranker ({RERANKER_MODE})...")
        if CrossEncoderReranker is None:
            log_with_timestamp("Reranker classes not available, skipping...", "WARN")
            reranker = None
            return

        if RERANKER_MODE == "colbert":
            reranker = ColBERTReranker()
        else:
            reranker = CrossEncoderReranker()
        log_with_timestamp(f"Reranker loaded successfully: {RERANKER_MODE}")
    except Exception as e:
        log_with_timestamp(f"Reranker failed to load: {e}", "WARN")
        reranker = None

def load_feature_data():
    """Load ML feature data"""
    global fe
    try:
        log_with_timestamp("Loading ML feature data...")
        fe = pl.read_parquet(FE_PATH).select([
            "content_id_hashed","content_title","image_url",
            "selling_price","content_rate_avg","content_review_count",
            "level1_category_name","level2_category_name","leaf_category_name",
            "original_price","discounted_price","merchant_count","content_rate_count"
        ])
        log_with_timestamp(f"ML Feature data loaded successfully: {len(fe)} products with all fields")
    except Exception as e:
        log_with_timestamp(f"ML Feature data failed to load: {e}", "ERROR")
        fe = None

def load_all_models():
    """Load all AI models and data"""
    load_tfidf_models()
    load_click_model()
    load_order_model()
    load_sbert_models()
    load_reranker()
    load_feature_data()

# ===== ML HELPER FUNCTIONS =====
def norm_query(s: str) -> str:
    """Normalize query text for TF-IDF search"""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s.lower().strip())
    s = re.sub(r"[_/\-\\]", " ", s)
    s = re.sub(r"[^0-9a-zçğıöşü\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def norm_text(s: str) -> str:
    """Normalize text for SBERT"""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s.lower().strip())
    s = re.sub(r"[_\-/]", " ", s)
    s = re.sub(r"[^0-9a-zçğıöşü\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def minmax(a):
    """Min-max normalization"""
    a = np.asarray(a, dtype=np.float32)
    if a.size == 0:
        return a
    mn, mx = float(np.min(a)), float(np.max(a))
    return (a - mn) / (mx - mn + 1e-12) if mx > mn else np.zeros_like(a, dtype=np.float32)

def tfidf_score(query: str, cid: str) -> float:
    """Calculate TF-IDF cosine similarity for a single product"""
    if vec is None or X_corpus is None or cid not in id_to_idx:
        return 0.0
    q = norm_query(query)
    if not q:
        return 0.0
    qv = vec.transform([q])
    cv = X_corpus[id_to_idx[cid]]
    return float(cosine_similarity(qv, cv)[0][0])

def retrieve_ids(query: str, topk: int = 200):
    """Retrieve product IDs using TF-IDF similarity"""
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
    """Perform ML-based search using TF-IDF + CatBoost"""
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

def sbert_recall(query: str, topk: int):
    """Perform SBERT + FAISS semantic retrieval"""
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

def build_doc_text(title: str, level2_category: str, leaf_category: str) -> str:
    """Build document text for reranker"""
    parts = []
    if title and title != "Ürün":
        parts.append(title)
    if level2_category:
        parts.append(level2_category)
    if leaf_category and leaf_category != level2_category:
        parts.append(leaf_category)
    return " ".join(parts) if parts else "Ürün"

def hybrid_semantic_search(query: str, recall_k: int = TOPK_RECALL_DEFAULT, return_k: int = TOPK_RETURN_DEFAULT):
    """Perform enhanced hybrid semantic search with SBERT + Advanced Reranker"""
    if (sbert_model is None or faiss_index is None or
        sbert_ids is None or fe is None):
        log_with_timestamp("Hybrid semantic search models not available", "WARN")
        return pl.DataFrame({
            "content_id_hashed": [], "content_title": [], "image_url": [],
            "selling_price": [], "content_rate_avg": [], "content_review_count": [],
            "score": []
        })

    log_with_timestamp(f"Semantic Step 1: SBERT recall (top {recall_k})")
    ids, sbert_scores = sbert_recall(query, recall_k)
    if not ids:
        log_with_timestamp("No products found in SBERT recall")
        return pl.DataFrame({
            "content_id_hashed": [], "content_title": [], "image_url": [],
            "selling_price": [], "content_rate_avg": [], "content_review_count": [],
            "score": []
        })

    log_with_timestamp(f"Semantic Step 1 Complete: {len(ids)} products retrieved")

    # Join with product features first
    df = pl.DataFrame({"content_id_hashed": ids}).join(fe, on="content_id_hashed", how="left")

    log_with_timestamp("Semantic Step 2: Advanced reranking with rich document context...")

    # Build rich document texts
    doc_texts = []
    for row in df.to_dicts():
        doc_text = build_doc_text(
            row.get("content_title", ""),
            row.get("level2_category_name", ""),
            row.get("leaf_category_name", "")
        )
        doc_texts.append(doc_text)

    # Rerank with rich context
    reranker_scores = reranker.score(query, doc_texts, batch_size=64)

    log_with_timestamp(f"Reranker scores: min={np.min(reranker_scores):.4f}, max={np.max(reranker_scores):.4f}")
    log_with_timestamp(f"SBERT scores: min={np.min(sbert_scores):.4f}, max={np.max(sbert_scores):.4f}")

    # Advanced hybrid scoring with reranker priority
    if reranker is not None:
        # Reranker-first approach
        order_idx = np.argsort(-reranker_scores)[:return_k].astype(np.int64)
        final_scores = reranker_scores[order_idx]

        log_with_timestamp("Using reranker-first scoring approach")
    else:
        # Fallback to SBERT only
        order_idx = np.argsort(-sbert_scores)[:return_k].astype(np.int64)
        final_scores = sbert_scores[order_idx]

    log_with_timestamp(f"Semantic Step 2 Complete: Top {return_k} products selected")

    # Create result dataframe with proper ordering
    rank_df = pl.DataFrame({
        "__row": order_idx,
        "__rank": np.arange(len(order_idx), dtype=np.int64),
        "score": final_scores.astype(np.float32)
    })

    out = (
        df.with_row_index("__row")
          .join(rank_df, on="__row", how="inner")
          .sort("__rank")
          .drop(["__row", "__rank"])
          .with_columns([
              pl.col("selling_price").fill_null(0.0),
              pl.col("content_rate_avg").fill_null(0.0),
              pl.col("content_review_count").fill_null(0),
              pl.col("content_title").fill_null("Ürün"),
              pl.col("image_url").fill_null(""),
              pl.col("level1_category_name").fill_null(""),
              pl.col("level2_category_name").fill_null(""),
              pl.col("leaf_category_name").fill_null("")
          ])
    )

    return out