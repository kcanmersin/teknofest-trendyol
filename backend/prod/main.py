from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
import logging
from typing import List, Dict

from .models import SearchRequest, SearchResponse, ProductResponse, AdvancedSearchRequest, AutocompleteResponse
from .ml_loader import load_all_models, df, fe, vec, X_corpus, m_click, m_order, sbert_model, faiss_index, sbert_ids, reranker, sbert_embs
from .ml_search import ml_search
from .hybrid_search import hybrid_semantic_search
from .db_search import db_search
from .elasticsearch_service import init_elasticsearch, get_autocomplete_suggestions, es_client
from .config import PRODUCTS_INDEX, RERANKER_MODE, TOPK_RECALL_DEFAULT
from .utils import log_with_timestamp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Trendyol Unified Search API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize application and load models"""
    log_with_timestamp("STARTING TRENDYOL UNIFIED SEARCH API")
    log_with_timestamp("=" * 60)
    log_with_timestamp("Loading application data...")
    load_all_models()
    
    log_with_timestamp("Initializing Elasticsearch for autocomplete...")
    init_elasticsearch()
    
    ml_ready = (vec is not None and X_corpus is not None and 
                m_click is not None and m_order is not None and fe is not None)
    db_ready = df is not None
    es_ready = es_client is not None
    hybrid_ready = (sbert_model is not None and faiss_index is not None and 
                   sbert_ids is not None and reranker is not None and fe is not None)
    
    log_with_timestamp("SYSTEM STATUS:")
    log_with_timestamp(f"   ML Engine: {'READY' if ml_ready else 'NOT READY'}")
    log_with_timestamp(f"   DB Engine: {'READY' if db_ready else 'NOT READY'}")
    log_with_timestamp(f"   Hybrid Semantic Engine: {'READY' if hybrid_ready else 'NOT READY'}")
    log_with_timestamp(f"   Elasticsearch: {'READY' if es_ready else 'NOT READY'}")
    
    if ml_ready:
        log_with_timestamp(f"   ML Corpus Size: {X_corpus.shape[0]} products")
        log_with_timestamp(f"   Vocabulary Size: {len(vec.vocabulary_)} terms")
    
    if db_ready:
        log_with_timestamp(f"   DB Size: {len(df)} products")
        unique_categories = df.select("level2_category_name").n_unique()
        log_with_timestamp(f"     Categories: {unique_categories} unique")
    
    if hybrid_ready:
        log_with_timestamp(f"   SBERT Embeddings: {sbert_embs.shape[0]} products")
        log_with_timestamp(f"   FAISS Index Size: {faiss_index.ntotal}")
        log_with_timestamp(f"   Reranker Mode: {RERANKER_MODE}")
    
    if es_ready:
        log_with_timestamp(f"   Elasticsearch Index: {PRODUCTS_INDEX}")
    
    log_with_timestamp("Available endpoints:")
    log_with_timestamp("   • POST /search (supports mode='ml', 'db', or 'hybrid')")
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
    """Main search endpoint supporting ml, db, and hybrid modes"""
    try:
        mode = request.mode or "db"
        
        log_with_timestamp("=" * 60)
        log_with_timestamp(f"NEW SEARCH REQUEST")
        log_with_timestamp(f"Query: '{request.query}'")
        log_with_timestamp(f"Mode: {mode.upper()}")
        log_with_timestamp(f"Limit: {request.limit}")
        log_with_timestamp("=" * 60)
        
        if mode == "ml":
            products = _handle_ml_search(request)
        elif mode == "hybrid":
            products = _handle_hybrid_search(request)
        else:
            products = _handle_db_search(request)
        
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

def _handle_ml_search(request: SearchRequest):
    """Handle ML-based search"""
    log_with_timestamp("USING MACHINE LEARNING SEARCH ENGINE")
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
    
    return _format_ml_products(results)

def _handle_hybrid_search(request: SearchRequest):
    """Handle hybrid semantic search"""
    log_with_timestamp("USING HYBRID SEMANTIC SEARCH ENGINE")
    if (sbert_model is None or faiss_index is None or 
        sbert_ids is None or reranker is None or fe is None):
        log_with_timestamp("Hybrid semantic search models not available!", "ERROR")
        raise HTTPException(status_code=500, detail="Hybrid semantic search models not loaded")
    
    log_with_timestamp("Running SBERT + Reranker pipeline...")
    recall_k = max(request.limit*8, TOPK_RECALL_DEFAULT)
    res_df = hybrid_semantic_search(request.query, recall_k=recall_k, return_k=request.limit)
    results = res_df.to_pandas().to_dict(orient="records")
    
    log_with_timestamp(f"Hybrid Search completed: {len(results)} products found")
    if results:
        avg_score = sum(r.get('score', 0) for r in results) / len(results)
        log_with_timestamp(f"Average Hybrid Score: {avg_score:.4f}")
    
    return _format_hybrid_products(results)

def _handle_db_search(request: SearchRequest):
    """Handle database search"""
    log_with_timestamp("USING DATABASE SEARCH ENGINE")
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
    
    return _format_db_products(results)

def _format_ml_products(results):
    """Format ML search results"""
    products = []
    for product in results:
        title = product.get('content_title', 'Ürün')
        if title == 'Lorem Ipsum':
            title = f"{product.get('level2_category_name', 'Ürün')} - {product.get('leaf_category_name', 'Detay')}"
        
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
    return products

def _format_hybrid_products(results):
    """Format hybrid search results"""
    products = []
    for product in results:
        title = product.get('content_title', 'Ürün')
        if title == 'Lorem Ipsum':
            title = f"Ürün"
        
        original = product.get('original_price', 0)
        selling = product.get('selling_price', 0)
        discount_pct = None
        if original and selling and original > selling and original > 0:
            discount_pct = round(((original - selling) / original) * 100, 1)
        
        products.append(ProductResponse(
            content_id_hashed=product.get('content_id_hashed', ''),
            content_title=title,
            image_url=product.get('image_url', ''),
            level1_category_name="",
            level2_category_name="",
            leaf_category_name="",
            merchant_count=None,
            original_price=0.0,
            selling_price=product.get('selling_price', 0.0),
            discounted_price=0.0,
            content_review_count=int(product.get('content_review_count', 0)),
            content_rate_count=0,
            content_rate_avg=product.get('content_rate_avg'),
            discount_percentage=discount_pct,
            score=product.get('score')
        ))
    return products

def _format_db_products(results):
    """Format database search results"""
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
    return products

@app.get("/search")
def search_get(q: str = Query(..., description="Arama sorgusu"),
               topk: int = Query(50, ge=1, le=200),
               mode: str = Query("ml", description="Search mode: ml, db, or hybrid")):
    """GET endpoint for search compatibility"""
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
    """Get all categories with product counts"""
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    try:
        level1_stats = df.group_by("level1_category_name").agg([
            pl.len().alias("product_count")
        ]).sort("product_count", descending=True)
        
        level2_stats = df.group_by(["level1_category_name", "level2_category_name"]).agg([
            pl.len().alias("product_count")
        ]).sort("product_count", descending=True)
        
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

@app.get("/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(q: str = Query(..., min_length=2, description="Search query for autocomplete")):
    """Autocomplete suggestions endpoint"""
    try:
        if len(q.strip()) < 2:
            return AutocompleteResponse(suggestions=[], total=0)
        
        suggestions = get_autocomplete_suggestions(q.strip(), limit=8)
        
        # Fallback to database search if Elasticsearch is not available
        if not suggestions and df is not None:
            suggestions = _get_db_autocomplete_suggestions(q)
        
        return AutocompleteResponse(
            suggestions=suggestions,
            total=len(suggestions)
        )
        
    except Exception as e:
        log_with_timestamp(f"Autocomplete error: {e}", "ERROR")
        return AutocompleteResponse(suggestions=[], total=0)

def _get_db_autocomplete_suggestions(query: str) -> List[Dict]:
    """Get autocomplete suggestions from database"""
    query_lower = query.lower().strip()
    
    title_matches = df.filter(
        pl.col("content_title").str.to_lowercase().str.contains(query_lower)
    ).select("content_title", "level2_category_name").head(5)
    
    category_matches = df.filter(
        pl.col("level2_category_name").str.to_lowercase().str.contains(query_lower)
    ).select("level2_category_name").unique().head(3)
    
    suggestions = []
    
    for row in title_matches.to_dicts():
        title = row.get('content_title', '').strip()
        if title and title != 'Lorem Ipsum':
            suggestions.append({
                "text": title,
                "type": "product",
                "category": row.get('level2_category_name', '')
            })
    
    for row in category_matches.to_dicts():
        cat = row.get('level2_category_name', '').strip()
        if cat:
            suggestions.append({
                "text": cat,
                "type": "category",
                "category": cat
            })
    
    return suggestions

@app.post("/refresh")
async def refresh_data():
    """Refresh data endpoint"""
    load_all_models()
    if df is not None:
        return {"message": "Data refreshed successfully", "total_products": len(df)}
    else:
        raise HTTPException(status_code=500, detail="Failed to refresh data")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)