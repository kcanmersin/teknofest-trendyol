import os
import numpy as np
import polars as pl
from joblib import load
from sentence_transformers import SentenceTransformer
import faiss
from rerankers import CrossEncoderReranker, ColBERTReranker

from .config import ARTIF_DIR, MODEL_DIR, FE_PATH, RERANKER_MODE
from .utils import log_with_timestamp

# Global model variables
vec = None
X_corpus = None
id_list = None
id_to_idx = {}
m_click = None
m_order = None
sbert_model = None
sbert_ids = None
sbert_embs = None
faiss_index = None
reranker = None
df = None
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

def load_catboost_models():
    """Load CatBoost models"""
    global m_click, m_order
    try:
        m_click = load(os.path.join(MODEL_DIR, "m_click_catboost.joblib"))
        log_with_timestamp("ML Click prediction model loaded successfully")
    except Exception as e:
        log_with_timestamp(f"ML Click model failed to load: {e}", "WARN")

    try:
        m_order = load(os.path.join(MODEL_DIR, "m_order_catboost.joblib"))
        log_with_timestamp("ML Order prediction model loaded successfully")
    except Exception as e:
        log_with_timestamp(f"ML Order model failed to load: {e}", "WARN")

def load_sbert_models():
    """Load SBERT models"""
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
        if RERANKER_MODE == "colbert":
            reranker = ColBERTReranker()
        else:
            reranker = CrossEncoderReranker()
        log_with_timestamp(f"Reranker loaded successfully: {RERANKER_MODE}")
    except Exception as e:
        log_with_timestamp(f"Reranker failed to load: {e}", "WARN")
        reranker = None

def load_data():
    """Load data"""
    global df, fe
    try:
        log_with_timestamp("Loading DB data...")
        df = pl.read_parquet(FE_PATH)
        log_with_timestamp(f"DB Data loaded successfully: {len(df)} products, {len(df.columns)} columns")
        sample_categories = df.select("level2_category_name").unique().head(5).to_series().to_list()
        log_with_timestamp(f"Sample categories: {', '.join(sample_categories[:3])}...")
    except Exception as e:
        log_with_timestamp(f"DB Data loading failed: {e}", "ERROR")
        df = None

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
    """Load all ML models"""
    load_tfidf_models()
    load_catboost_models()
    load_sbert_models()
    load_reranker()
    load_data()