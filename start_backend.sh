#!/bin/bash

echo "Starting Trendyol Backend Server..."
echo "======================================"

# Conda environment'ı aktifleştir
echo "Activating conda environment: trendyol-enes"
source ~/anaconda3/etc/profile.d/conda.sh
conda activate trendyol-enes

# Backend dizinine geç
echo "Navigating to backend/prod directory"
cd backend/prod

# Python server'ı başlat
echo "Starting FastAPI server..."
python main.py