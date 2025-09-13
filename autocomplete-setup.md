# Elasticsearch Autocomplete Setup (Backend)

## Kurulum Adımları

### 1. Elasticsearch Docker Kurulumu
```bash
# Elasticsearch başlat
docker run -d \
  --name trendyol-elasticsearch \
  -p 9200:9200 \
  -p 9300:9300 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
  docker.elastic.co/elasticsearch/elasticsearch:8.11.0

# Elasticsearch durumu kontrol et
curl http://localhost:9200
```

### 2. Backend Bağımlılıkları
```bash
cd backend
pip install elasticsearch==8.11.0
```

### 3. Backend Başlat
```bash
cd backend
python merged_backend.py
```

## Backend Autocomplete Nasıl Çalışır

### Elasticsearch Configuration
- **Index**: `trendyol_products`
- **Edge N-gram Analyzer**: 2-10 karakter arası kısmi eşleşmeler
- **Fallback**: Elasticsearch yoksa Polars ile arama
- **Endpoint**: `GET /autocomplete?q=query`

### Veri İndexleme
Backend başlatıldığında otomatik olarak:
1. Polars'dan 10,000 ürün sample alınır
2. Ürün adları ve kategoriler Elasticsearch'e indexlenir
3. Edge N-gram analyzer ile autocomplete için optimize edilir

### API Response Format
```json
{
  "suggestions": [
    {
      "text": "Samsung Galaxy S21",
      "type": "product",
      "category": "Elektronik"
    },
    {
      "text": "Giyim",
      "type": "category", 
      "category": "Giyim"
    }
  ],
  "total": 2
}
```

## Test Senaryoları

### API Test Komutları
```bash
# Elasticsearch durumu
curl "http://localhost:9200/trendyol_products/_count"

# Sample autocomplete
curl "http://localhost:8000/autocomplete?q=sam"
curl "http://localhost:8000/autocomplete?q=giy"
curl "http://localhost:8000/autocomplete?q=iph"
curl "http://localhost:8000/autocomplete?q=el"
```

### Manuel Veri Yenileme
```bash
# Veri yeniden indexle
curl -X POST "http://localhost:8000/refresh"
```

## Backend Özellikler
- ✅ Elasticsearch ile hızlı autocomplete
- ✅ Edge N-gram tokenizer (kısmi eşleşme)
- ✅ Product/Category ayrımı
- ✅ Popularity-based sorting
- ✅ Polars fallback (ES yoksa)
- ✅ Bulk indexing (performance)