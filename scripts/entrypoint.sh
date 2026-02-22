#!/bin/bash
set -e
echo "🚀 Bugra-Bot All-in-One Mode başlatılıyor..."
echo "🧠 Redis Server başlatılıyor..."
redis-server --daemonize yes --protected-mode no
echo "📡 Monitoring API (Uvicorn) arka planda başlatılıyor..."
cd /app/src
uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} &
echo "🤖 Trading Worker başlatılıyor..."
exec python -m bot.main
