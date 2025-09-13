from elasticsearch import Elasticsearch
from typing import List, Dict

from .config import ELASTICSEARCH_URL, PRODUCTS_INDEX
from .ml_loader import df
from .utils import log_with_timestamp

es_client = None

def init_elasticsearch():
    """Initialize Elasticsearch client and create index"""
    global es_client
    try:
        es_client = Elasticsearch([ELASTICSEARCH_URL])
        
        if es_client.ping():
            log_with_timestamp("Elasticsearch connection successful")
            
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
        for cat in categories[:500]:
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