import polars as pl
from typing import List, Dict

from .ml_loader import df

def db_search(query: str, limit: int = 50) -> List[Dict]:
    """Database search using Polars filtering"""
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