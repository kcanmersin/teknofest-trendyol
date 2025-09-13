import os

# Model paths
ARTIF_DIR = os.path.expanduser("~/.cache/trendyol/artifacts_enes")
MODEL_DIR = os.path.expanduser("~/models")
FE_PATH = "../trendyol-teknofest-hackathon/hackathon_2nd_phase_data/frontend_data.parquet"

# Elasticsearch config
ELASTICSEARCH_URL = "http://localhost:9200"
PRODUCTS_INDEX = "trendyol_products"

# Hybrid semantic search config
RERANKER_MODE = os.environ.get("RERANKER_MODE", "crossencoder").lower()
TOPK_RECALL_DEFAULT = 400
TOPK_RETURN_DEFAULT = 50