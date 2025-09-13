#!/bin/bash

echo "🚀 Trendyol Elasticsearch Autocomplete Setup"
echo "============================================"

# Stop existing container if running
echo "📦 Stopping existing Elasticsearch container..."
docker stop trendyol-elasticsearch 2>/dev/null || true
docker rm trendyol-elasticsearch 2>/dev/null || true

# Start Elasticsearch
echo "🔧 Starting Elasticsearch..."
docker run -d \
  --name trendyol-elasticsearch \
  -p 9200:9200 \
  -p 9300:9300 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
  docker.elastic.co/elasticsearch/elasticsearch:8.11.0

# Wait for Elasticsearch to start
echo "⏳ Waiting for Elasticsearch to start..."
for i in {1..30}; do
    if curl -s http://localhost:9200 > /dev/null 2>&1; then
        echo "✅ Elasticsearch is ready!"
        break
    fi
    echo "   Waiting... ($i/30)"
    sleep 2
done

# Check if Elasticsearch is running
if ! curl -s http://localhost:9200 > /dev/null 2>&1; then
    echo "❌ Failed to start Elasticsearch"
    exit 1
fi

# Install Python dependency
echo "📦 Installing Python dependencies..."
cd backend
pip install elasticsearch==8.11.0

# Restart backend to initialize Elasticsearch
echo "🔄 Backend'i yeniden başlat (Ctrl+C ile durdur, sonra tekrar çalıştır)"
echo ""
echo "python merged_backend.py"
echo ""
echo "✅ Setup complete! Backend'i restart et ve test et:"
echo "   curl 'http://localhost:8000/autocomplete?q=sam'"