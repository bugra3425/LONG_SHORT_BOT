"""
🧠 Redis Bağlantı Yönetimi
Pozisyonlar, istatistikler ve sinyallerin kalıcı depolanması için
"""
import redis.asyncio as redis
import json
import logging
from .config import REDIS_URL

logger = logging.getLogger("redis")

class RedisClient:
    def __init__(self):
        self.url = REDIS_URL
        self._redis = None

    async def connect(self):
        """Redis bağlantısını başlat"""
        if not self._redis:
            try:
                self._redis = redis.from_url(self.url, decode_responses=True)
                await self._redis.ping()
                logger.info("🔌 Redis bağlantısı başarılı.")
            except Exception as e:
                logger.error(f"❌ Redis bağlantı hatası: {e}")
                self._redis = None

    async def close(self):
        """Bağlantıyı kapat"""
        if self._redis:
            await self._redis.aclose()
            self._redis = None

    async def get(self, key: str):
        """Veri çek"""
        if not self._redis: await self.connect()
        try:
            val = await self._redis.get(key)
            return json.loads(val) if val else None
        except Exception as e:
            logger.error(f"Redis GET hatası ({key}): {e}")
            return None

    async def set(self, key: str, value: any, expire: int = None):
        """Veri kaydet"""
        if not self._redis: await self.connect()
        try:
            await self._redis.set(key, json.dumps(value), ex=expire)
        except Exception as e:
            logger.error(f"Redis SET hatası ({key}): {e}")

    async def hset(self, key: str, field: str, value: any):
        """Hash set"""
        if not self._redis: await self.connect()
        try:
            await self._redis.hset(key, field, json.dumps(value))
        except Exception as e:
            logger.error(f"Redis HSET hatası ({key}:{field}): {e}")

    async def hgetall(self, key: str):
        """Hash get all"""
        if not self._redis: await self.connect()
        try:
            data = await self._redis.hgetall(key)
            return {k: json.loads(v) for k, v in data.items()}
        except Exception as e:
            logger.error(f"Redis HGETALL hatası ({key}): {e}")
            return {}

    async def hdel(self, key: str, field: str):
        """Hash delete field"""
        if not self._redis: await self.connect()
        try:
            await self._redis.hdel(key, field)
        except Exception as e:
            logger.error(f"Redis HDEL hatası ({key}:{field}): {e}")

    async def delete(self, key: str):
        """Key sil"""
        if not self._redis: await self.connect()
        try:
            await self._redis.delete(key)
        except Exception as e:
            logger.error(f"Redis DELETE hatası ({key}): {e}")

# Singleton instance
redis_client = RedisClient()
