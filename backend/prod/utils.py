import re
import unicodedata
import numpy as np
from datetime import datetime

def log_with_timestamp(message, level="INFO"):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = "INFO" if level == "INFO" else "WARN" if level == "WARN" else "ERROR"
    print(f"[{timestamp}] {prefix}: {message}")

def norm_query(s: str) -> str:
    """Normalize query for TF-IDF search"""
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s.lower().strip())
    s = re.sub(r"[_/\-\\]", " ", s)
    s = re.sub(r"[^0-9a-zçğıöşü\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def norm_text(s: str) -> str:
    """Normalize text for SBERT"""
    if not isinstance(s, str): 
        return ""
    s = unicodedata.normalize("NFKD", s.lower().strip())
    s = re.sub(r"[_\-/]", " ", s)
    s = re.sub(r"[^0-9a-zçğıöşü\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def minmax(a):
    """Min-max normalization"""
    a = np.asarray(a, dtype=np.float32)
    if a.size == 0:
        return a
    mn, mx = float(np.min(a)), float(np.max(a))
    return (a - mn) / (mx - mn + 1e-12) if mx > mn else np.zeros_like(a, dtype=np.float32)