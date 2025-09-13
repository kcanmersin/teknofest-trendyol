import os
from datetime import datetime
import logging

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== ML MODEL PATHS =====
ARTIF_DIR = os.path.expanduser("~/.cache/trendyol/artifacts_enes")
MODEL_DIR = os.path.expanduser("~/models")
FE_PATH = "../trendyol-teknofest-hackathon/hackathon_2nd_phase_data/frontend_data.parquet"

# ===== HYBRID SEMANTIC SEARCH MODELS =====
RERANKER_MODE = os.environ.get("RERANKER_MODE", "crossencoder").lower()
TOPK_RECALL_DEFAULT = 400
TOPK_RETURN_DEFAULT = 50

# ===== ELASTICSEARCH SETUP =====
ELASTICSEARCH_URL = "http://localhost:9200"
PRODUCTS_INDEX = "trendyol_products"

def log_with_timestamp(message, level="INFO"):
    """Log messages with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = "INFO" if level == "INFO" else "WARN" if level == "WARN" else "ERROR"
    print(f"[{timestamp}] {prefix}: {message}")