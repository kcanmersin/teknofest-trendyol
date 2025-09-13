from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os, re, unicodedata, numpy as np, polars as pl
from joblib import load
from sklearn.metrics.pairwise import cosine_similarity
import traceback, logging, random
from typing import List, Dict, Optional
from datetime import datetime
from elasticsearch import Elasticsearch
import asyncio

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Trendyol Unified Search API", version="2.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== ML MODEL PATHS =====
ARTIF_DIR = os.path.expanduser("~/.cache/trendyol/artifacts_enes")
MODEL_DIR = os.path.expanduser("~/models")
FE_PATH = "../trendyol-teknofest-hackathon/hackathon_2nd_phase_data/frontend_data.parquet"

# ===== ML MODEL LOADING =====
vec = None
X_corpus = None
id_list = None
id_to_idx = {}
m_click = None
m_order = None

# ===== ELASTICSEARCH SETUP =====
es_client = None
ELASTICSEARCH_URL = "http://localhost:9200"
PRODUCTS_INDEX = "trendyol_products"

def log_with_timestamp(message, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = "INFO" if level == "INFO" else "WARN" if level == "WARN" else "ERROR"
    print(f"[{timestamp}] {prefix}: {message}")

try:
    vec = load(os.path.join(ARTIF_DIR, "tfidf_vec.joblib"))
    X_corpus = load(os.path.join(ARTIF_DIR, "tfidf_X.joblib"))
    id_list = load(os.path.join(ARTIF_DIR, "ids.joblib"))
    id_to_idx = {cid: i for i, cid in enumerate(id_list)}
    log_with_timestamp(f"ML TF-IDF models loaded successfully (vocab: {len(vec.vocabulary_)}, corpus: {X_corpus.shape})")
except Exception as e:
    log_with_timestamp(f"ML TF-IDF models failed to load: {e}", "WARN")

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

# ===== DB DATA LOADING =====
df = None

def load_data():
    """Veri yükleme fonksiyonu"""
    global df
    try:
        log_with_timestamp("Loading DB data...")
        df = pl.read_parquet(FE_PATH)
        log_with_timestamp(f"DB Data loaded successfully: {len(df)} products, {len(df.columns)} columns")
        # Show sample categories
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

# ===== PYDANTIC MODELS =====
class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 50
    mode: Optional[str] = "db"  # "ml" or "db"

class ProductResponse(BaseModel):
    content_id_hashed: str
    content_title: str
    image_url: str
    level1_category_name: Optional[str] = ""
    level2_category_name: Optional[str] = ""
    leaf_category_name: Optional[str] = ""
    merchant_count: Optional[float] = None
    original_price: Optional[float] = 0.0
    selling_price: float
    discounted_price: Optional[float] = 0.0
    content_review_count: int
    content_rate_count: Optional[int] = 0
    content_rate_avg: Optional[float] = None
    discount_percentage: Optional[float] = None
    # ML-specific fields
    tfidf_sim: Optional[float] = None
    score: Optional[float] = None

class SearchResponse(BaseModel):
    query: str
    total_results: int
    products: List[ProductResponse]
    mode: str

class AdvancedSearchRequest(BaseModel):
    query: str = ""
    category_level1: Optional[str] = None
    category_level2: Optional[str] = None
    category_level2_list: Optional[List[str]] = None
    category_leaf: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None
    min_review_count: Optional[int] = None
    limit: int = 50
    mode: Optional[str] = "db"  # "ml" or "db"

class AutocompleteResponse(BaseModel):
    suggestions: List[Dict[str, str]]
    total: int

# ===== ML HELPER FUNCTIONS =====
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
    if vec is None or X_corpus is None or cid not in id_to_idx:
        return 0.0
    q = norm_query(query)
    if not q:
        return 0.0
    qv = vec.transform([q])               
    cv = X_corpus[id_to_idx[cid]]         
    return float(cosine_similarity(qv, cv)[0][0])

def retrieve_ids(query: str, topk: int = 200):
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

# ===== DB HELPER FUNCTIONS =====
def db_search(query: str, limit: int = 50) -> List[Dict]:
    """DB-based search using Polars filtering"""
    if df is None:
        return []
    
    # Basit kategori filtresi
    if query.lower().strip():
        query_lower = query.lower()
        
        # Kategorilerde ve title'da arama yap
        filtered = df.filter(
            pl.col("content_title").str.to_lowercase().str.contains(query_lower) |
            pl.col("level1_category_name").str.to_lowercase().str.contains(query_lower) |
            pl.col("level2_category_name").str.to_lowercase().str.contains(query_lower) |
            pl.col("leaf_category_name").str.to_lowercase().str.contains(query_lower)
        )
        
        if len(filtered) > 0:
            # Rating'e göre sırala
            sample_size = min(limit * 2, len(filtered))
            sampled = filtered.sample(sample_size) if len(filtered) > sample_size else filtered
            sorted_results = sampled.sort([
                pl.col("content_rate_avg").fill_null(0),
                pl.col("content_review_count")
            ], descending=[True, True])
            return sorted_results.head(limit).to_dicts()
    
    # Rastgele ürünler döndür
    return df.sample(min(limit, len(df))).to_dicts()

# ===== ELASTICSEARCH HELPER FUNCTIONS =====
def init_elasticsearch():
    """Initialize Elasticsearch client and create index"""
    global es_client
    try:
        es_client = Elasticsearch([ELASTICSEARCH_URL])
        
        # Check if connection is successful
        if es_client.ping():
            log_with_timestamp("Elasticsearch connection successful")
            
            # Create index if it doesn't exist
            if not es_client.indices.exists(index=PRODUCTS_INDEX):
                create_autocomplete_index()
                index_product_data()
            else:
                log_with_timestamp(f"Elasticsearch index '{PRODUCTS_INDEX}' already exists")
        else:
            log_with_timestamp("Elasticsearch connection failed", "WARN")
            es_client = None
    except Exception as e:
        log_with_timestamp(f"Elasticsearch initialization failed: {e}", "WARN")
        es_client = None

def create_autocomplete_index():
    """Create Elasticsearch index with autocomplete settings"""
    if es_client is None:
        return
    
    index_body = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "autocomplete": {
                        "tokenizer": "autocomplete",
                        "filter": ["lowercase"]
                    },
                    "autocomplete_search": {
                        "tokenizer": "keyword",
                        "filter": ["lowercase"]
                    }
                },
                "tokenizer": {
                    "autocomplete": {
                        "type": "edge_ngram",
                        "min_gram": 2,
                        "max_gram": 10,
                        "token_chars": ["letter", "digit"]
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "title": {
                    "type": "text",
                    "analyzer": "autocomplete",
                    "search_analyzer": "autocomplete_search"
                },
                "category_level1": {
                    "type": "text",
                    "analyzer": "autocomplete",
                    "search_analyzer": "autocomplete_search"
                },
                "category_level2": {
                    "type": "text",
                    "analyzer": "autocomplete",
                    "search_analyzer": "autocomplete_search"
                },
                "category_leaf": {
                    "type": "text",
                    "analyzer": "autocomplete",
                    "search_analyzer": "autocomplete_search"
                },
                "content_id": {"type": "keyword"},
                "suggestion_type": {"type": "keyword"},
                "popularity": {"type": "integer"}
            }
        }
    }
    
    try:
        es_client.indices.create(index=PRODUCTS_INDEX, body=index_body)
        log_with_timestamp(f"Created Elasticsearch index: {PRODUCTS_INDEX}")
    except Exception as e:
        log_with_timestamp(f"Failed to create index: {e}", "ERROR")

def index_product_data():
    """Index product data for autocomplete"""
    if es_client is None or df is None:
        return
    
    try:
        log_with_timestamp("Indexing product data for autocomplete...")
        
        # Sample data for indexing (to avoid overwhelming ES)
        sample_df = df.sample(min(10000, len(df)))
        
        docs = []
        doc_id = 1
        
        # Index product titles
        for row in sample_df.to_dicts():
            title = row.get('content_title', '').strip()
            if title and title != 'Lorem Ipsum' and len(title) > 2:
                docs.append({
                    "_index": PRODUCTS_INDEX,
                    "_id": doc_id,
                    "_source": {
                        "title": title,
                        "category_level1": row.get('level1_category_name', ''),
                        "category_level2": row.get('level2_category_name', ''),
                        "category_leaf": row.get('leaf_category_name', ''),
                        "content_id": row.get('content_id_hashed', ''),
                        "suggestion_type": "product",
                        "popularity": row.get('content_review_count', 0)
                    }
                })
                doc_id += 1
        
        # Index unique categories
        categories = df.select("level2_category_name").unique().to_series().to_list()
        for cat in categories[:500]:  # Limit categories
            if cat and len(cat) > 2:
                docs.append({
                    "_index": PRODUCTS_INDEX,
                    "_id": doc_id,
                    "_source": {
                        "title": cat,
                        "category_level2": cat,
                        "suggestion_type": "category",
                        "popularity": 100
                    }
                })
                doc_id += 1
        
        # Bulk index
        from elasticsearch.helpers import bulk
        bulk(es_client, docs, chunk_size=1000)
        
        log_with_timestamp(f"Indexed {len(docs)} documents for autocomplete")
        
    except Exception as e:
        log_with_timestamp(f"Failed to index product data: {e}", "ERROR")

def get_autocomplete_suggestions(query: str, limit: int = 10) -> List[Dict]:
    """Get autocomplete suggestions from Elasticsearch"""
    if es_client is None or not query or len(query) < 2:
        return []
    
    try:
        search_body = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "match": {
                                "title": {
                                    "query": query,
                                    "boost": 3
                                }
                            }
                        },
                        {
                            "match": {
                                "category_level2": {
                                    "query": query,
                                    "boost": 2
                                }
                            }
                        }
                    ]
                }
            },
            "sort": [
                {"popularity": {"order": "desc"}},
                "_score"
            ],
            "size": limit,
            "_source": ["title", "suggestion_type", "category_level2"]
        }
        
        response = es_client.search(index=PRODUCTS_INDEX, body=search_body)
        
        suggestions = []
        seen = set()
        
        for hit in response['hits']['hits']:
            source = hit['_source']
            title = source.get('title', '').strip()
            
            if title and title.lower() not in seen and len(title) > 1:
                suggestions.append({
                    "text": title,
                    "type": source.get('suggestion_type', 'product'),
                    "category": source.get('category_level2', '')
                })
                seen.add(title.lower())
        
        return suggestions[:limit]
        
    except Exception as e:
        log_with_timestamp(f"Autocomplete search failed: {e}", "WARN")
        return []

# ===== API ENDPOINTS =====
@app.on_event("startup")
async def startup_event():
    """Uygulama başlangıcında veri yükle"""
    log_with_timestamp("STARTING TRENDYOL UNIFIED SEARCH API")
    log_with_timestamp("=" * 60)
    log_with_timestamp("Loading application data...")
    load_data()
    
    # Initialize Elasticsearch
    log_with_timestamp("Initializing Elasticsearch for autocomplete...")
    init_elasticsearch()
    
    # Status check
    ml_ready = (vec is not None and X_corpus is not None and 
                m_click is not None and m_order is not None and fe is not None)
    db_ready = df is not None
    es_ready = es_client is not None
    
    log_with_timestamp("SYSTEM STATUS:")
    log_with_timestamp(f"   ML Engine: {'READY' if ml_ready else 'NOT READY'}")
    log_with_timestamp(f"   DB Engine: {'READY' if db_ready else 'NOT READY'}")
    log_with_timestamp(f"   Elasticsearch: {'READY' if es_ready else 'NOT READY'}")
    
    if ml_ready:
        log_with_timestamp(f"   ML Corpus Size: {X_corpus.shape[0]} products")
        log_with_timestamp(f"   Vocabulary Size: {len(vec.vocabulary_)} terms")
    
    if db_ready:
        log_with_timestamp(f"   DB Size: {len(df)} products")
        unique_categories = df.select("level2_category_name").n_unique()
        log_with_timestamp(f"     Categories: {unique_categories} unique")
    
    if es_ready:
        log_with_timestamp(f"   Elasticsearch Index: {PRODUCTS_INDEX}")
    
    log_with_timestamp("Available endpoints:")
    log_with_timestamp("   • POST /search (supports mode='ml' or 'db')")
    log_with_timestamp("   • GET /autocomplete")
    log_with_timestamp("   • GET /healthz")
    log_with_timestamp("   • GET /categories")
    log_with_timestamp("=" * 60)
    log_with_timestamp("APPLICATION READY FOR REQUESTS")

@app.get("/")
async def root():
    return {"message": "Trendyol Unified Search API", "status": "active", "modes": ["ml", "db"]}

@app.get("/healthz")
def healthz():
    return JSONResponse({
        "status": "ok",
        "db_rows": int(df.height) if df is not None else 0,
        "ml_fe_rows": int(fe.height) if fe is not None else 0,
        "has_click_model": m_click is not None,
        "has_order_model": m_order is not None,
        "has_tfidf": (vec is not None and X_corpus is not None)
    })

@app.post("/search", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    try:
        mode = request.mode or "db"
        
        log_with_timestamp("=" * 60)
        log_with_timestamp(f"NEW SEARCH REQUEST")
        log_with_timestamp(f"Query: '{request.query}'")
        log_with_timestamp(f"Mode: {mode.upper()}")
        log_with_timestamp(f"Limit: {request.limit}")
        log_with_timestamp("=" * 60)
        
        if mode == "ml":
            log_with_timestamp("USING MACHINE LEARNING SEARCH ENGINE")
            # ML-based search
            if vec is None or X_corpus is None or m_click is None or m_order is None or fe is None:
                log_with_timestamp("ML models not available!", "ERROR")
                raise HTTPException(status_code=500, detail="ML models not loaded")
            
            log_with_timestamp("Running TF-IDF retrieval...")
            topk_retrieval = max(request.limit*4, 100)
            res_df = ml_search(request.query, topk_retrieval=topk_retrieval, topk_final=request.limit)
            results = res_df.to_pandas().to_dict(orient="records")
            
            log_with_timestamp(f"ML Search completed: {len(results)} products found")
            if results:
                avg_score = sum(r.get('score', 0) for r in results) / len(results)
                avg_tfidf = sum(r.get('tfidf_sim', 0) for r in results) / len(results)
                log_with_timestamp(f"Average ML Score: {avg_score:.4f}, Average TF-IDF: {avg_tfidf:.4f}")
            
            products = []
            for product in results:
                # ML mode için de title'ı düzelt
                title = product.get('content_title', 'Ürün')
                if title == 'Lorem Ipsum':
                    title = f"{product.get('level2_category_name', 'Ürün')} - {product.get('leaf_category_name', 'Detay')}"
                
                # İndirim yüzdesini hesapla
                original = product.get('original_price', 0)
                selling = product.get('selling_price', 0)
                discount_pct = None
                if original and selling and original > selling and original > 0:
                    discount_pct = round(((original - selling) / original) * 100, 1)
                
                products.append(ProductResponse(
                    content_id_hashed=product.get('content_id_hashed', ''),
                    content_title=title,
                    image_url=product.get('image_url', ''),
                    level1_category_name=product.get('level1_category_name', ''),
                    level2_category_name=product.get('level2_category_name', ''),
                    leaf_category_name=product.get('leaf_category_name', ''),
                    merchant_count=product.get('merchant_count'),
                    original_price=product.get('original_price', 0.0),
                    selling_price=product.get('selling_price', 0.0),
                    discounted_price=product.get('discounted_price', 0.0),
                    content_review_count=int(product.get('content_review_count', 0)),
                    content_rate_count=int(product.get('content_rate_count', 0)),
                    content_rate_avg=product.get('content_rate_avg'),
                    discount_percentage=discount_pct,
                    tfidf_sim=product.get('tfidf_sim'),
                    score=product.get('score')
                ))
            
        else:
            log_with_timestamp("USING DATABASE SEARCH ENGINE")
            # DB-based search
            if df is None:
                log_with_timestamp("Database not available!", "ERROR")
                raise HTTPException(status_code=500, detail="Database not loaded")
            
            log_with_timestamp("Running DB query with Polars filters...")
            results = db_search(request.query, request.limit)
            
            log_with_timestamp(f"DB Search completed: {len(results)} products found")
            if results:
                avg_price = sum(r.get('selling_price', 0) for r in results) / len(results)
                avg_rating = sum(r.get('content_rate_avg', 0) or 0 for r in results) / len(results)
                log_with_timestamp(f"Average Price: {avg_price:.2f}, Average Rating: {avg_rating:.2f}")
            
            products = []
            for product in results:
                title = product.get('content_title', 'Ürün')
                if title == 'Lorem Ipsum':
                    title = f"{product.get('level2_category_name', 'Ürün')} - {product.get('leaf_category_name', 'Detay')}"
                
                # İndirim yüzdesini hesapla
                original = product.get('original_price', 0)
                selling = product.get('selling_price', 0)
                discount_pct = None
                if original > selling and original > 0:
                    discount_pct = round(((original - selling) / original) * 100, 1)
                
                products.append(ProductResponse(
                    content_id_hashed=product.get('content_id_hashed', ''),
                    content_title=title,
                    image_url=product.get('image_url', ''),
                    level1_category_name=product.get('level1_category_name', ''),
                    level2_category_name=product.get('level2_category_name', ''),
                    leaf_category_name=product.get('leaf_category_name', ''),
                    merchant_count=product.get('merchant_count'),
                    original_price=product.get('original_price', 0.0),
                    selling_price=product.get('selling_price', 0.0),
                    discounted_price=product.get('discounted_price', 0.0),
                    content_review_count=int(product.get('content_review_count', 0)),
                    content_rate_count=int(product.get('content_rate_count', 0)),
                    content_rate_avg=product.get('content_rate_avg'),
                    discount_percentage=discount_pct
                ))
        
        response = SearchResponse(
            query=request.query,
            total_results=len(products),
            products=products,
            mode=mode
        )
        
        log_with_timestamp("SEARCH COMPLETED SUCCESSFULLY")
        log_with_timestamp(f"Final Results: {len(products)} products returned")
        log_with_timestamp(f"Engine Used: {mode.upper()}")
        log_with_timestamp("=" * 60)
        
        return response
        
    except Exception as e:
        logging.exception("Search handler failed")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "traceback": traceback.format_exc()}
        )

@app.get("/search")
def search_get(q: str = Query(..., description="Arama sorgusu"),
               topk: int = Query(50, ge=1, le=200),
               mode: str = Query("ml", description="Search mode: ml or db")):
    """GET endpoint for ML compatibility"""
    try:
        request = SearchRequest(query=q, limit=topk, mode=mode)
        return search_products(request)
    except Exception as e:
        logging.exception("GET Search handler failed")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "traceback": traceback.format_exc()}
        )

@app.get("/categories")
async def get_categories():
    """Tüm kategorileri ve sayılarını döndür"""
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    try:
        # Level1 kategoriler
        level1_stats = df.group_by("level1_category_name").agg([
            pl.len().alias("product_count")
        ]).sort("product_count", descending=True)
        
        # Level2 kategoriler
        level2_stats = df.group_by(["level1_category_name", "level2_category_name"]).agg([
            pl.len().alias("product_count")
        ]).sort("product_count", descending=True)
        
        # Leaf kategoriler
        leaf_stats = df.group_by(["level1_category_name", "level2_category_name", "leaf_category_name"]).agg([
            pl.len().alias("product_count")
        ]).sort("product_count", descending=True)
        
        return {
            "level1_categories": level1_stats.to_dicts(),
            "level2_categories": level2_stats.to_dicts(),
            "leaf_categories": leaf_stats.to_dicts(),
            "total_products": len(df)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Categories error: {str(e)}")

@app.get("/categories/grouped")
async def get_grouped_categories():
    """Frontend sidebar için optimize edilmiş gruplu kategoriler"""
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    try:
        # Level2 kategorileri grupla
        level2_stats = df.group_by(["level1_category_name", "level2_category_name"]).agg([
            pl.len().alias("product_count")
        ]).sort("product_count", descending=True)
        
        # Mantıklı gruplara ayır
        category_groups = {
            "Giyim & Moda": {
                "level1_names": ["Giyim"],
                "icon": "fas fa-tshirt",
                "color": "#0f766e"
            },
            "Ayakkabı": {
                "level1_names": ["Ayakkabı"], 
                "icon": "fas fa-shoe-prints",
                "color": "#7c3aed"
            },
            "Aksesuar & Takı": {
                "level1_names": ["Aksesuar"],
                "icon": "fas fa-gem", 
                "color": "#dc2626"
            },
            "Ev & Yaşam": {
                "level1_names": ["Ev & Mobilya", "Banyo Yapı & Hırdavat", "Bahçe & Elektrikli El Aletleri"],
                "icon": "fas fa-home",
                "color": "#059669"
            },
            "Kozmetik & Bakım": {
                "level1_names": ["Kozmetik & Kişisel Bakım"],
                "icon": "fas fa-spa",
                "color": "#ec4899"
            },
            "Spor & Eğlence": {
                "level1_names": ["Spor & Outdoor", "Hobi & Eğlence"],
                "icon": "fas fa-dumbbell",
                "color": "#f59e0b"
            },
            "Anne & Bebek": {
                "level1_names": ["Anne & Bebek & Çocuk"],
                "icon": "fas fa-baby",
                "color": "#06b6d4"
            },
            "Teknoloji & Diğer": {
                "level1_names": ["Elektronik", "Otomobil & Motosiklet", "Kırtasiye & Ofis Malzemeleri", "Kitap", "Süpermarket", "Ek Hizmetler", "unknown"],
                "icon": "fas fa-laptop",
                "color": "#6366f1"
            }
        }
        
        result = {}
        level2_data = level2_stats.to_dicts()
        
        for group_name, group_info in category_groups.items():
            subcategories = []
            for category in level2_data:
                if category["level1_category_name"] in group_info["level1_names"]:
                    subcategories.append({
                        "name": category["level2_category_name"],
                        "count": category["product_count"],
                        "level1_parent": category["level1_category_name"]
                    })
            
            # En popüler 15 kategoriyi al
            subcategories = sorted(subcategories, key=lambda x: x["count"], reverse=True)[:15]
            
            if subcategories:  # Boş grupları dahil etme
                result[group_name] = {
                    "icon": group_info["icon"],
                    "color": group_info["color"],
                    "subcategories": subcategories,
                    "total_products": sum(sub["count"] for sub in subcategories)
                }
        
        return {
            "groups": result,
            "total_products": len(df)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Grouped categories error: {str(e)}")

@app.get("/popular-categories")
async def get_popular_categories(limit: int = 10):
    """En popüler kategorileri döndür"""
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    try:
        # Popüler Level2 kategoriler
        popular = df.group_by("level2_category_name").agg([
            pl.len().alias("product_count"),
            pl.mean("content_rate_avg").alias("avg_rating"),
            pl.mean("original_price").alias("avg_price")
        ]).filter(
            pl.col("product_count") > 100  # En az 100 ürün olan kategoriler
        ).sort("product_count", descending=True).head(limit)
        
        return {
            "popular_categories": popular.to_dicts(),
            "total_categories": len(df.select("level2_category_name").unique())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Popular categories error: {str(e)}")

@app.post("/search/advanced", response_model=SearchResponse)
async def advanced_search(request: AdvancedSearchRequest):
    """Gelişmiş arama - kategori ve fiyat filtreleriyle"""
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    try:
        mode = request.mode or "db"
        
        # Şimdilik sadece DB mode destekleniyor
        if mode == "ml":
            # ML advanced search için basit fallback
            ml_request = SearchRequest(query=request.query, limit=request.limit, mode="ml")
            return await search_products(ml_request)
        
        filtered_df = df
        
        # Kategori filtreleri
        if request.category_level1:
            filtered_df = filtered_df.filter(
                pl.col("level1_category_name") == request.category_level1
            )
        
        # Multi-category filtering (OR logic)
        if request.category_level2_list and len(request.category_level2_list) > 0:
            filtered_df = filtered_df.filter(
                pl.col("level2_category_name").is_in(request.category_level2_list)
            )
        elif request.category_level2:
            filtered_df = filtered_df.filter(
                pl.col("level2_category_name") == request.category_level2
            )
        
        if request.category_leaf:
            filtered_df = filtered_df.filter(
                pl.col("leaf_category_name").str.to_lowercase().str.contains(request.category_leaf.lower())
            )
        
        # Fiyat filtreleri
        if request.min_price is not None:
            filtered_df = filtered_df.filter(pl.col("selling_price") >= request.min_price)
        
        if request.max_price is not None:
            filtered_df = filtered_df.filter(pl.col("selling_price") <= request.max_price)
        
        # Rating filtreleri
        if request.min_rating is not None:
            filtered_df = filtered_df.filter(
                pl.col("content_rate_avg").fill_null(0) >= request.min_rating
            )
        
        if request.min_review_count is not None:
            filtered_df = filtered_df.filter(
                pl.col("content_review_count") >= request.min_review_count
            )
        
        # Text arama
        if request.query.strip():
            query_lower = request.query.lower()
            filtered_df = filtered_df.filter(
                pl.col("content_title").str.to_lowercase().str.contains(query_lower) |
                pl.col("level1_category_name").str.to_lowercase().str.contains(query_lower) |
                pl.col("level2_category_name").str.to_lowercase().str.contains(query_lower) |
                pl.col("leaf_category_name").str.to_lowercase().str.contains(query_lower)
            )
        
        # Sıralama ve limit
        if len(filtered_df) > 0:
            sorted_results = filtered_df.sort([
                pl.col("content_rate_avg").fill_null(0),
                pl.col("content_review_count")
            ], descending=[True, True]).head(request.limit)
            results = sorted_results.to_dicts()
        else:
            results = []
        
        # Response formatla
        products = []
        for product in results:
            title = product.get('content_title', 'Ürün')
            if title == 'Lorem Ipsum':
                title = f"{product.get('level2_category_name', 'Ürün')} - {product.get('leaf_category_name', 'Detay')}"
            
            original = product.get('original_price', 0)
            selling = product.get('selling_price', 0)
            discount_pct = None
            if original > selling and original > 0:
                discount_pct = round(((original - selling) / original) * 100, 1)
            
            products.append(ProductResponse(
                content_id_hashed=product.get('content_id_hashed', ''),
                content_title=title,
                image_url=product.get('image_url', ''),
                level1_category_name=product.get('level1_category_name', ''),
                level2_category_name=product.get('level2_category_name', ''),
                leaf_category_name=product.get('leaf_category_name', ''),
                merchant_count=product.get('merchant_count'),
                original_price=product.get('original_price', 0.0),
                selling_price=product.get('selling_price', 0.0),
                discounted_price=product.get('discounted_price', 0.0),
                content_review_count=int(product.get('content_review_count', 0)),
                content_rate_count=int(product.get('content_rate_count', 0)),
                content_rate_avg=product.get('content_rate_avg'),
                discount_percentage=discount_pct
            ))
        
        return SearchResponse(
            query=request.query or "advanced_search",
            total_results=len(products),
            products=products,
            mode=mode
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Advanced search error: {str(e)}")

@app.get("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(q: str = Query(..., min_length=2, description="Search query for autocomplete")):
    """Autocomplete suggestions endpoint"""
    try:
        if len(q.strip()) < 2:
            return AutocompleteResponse(suggestions=[], total=0)
        
        # Get suggestions from Elasticsearch
        suggestions = get_autocomplete_suggestions(q.strip(), limit=8)
        
        # Fallback to database search if Elasticsearch is not available
        if not suggestions and df is not None:
            query_lower = q.lower().strip()
            
            # Get product titles
            title_matches = df.filter(
                pl.col("content_title").str.to_lowercase().str.contains(query_lower)
            ).select("content_title", "level2_category_name").head(5)
            
            # Get category matches
            category_matches = df.filter(
                pl.col("level2_category_name").str.to_lowercase().str.contains(query_lower)
            ).select("level2_category_name").unique().head(3)
            
            suggestions = []
            
            # Add product suggestions
            for row in title_matches.to_dicts():
                title = row.get('content_title', '').strip()
                if title and title != 'Lorem Ipsum':
                    suggestions.append({
                        "text": title,
                        "type": "product",
                        "category": row.get('level2_category_name', '')
                    })
            
            # Add category suggestions
            for row in category_matches.to_dicts():
                cat = row.get('level2_category_name', '').strip()
                if cat:
                    suggestions.append({
                        "text": cat,
                        "type": "category",
                        "category": cat
                    })
        
        return AutocompleteResponse(
            suggestions=suggestions,
            total=len(suggestions)
        )
        
    except Exception as e:
        log_with_timestamp(f"Autocomplete error: {e}", "ERROR")
        return AutocompleteResponse(suggestions=[], total=0)

@app.post("/refresh")
async def refresh_data():
    """Veriyi yeniden yükle"""
    load_data()
    if df is not None:
        return {"message": "Data refreshed successfully", "total_products": len(df)}
    else:
        raise HTTPException(status_code=500, detail="Failed to refresh data")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)