"""
📡 Bugra-Bot Monitoring API
Northflank üzerinde botun durumunu izlemek için
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from bot.redis_client import redis_client
from bot.config import LOG_LEVEL

app = FastAPI(title="Bugra-Bot API", version="2.2.0")

# --- Modeller ---
class PositionModel(BaseModel):
    symbol: str
    side: str
    entry_price: float
    amount: float
    margin: float
    pnl_pct: Optional[float] = 0
    opened_at: str

class StatsModel(BaseModel):
    balance: float
    open_positions: int
    daily_pnl: float
    wins: int
    losses: int
    last_update: str

# --- Endpoints ---

@app.get("/health")
async def health_check():
    """Northflank Health Check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/stats", response_model=StatsModel)
async def get_stats():
    """Genel bot istatistiklerini getir"""
    stats = await redis_client.get("bot:stats")
    if not stats:
        raise HTTPException(status_code=404, detail="Stats not found")
    return stats

@app.get("/positions", response_model=List[dict])
async def get_positions():
    """Aktif pozisyonları getir"""
    positions = await redis_client.hgetall("bot:positions")
    return list(positions.values())

@app.get("/candidates", response_model=List[dict])
async def get_candidates():
    """Scanner verilerini getir"""
    candidates = await redis_client.get("bot:candidates")
    return candidates or []

@app.post("/reset")
async def reset_stats():
    """İstatistikleri sıfırla (Gelişmiş kontrol için)"""
    await redis_client.delete("bot:stats")
    return {"status": "reset requested"}
