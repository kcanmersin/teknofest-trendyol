from pydantic import BaseModel
from typing import List, Dict, Optional

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