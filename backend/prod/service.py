import polars as pl
import random
from typing import List, Dict, Optional
from .config import FE_PATH, log_with_timestamp
from .ai_model import ml_search, hybrid_semantic_search

# ===== DB DATA LOADING =====
df = None

def load_data():
    """Load database data"""
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

def db_search(query: str, limit: int = 50) -> List[Dict]:
    """Perform database-based search using Polars filtering"""
    if df is None:
        return []

    # Simple category filtering
    if query.lower().strip():
        query_lower = query.lower()

        # Search in categories and title
        filtered = df.filter(
            pl.col("content_title").str.to_lowercase().str.contains(query_lower) |
            pl.col("level1_category_name").str.to_lowercase().str.contains(query_lower) |
            pl.col("level2_category_name").str.to_lowercase().str.contains(query_lower) |
            pl.col("leaf_category_name").str.to_lowercase().str.contains(query_lower)
        )

        if len(filtered) > 0:
            # Sort by rating
            sample_size = min(limit * 2, len(filtered))
            sampled = filtered.sample(sample_size) if len(filtered) > sample_size else filtered
            sorted_results = sampled.sort([
                pl.col("content_rate_avg").fill_null(0),
                pl.col("content_review_count")
            ], descending=[True, True])
            return sorted_results.head(limit).to_dicts()

    # Return random products
    return df.sample(min(limit, len(df))).to_dicts()

def advanced_db_search(query: str = "", category_level1: Optional[str] = None,
                      category_level2: Optional[str] = None,
                      category_level2_list: Optional[List[str]] = None,
                      category_leaf: Optional[str] = None,
                      min_price: Optional[float] = None,
                      max_price: Optional[float] = None,
                      min_rating: Optional[float] = None,
                      min_review_count: Optional[int] = None,
                      limit: int = 50) -> List[Dict]:
    """Perform advanced database search with filters"""
    if df is None:
        return []

    filtered_df = df

    # Category filters
    if category_level1:
        filtered_df = filtered_df.filter(
            pl.col("level1_category_name") == category_level1
        )

    # Multi-category filtering (OR logic)
    if category_level2_list and len(category_level2_list) > 0:
        filtered_df = filtered_df.filter(
            pl.col("level2_category_name").is_in(category_level2_list)
        )
    elif category_level2:
        filtered_df = filtered_df.filter(
            pl.col("level2_category_name") == category_level2
        )

    if category_leaf:
        filtered_df = filtered_df.filter(
            pl.col("leaf_category_name").str.to_lowercase().str.contains(category_leaf.lower())
        )

    # Price filters
    if min_price is not None:
        filtered_df = filtered_df.filter(pl.col("selling_price") >= min_price)

    if max_price is not None:
        filtered_df = filtered_df.filter(pl.col("selling_price") <= max_price)

    # Rating filters
    if min_rating is not None:
        filtered_df = filtered_df.filter(
            pl.col("content_rate_avg").fill_null(0) >= min_rating
        )

    if min_review_count is not None:
        filtered_df = filtered_df.filter(
            pl.col("content_review_count") >= min_review_count
        )

    # Text search
    if query.strip():
        query_lower = query.lower()
        filtered_df = filtered_df.filter(
            pl.col("content_title").str.to_lowercase().str.contains(query_lower) |
            pl.col("level1_category_name").str.to_lowercase().str.contains(query_lower) |
            pl.col("level2_category_name").str.to_lowercase().str.contains(query_lower) |
            pl.col("leaf_category_name").str.to_lowercase().str.contains(query_lower)
        )

    # Sort and limit
    if len(filtered_df) > 0:
        sorted_results = filtered_df.sort([
            pl.col("content_rate_avg").fill_null(0),
            pl.col("content_review_count")
        ], descending=[True, True]).head(limit)
        results = sorted_results.to_dicts()
    else:
        results = []

    return results

def get_categories():
    """Get all categories and their counts"""
    if df is None:
        return None

    try:
        # Level1 categories
        level1_stats = df.group_by("level1_category_name").agg([
            pl.len().alias("product_count")
        ]).sort("product_count", descending=True)

        # Level2 categories
        level2_stats = df.group_by(["level1_category_name", "level2_category_name"]).agg([
            pl.len().alias("product_count")
        ]).sort("product_count", descending=True)

        # Leaf categories
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
        return None

def get_grouped_categories():
    """Get optimized grouped categories for frontend sidebar"""
    if df is None:
        return None

    try:
        # Group Level2 categories
        level2_stats = df.group_by(["level1_category_name", "level2_category_name"]).agg([
            pl.len().alias("product_count")
        ]).sort("product_count", descending=True)

        # Category groups
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

            # Take top 15 most popular categories
            subcategories = sorted(subcategories, key=lambda x: x["count"], reverse=True)[:15]

            if subcategories:  # Don't include empty groups
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
        return None

def get_popular_categories(limit: int = 10):
    """Get most popular categories"""
    if df is None:
        return None

    try:
        # Popular Level2 categories
        popular = df.group_by("level2_category_name").agg([
            pl.len().alias("product_count"),
            pl.mean("content_rate_avg").alias("avg_rating"),
            pl.mean("original_price").alias("avg_price")
        ]).filter(
            pl.col("product_count") > 100  # Categories with at least 100 products
        ).sort("product_count", descending=True).head(limit)

        return {
            "popular_categories": popular.to_dicts(),
            "total_categories": len(df.select("level2_category_name").unique())
        }
    except Exception as e:
        return None

def get_fallback_autocomplete_suggestions(query: str, limit: int = 8) -> List[Dict]:
    """Get autocomplete suggestions from database fallback"""
    if df is None or not query or len(query) < 2:
        return []

    try:
        query_lower = query.lower().strip()

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

        return suggestions[:limit]

    except Exception as e:
        return []

def get_database():
    """Get database dataframe"""
    return df