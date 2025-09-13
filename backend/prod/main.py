from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import traceback
import logging
from typing import List, Dict, Optional
from datetime import datetime

from config import log_with_timestamp
from ai_model import (
    load_all_models, ml_search, hybrid_semantic_search,
    vec, X_corpus, m_click, m_order, fe, sbert_model, faiss_index,
    sbert_ids, reranker, sbert_embs, RERANKER_MODE,
    TOPK_RECALL_DEFAULT, TOPK_RETURN_DEFAULT
)
from service import (
    load_data, db_search, advanced_db_search, get_categories,
    get_grouped_categories, get_popular_categories,
    get_fallback_autocomplete_suggestions, get_database
)
from elastic_search import init_elasticsearch, get_autocomplete_suggestions, index_product_data

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

# ===== PYDANTIC MODELS =====
class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 50
    mode: Optional[str] = "db"  # "ml", "db", or "hybrid"

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
    mode: Optional[str] = "db"  # "ml", "db", or "hybrid"

class AutocompleteResponse(BaseModel):
    suggestions: List[Dict[str, str]]
    total: int

def format_product_response(product: Dict, mode: str) -> ProductResponse:
    """Format product data to ProductResponse"""
    title = product.get('content_title', 'Ürün')
    if title == 'Lorem Ipsum':
        title = f"{product.get('level2_category_name', 'Ürün')} - {product.get('leaf_category_name', 'Detay')}"

    # Calculate discount percentage
    original = product.get('original_price', 0)
    selling = product.get('selling_price', 0)
    discount_pct = None
    if original and selling and original > selling and original > 0:
        discount_pct = round(((original - selling) / original) * 100, 1)

    return ProductResponse(
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
    )

# ===== API ENDPOINTS =====
@app.on_event("startup")
async def startup_event():
    """Load data and models on application startup"""
    log_with_timestamp("STARTING TRENDYOL UNIFIED SEARCH API")
    log_with_timestamp("=" * 60)
    log_with_timestamp("Loading application data...")

    # Load database
    load_data()

    # Load AI models
    load_all_models()

    # Initialize Elasticsearch
    log_with_timestamp("Initializing Elasticsearch for autocomplete...")
    init_elasticsearch()

    # Index product data in Elasticsearch
    df = get_database()
    if df is not None:
        index_product_data(df)

    # Status check
    ml_ready = (vec is not None and X_corpus is not None and
                m_click is not None and m_order is not None and fe is not None)
    db_ready = get_database() is not None
    # Reranker olmasa da çalışabilir, sadece SBERT kullanır
    hybrid_ready = (sbert_model is not None and faiss_index is not None and
                   sbert_ids is not None and fe is not None)

    log_with_timestamp("SYSTEM STATUS:")
    log_with_timestamp(f"   ML Engine: {'READY' if ml_ready else 'NOT READY'}")
    log_with_timestamp(f"   DB Engine: {'READY' if db_ready else 'NOT READY'}")
    log_with_timestamp(f"   Hybrid Semantic Engine: {'READY' if hybrid_ready else 'NOT READY'}")

    if ml_ready:
        log_with_timestamp(f"   ML Corpus Size: {X_corpus.shape[0]} products")
        log_with_timestamp(f"   Vocabulary Size: {len(vec.vocabulary_)} terms")

    if db_ready:
        df = get_database()
        log_with_timestamp(f"   DB Size: {len(df)} products")
        unique_categories = df.select("level2_category_name").n_unique()
        log_with_timestamp(f"     Categories: {unique_categories} unique")

    if hybrid_ready:
        log_with_timestamp(f"   SBERT Embeddings: {sbert_embs.shape[0]} products")
        log_with_timestamp(f"   FAISS Index Size: {faiss_index.ntotal}")
        log_with_timestamp(f"   Reranker Mode: {RERANKER_MODE}")

    log_with_timestamp("Available endpoints:")
    log_with_timestamp("   • POST /search (supports mode='ml'=Semantic, 'db'=Database, 'hybrid'=Enhanced)")
    log_with_timestamp("   • GET /autocomplete")
    log_with_timestamp("   • GET /healthz")
    log_with_timestamp("   • GET /categories")
    log_with_timestamp("=" * 60)
    log_with_timestamp("APPLICATION READY FOR REQUESTS")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Trendyol Unified Search API", "status": "active", "modes": ["ml", "db", "hybrid"]}

@app.get("/healthz")
def healthz():
    """Health check endpoint"""
    df = get_database()
    return JSONResponse({
        "status": "ok",
        "db_rows": int(df.height) if df is not None else 0,
        "ml_fe_rows": int(fe.height) if fe is not None else 0,
        "has_click_model": m_click is not None,
        "has_order_model": m_order is not None,
        "has_tfidf": (vec is not None and X_corpus is not None),
        "has_sbert": sbert_model is not None,
        "has_faiss": faiss_index is not None,
        "has_reranker": reranker is not None,
        "reranker_mode": RERANKER_MODE,
        "sbert_embeddings": int(sbert_embs.shape[0]) if sbert_embs is not None else 0
    })

@app.post("/search", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    """Main search endpoint"""
    try:
        mode = request.mode or "db"

        log_with_timestamp("=" * 60)
        log_with_timestamp(f"NEW SEARCH REQUEST")
        log_with_timestamp(f"Query: '{request.query}'")
        log_with_timestamp(f"Mode: {mode.upper()}")
        log_with_timestamp(f"Limit: {request.limit}")
        log_with_timestamp("=" * 60)

        if mode == "ml":
            log_with_timestamp("USING SEMANTIC SEARCH ENGINE (SBERT + Reranker)")
            # Semantic ML search - prioritize hybrid semantic search
            if (sbert_model is not None and faiss_index is not None and
                sbert_ids is not None and fe is not None):
                log_with_timestamp("Running Semantic Search (SBERT + Advanced Reranker)...")
                recall_k = max(request.limit*8, TOPK_RECALL_DEFAULT)
                res_df = hybrid_semantic_search(request.query, recall_k=recall_k, return_k=request.limit)
                results = res_df.to_pandas().to_dict(orient="records")
                log_with_timestamp(f"Semantic Search completed: {len(results)} products found")

            elif vec is not None and X_corpus is not None and m_click is not None and m_order is not None and fe is not None:
                log_with_timestamp("Semantic search unavailable, falling back to TF-IDF + CatBoost...")
                topk_retrieval = max(request.limit*4, 100)
                res_df = ml_search(request.query, topk_retrieval=topk_retrieval, topk_final=request.limit)
                results = res_df.to_pandas().to_dict(orient="records")
                log_with_timestamp(f"TF-IDF Search completed: {len(results)} products found")

            else:
                log_with_timestamp("No ML models available!", "ERROR")
                raise HTTPException(status_code=500, detail="ML models not loaded")

            if results:
                avg_score = sum(r.get('score', 0) for r in results) / len(results)
                log_with_timestamp(f"Average Semantic Score: {avg_score:.4f}")

            products = [format_product_response(product, mode) for product in results]

        elif mode == "hybrid":
            log_with_timestamp("USING ENHANCED SEMANTIC SEARCH ENGINE")
            # Enhanced semantic search with full context
            if (sbert_model is None or faiss_index is None or
                sbert_ids is None or fe is None):
                log_with_timestamp("Enhanced semantic search models not available!", "ERROR")
                raise HTTPException(status_code=500, detail="Enhanced semantic search models not loaded")

            log_with_timestamp("Running Enhanced SBERT + Advanced Reranker pipeline...")
            recall_k = max(request.limit*10, TOPK_RECALL_DEFAULT)  # More candidates for better quality
            res_df = hybrid_semantic_search(request.query, recall_k=recall_k, return_k=request.limit)
            results = res_df.to_pandas().to_dict(orient="records")

            log_with_timestamp(f"Enhanced Semantic Search completed: {len(results)} products found")
            if results:
                avg_score = sum(r.get('score', 0) for r in results) / len(results)
                log_with_timestamp(f"Average Enhanced Semantic Score: {avg_score:.4f}")

            products = [format_product_response(product, mode) for product in results]

        else:
            log_with_timestamp("USING DATABASE SEARCH ENGINE")
            # DB-based search
            df = get_database()
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

            products = [format_product_response(product, mode) for product in results]

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
def search_get(q: str = Query(..., description="Search query"),
               topk: int = Query(50, ge=1, le=200),
               mode: str = Query("ml", description="Search mode: ml, db, or hybrid")):
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
async def get_categories_endpoint():
    """Get all categories and their counts"""
    df = get_database()
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")

    try:
        result = get_categories()
        if result is None:
            raise HTTPException(status_code=500, detail="Failed to get categories")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Categories error: {str(e)}")

@app.get("/categories/grouped")
async def get_grouped_categories_endpoint():
    """Get optimized grouped categories for frontend sidebar"""
    df = get_database()
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")

    try:
        result = get_grouped_categories()
        if result is None:
            raise HTTPException(status_code=500, detail="Failed to get grouped categories")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Grouped categories error: {str(e)}")

@app.get("/popular-categories")
async def get_popular_categories_endpoint(limit: int = 10):
    """Get most popular categories"""
    df = get_database()
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")

    try:
        result = get_popular_categories(limit)
        if result is None:
            raise HTTPException(status_code=500, detail="Failed to get popular categories")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Popular categories error: {str(e)}")

@app.post("/search/advanced", response_model=SearchResponse)
async def advanced_search(request: AdvancedSearchRequest):
    """Advanced search with category and price filters"""
    df = get_database()
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")

    try:
        mode = request.mode or "db"

        # Only DB mode is supported for advanced search for now
        if mode == "ml":
            # ML advanced search simple fallback
            ml_request = SearchRequest(query=request.query, limit=request.limit, mode="ml")
            return await search_products(ml_request)

        results = advanced_db_search(
            query=request.query,
            category_level1=request.category_level1,
            category_level2=request.category_level2,
            category_level2_list=request.category_level2_list,
            category_leaf=request.category_leaf,
            min_price=request.min_price,
            max_price=request.max_price,
            min_rating=request.min_rating,
            min_review_count=request.min_review_count,
            limit=request.limit
        )

        products = [format_product_response(product, mode) for product in results]

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
        if not suggestions:
            suggestions = get_fallback_autocomplete_suggestions(q.strip(), limit=8)

        return AutocompleteResponse(
            suggestions=suggestions,
            total=len(suggestions)
        )

    except Exception as e:
        log_with_timestamp(f"Autocomplete error: {e}", "ERROR")
        return AutocompleteResponse(suggestions=[], total=0)

@app.post("/refresh")
async def refresh_data():
    """Refresh data"""
    load_data()
    df = get_database()
    if df is not None:
        return {"message": "Data refreshed successfully", "total_products": len(df)}
    else:
        raise HTTPException(status_code=500, detail="Failed to refresh data")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)