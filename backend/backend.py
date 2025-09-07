from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import polars as pl
import random
from typing import List, Dict, Optional

app = FastAPI(title="Trendyol Search API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # False yap
    allow_methods=["*"],
    allow_headers=["*"],
)
# Request/Response models
class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 50

class ProductResponse(BaseModel):
    content_id_hashed: str
    content_title: str
    image_url: str
    level1_category_name: str
    level2_category_name: str
    leaf_category_name: str
    merchant_count: Optional[float]
    original_price: float
    selling_price: float
    discounted_price: float
    content_review_count: int
    content_rate_count: int
    content_rate_avg: Optional[float]
    discount_percentage: Optional[float] = None

class SearchResponse(BaseModel):
    query: str
    total_results: int
    products: List[ProductResponse]

# Global data storage
df = None

def load_data():
    """Veri yükleme fonksiyonu"""
    global df
    try:
        df = pl.read_parquet('trendyol-teknofest-hackathon/hackathon_2nd_phase_data/frontend_data.parquet')
        print(f"Data loaded: {len(df)} products")
    except Exception as e:
        print(f"Error loading data: {e}")
        df = None

def search_products_placeholder(query: str, limit: int = 50) -> List[Dict]:
    """
    Placeholder arama fonksiyonu - gerçek model yerine rastgele sonuç döner
    """
    if df is None:
        return []
    
    # Basit kategori filtresi (gerçek model yerine)
    if query.lower().strip():
        query_lower = query.lower()
        
        # Kategorilerde arama yap
        filtered = df.filter(
            pl.col("level1_category_name").str.to_lowercase().str.contains(query_lower) |
            pl.col("level2_category_name").str.to_lowercase().str.contains(query_lower) |
            pl.col("leaf_category_name").str.to_lowercase().str.contains(query_lower)
        )
        
        if len(filtered) > 0:
            # Rastgele seç ve rating'e göre sırala
            sample_size = min(limit * 2, len(filtered))
            sampled = filtered.sample(sample_size)
            sorted_results = sampled.sort([
                pl.col("content_rate_avg").fill_null(0),
                pl.col("content_review_count")
            ], descending=[True, True])
            return sorted_results.head(limit).to_dicts()
    
    # Rastgele ürünler döndür
    return df.sample(min(limit, len(df))).to_dicts()

@app.on_event("startup")
async def startup_event():
    """Uygulama başlangıcında veri yükle"""
    load_data()

@app.get("/")
async def root():
    return {"message": "Trendyol Search API", "status": "active"}

@app.post("/search", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    try:
        results = search_products_placeholder(request.query, request.limit)
        
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
        
        return SearchResponse(
            query=request.query,
            total_results=len(products),
            products=products
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.get("/columns")
async def get_columns():
    """Mevcut tüm kolonları ve örnek veriyi göster"""
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    sample = df.head(1).to_dicts()[0]
    return {
        "columns": df.columns,
        "total_rows": len(df),
        "sample_product": sample
    }
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

class AdvancedSearchRequest(BaseModel):
    query: str = ""
    category_level1: Optional[str] = None
    category_level2: Optional[str] = None
    category_level2_list: Optional[List[str]] = None  # Multi-category support
    category_leaf: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_rating: Optional[float] = None
    min_review_count: Optional[int] = None
    limit: int = 50

@app.post("/search/advanced", response_model=SearchResponse)
async def advanced_search(request: AdvancedSearchRequest):
    """Gelişmiş arama - kategori ve fiyat filtreleriyle"""
    print("🔥 ADVANCED SEARCH - VERSION 4 - MULTI-CATEGORY OR FILTERING")
    print(f"🎯 FILTER: category_level2 = '{request.category_level2}'")
    print(f"🎯 FILTER: category_level2_list = {request.category_level2_list}")
    
    if df is None:
        raise HTTPException(status_code=500, detail="Data not loaded")
    
    try:
        filtered_df = df
        
        # Kategori filtreleri
        if request.category_level1:
            filtered_df = filtered_df.filter(
                pl.col("level1_category_name") == request.category_level1
            )
        
        # Multi-category filtering (OR logic)
        if request.category_level2_list and len(request.category_level2_list) > 0:
            print(f"🎯 APPLYING MULTI-CATEGORY OR FILTER: level2_category_name IN {request.category_level2_list}")
            before_count = len(filtered_df)
            filtered_df = filtered_df.filter(
                pl.col("level2_category_name").is_in(request.category_level2_list)
            )
            after_count = len(filtered_df)
            print(f"📊 MULTI-FILTER RESULT: {before_count} → {after_count} products")
        elif request.category_level2:
            print(f"🎯 APPLYING EXACT MATCH FILTER: level2_category_name == '{request.category_level2}'")
            before_count = len(filtered_df)
            filtered_df = filtered_df.filter(
                pl.col("level2_category_name") == request.category_level2
            )
            after_count = len(filtered_df)
            print(f"📊 FILTER RESULT: {before_count} → {after_count} products")
        
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
            products=products
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Advanced search error: {str(e)}")

@app.post("/refresh")
async def refresh_data():
    """Veriyi yeniden yükle (rehber gereksinimi)"""
    load_data()
    if df is not None:
        return {"message": "Data refreshed successfully", "total_products": len(df)}
    else:
        raise HTTPException(status_code=500, detail="Failed to refresh data")

if __name__ == "__main__":
    import uvicorn
    # backend.py'nin en altındaki satırı değiştir:
    # backend.py'de host'u değiştir:
    uvicorn.run(app, host="0.0.0.0", port=8000)