"""
==============================================================================
PUMP & DUMP REVERSION BOT — EXCHANGE CLIENT
Tarih : 18 Şubat 2026
Geliştirici: Buğra Türkoğlu
18.02.2026.py'den adapte edilmiştir - Async Binance Futures
==============================================================================
"""
import asyncio
import logging
import aiohttp
import ccxt.async_support as ccxt
from .config import Config

logger = logging.getLogger("exchange")


def make_binance_exchange(extra_opts: dict = None, demo: bool = None) -> ccxt.binance:
    """
    Binance Futures exchange örneği oluşturur.

    DNS fix: aiodns yerine sistemin DefaultResolver'ını kullanır (Türkiye DNS sorunu).

    demo=True  → Binance Demo Trading (demo.binance.com) — gerçek para yok.
                  Dokümana göre: sandbox/testnet DEGİL, enable_demo_trading(True) kullan.
    demo=False → Canlı Binance Futures (API key varsa geçerli işlem açar).
    """
    if demo is None:
        demo = Config.DEMO_MODE
    
    # DNS fix: once Google/Cloudflare DNS ile AsyncResolver dene,
    # basarisiz olursa ThreadedResolver kullan (aiodns bypass, stdlib socket kullanir).
    session = None
    try:
        resolver  = aiohttp.AsyncResolver(nameservers=["8.8.8.8", "1.1.1.1", "8.8.4.4"])
        connector = aiohttp.TCPConnector(resolver=resolver, limit=20, ttl_dns_cache=300)
        session   = aiohttp.ClientSession(connector=connector)
    except Exception:
        try:
            resolver  = aiohttp.resolver.ThreadedResolver()
            connector = aiohttp.TCPConnector(resolver=resolver, limit=20, ttl_dns_cache=300)
            session   = aiohttp.ClientSession(connector=connector)
        except Exception:
            session = None

    opts = {
        "enableRateLimit": True,
        "timeout": Config.TIMEOUT_MS,
        "options": {"defaultType": Config.DEFAULT_TYPE},
        "apiKey": Config.BINANCE_API_KEY,
        "secret": Config.BINANCE_API_SECRET,
    }
    if extra_opts:
        opts.update(extra_opts)

    ex = ccxt.binance(opts)

    if demo:
        # Doküman önerisi: enable_demo_trading(True) — tüm URL'leri otomatik demo-fapi.binance.com'a yönlendirir.
        # set_sandbox_mode(True) KULLANMA — eski testnet'e gider, hata alırsın.
        ex.enable_demo_trading(True)
        logger.info("🧪 Demo Trading modu aktif (demo-fapi.binance.com)")
    else:
        logger.warning("⚠️ CANLI TRADING modu aktif!")

    if session is not None:
        ex.session = session
    return ex


def get_digits(prec) -> int:
    """
    Precision değerinden ondalık basamak sayısını hesapla.
    Örn: 0.001 → 3,  0.0100 → 2,  1 → 0
    Doküman: precision_to_digits bazı durumlarda hatalı çalışıyor, manuel hesap daha güvenilir.
    """
    if prec is None:
        return 0
    s = format(float(prec), 'f')
    if '.' not in s:
        return 0
    return len(s.split('.')[-1].rstrip('0'))


class AsyncExchangeClient:
    """
    Async Binance Futures bağlantı katmanı
    18.02.2026.py stratejisiyle tam uyumlu
    """

    def __init__(self, demo: bool = None):
        self.exchange = make_binance_exchange(demo=demo)
        self._api_key = None  # Lazy load için
        
    async def load_api_keys(self):
        """API anahtarlarını dinamik yükle"""
        if self._api_key:
            return
        
        api_key = Config.BINANCE_API_KEY
        api_secret = Config.BINANCE_API_SECRET
        
        if api_key and api_secret:
            self.exchange.api_key = api_key
            self.exchange.secret = api_secret
            self._api_key = True
            logger.info("🔑 API anahtarları yüklendi")
        else:
            logger.warning("⚠️ API anahtarları bulunamadı (.env dosyasını kontrol edin)")

    async def _safe_call(self, coro_func, *args, retries: int = 3, **kwargs):
        """Güvenli API çağrısı - retry + rate-limit yönetimi"""
        for i in range(retries):
            try:
                return await coro_func(*args, **kwargs)
            except ccxt.RateLimitExceeded:
                wait_time = 2 ** i
                logger.warning(f"⚠️ Rate limit aşıldı. {wait_time}s bekleniyor...")
                await asyncio.sleep(wait_time)
            except (ccxt.NetworkError, ccxt.ExchangeNotAvailable) as e:
                if i < retries - 1:
                    wait_time = 2 ** i
                    logger.warning(f"🔌 Ağ hatası, {wait_time}s sonra tekrar: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"❌ Ağ hatası (son deneme): {e}")
                    raise
            except Exception as e:
                logger.error(f"❌ API hatası: {e}")
                if i < retries - 1:
                    await asyncio.sleep(1)
                else:
                    raise
        return None

    async def fetch_balance(self) -> dict:
        """Futures cüzdan bakiyesini döndür"""
        try:
            balance = await self._safe_call(self.exchange.fetch_balance)
            usdt = balance.get('USDT', {})
            return {
                'total': float(usdt.get('total', 0)),
                'free': float(usdt.get('free', 0)),
                'used': float(usdt.get('used', 0)),
            }
        except Exception as e:
            logger.debug(f"Bakiye alınamadı: {e}")
            return {'total': 0, 'free': 0, 'used': 0}

    async def fetch_positions(self) -> list:
        """Açık pozisyonları listele"""
        try:
            positions = await self._safe_call(self.exchange.fetch_positions)
            return [p for p in positions if float(p.get('contracts', 0)) > 0]
        except Exception as e:
            logger.error(f"❌ Pozisyonlar alınamadı: {e}")
            return []

    async def set_leverage(self, symbol: str, leverage: int = None):
        """Kaldıracı ayarla"""
        if leverage is None:
            leverage = Config.LEVERAGE
        try:
            await self._safe_call(self.exchange.set_leverage, leverage, symbol)
            logger.info(f"⚙️ {symbol} kaldıraç: {leverage}x")
        except Exception as e:
            logger.warning(f"⚠️ {symbol} kaldıraç ayarlanamadı: {e}")

    async def set_margin_mode(self, symbol: str, mode: str = "isolated"):
        """Marjin modunu ayarla (isolated/cross)"""
        try:
            await self._safe_call(self.exchange.set_margin_mode, mode, symbol)
        except Exception as e:
            # Zaten ayarlıysa hata verir, sorun değil
            pass

    async def open_short(self, symbol: str, amount: float) -> dict | None:
        """Short pozisyon aç"""
        try:
            await self.set_leverage(symbol)
            await self.set_margin_mode(symbol)
            order = await self._safe_call(
                self.exchange.create_market_sell_order,
                symbol, amount, params={'reduceOnly': False}
            )
            logger.info(f"📉 SHORT açıldı: {symbol} | Miktar: {amount}")
            return order
        except Exception as e:
            logger.error(f"❌ SHORT açılamadı {symbol}: {e}")
            return None

    async def open_long(self, symbol: str, amount: float) -> dict | None:
        """Long pozisyon aç"""
        try:
            await self.set_leverage(symbol)
            await self.set_margin_mode(symbol)
            order = await self._safe_call(
                self.exchange.create_market_buy_order,
                symbol, amount, params={'reduceOnly': False}
            )
            logger.info(f"📈 LONG açıldı: {symbol} | Miktar: {amount}")
            return order
        except Exception as e:
            logger.error(f"❌ LONG açılamadı {symbol}: {e}")
            return None

    async def close_position(self, symbol: str, side: str, amount: float) -> dict | None:
        """Pozisyonu kapat (kısmi veya tam)"""
        try:
            if side == 'SHORT':
                order = await self._safe_call(
                    self.exchange.create_market_buy_order,
                    symbol, amount, params={'reduceOnly': True}
                )
            else:
                order = await self._safe_call(
                    self.exchange.create_market_sell_order,
                    symbol, amount, params={'reduceOnly': True}
                )
            logger.info(f"✅ Pozisyon kapatıldı: {symbol} | {amount}")
            return order
        except Exception as e:
            if "ReduceOnly Order is rejected" in str(e):
                logger.info(f"ℹ️ {symbol} pozisyonu zaten borsa tarafında (SL/TP) kapanmış.")
            else:
                logger.error(f"❌ Pozisyon kapatılamadı {symbol}: {e}")
            return None

    async def set_stop_loss(self, symbol: str, side: str, stop_price: float) -> dict | None:
        """Stop loss emri koy (Pozisyona bağlı — closePosition)"""
        try:
            # Önce varsa semboldeki tüm SL/TP emirlerini temizle
            await self.cancel_all_orders(symbol)
            await asyncio.sleep(1.0)  # Borsa motoruna vakit tanı
            
            sl_side = 'buy' if side == 'SHORT' else 'sell'
            order = await self._safe_call(
                self.exchange.create_order,
                symbol, 'stop_market', sl_side, None,
                params={'stopPrice': stop_price, 'closePosition': True}
            )
            logger.info(f"🛑 SL ayarlandı: {symbol} @ {stop_price} (Pozisyona bağlı)")
            return order
        except Exception as e:
            if "code\":-4130" in str(e):
                logger.warning(f"⚠️ {symbol} SL zaten ayarlı veya çakışma var: {e}")
            else:
                logger.error(f"❌ SL ayarlanamadı {symbol}: {e}")
            return None

    async def cancel_all_orders(self, symbol: str):
        """Bir sembol için tüm açık emirleri iptal et"""
        try:
            await self._safe_call(self.exchange.cancel_all_orders, symbol)
            logger.info(f"🗑️ Tüm emirler iptal edildi: {symbol}")
        except Exception as e:
            logger.warning(f"⚠️ Emir iptali başarısız {symbol}: {e}")

    async def fetch_ohlcv(self, symbol: str, timeframe: str = '4h', limit: int = 50) -> list:
        """OHLCV verisi çek"""
        try:
            return await self._safe_call(self.exchange.fetch_ohlcv, symbol, timeframe, limit=limit)
        except Exception as e:
            if "Invalid symbol status" in str(e) or "code\":-1122" in str(e):
                logger.warning(f"⚠️ {symbol} şu an işlem görmüyor (Invalid Status)")
            else:
                logger.error(f"❌ OHLCV alınamadı {symbol}: {e}")
            return []

    async def fetch_ticker(self, symbol: str) -> dict | None:
        """Anlık fiyat bilgisi"""
        return await self._safe_call(self.exchange.fetch_ticker, symbol)

    async def fetch_tickers(self, symbols: list = None) -> dict:
        """Birden fazla sembol için ticker çek"""
        try:
            return await self._safe_call(self.exchange.fetch_tickers, symbols)
        except Exception as e:
            logger.error(f"❌ Tickers alınamadı: {e}")
            return {}

    async def load_markets(self):
        """Piyasaları yükle"""
        try:
            return await self._safe_call(self.exchange.load_markets)
        except Exception as e:
            logger.error(f"❌ Markets yüklenemedi: {e}")
            return {}

    def sanitize_amount(self, symbol: str, amount: float) -> float:
        """Miktarı market limitlerine uygun hale getir"""
        try:
            return float(self.exchange.amount_to_precision(symbol, amount))
        except Exception as e:
            logger.warning(f"⚠️ Miktar normalize edilemedi {symbol}: {e}")
            return amount

    async def cleanup_orphan_orders(self, active_symbols: set):
        """Aktif pozisyonu olmayan coinlerin bekleyen emirlerini iptal et"""
        try:
            open_orders = await self._safe_call(self.exchange.fetch_open_orders)
            if not open_orders:
                return
            
            order_symbols = set()
            for order in open_orders:
                raw_sym = order.get('info', {}).get('symbol', '')
                if not raw_sym:
                    raw_sym = order['symbol'].replace('/', '').split(':')[0]
                order_symbols.add(raw_sym)
            
            orphan_symbols = order_symbols - active_symbols
            
            if orphan_symbols:
                logger.info(f"🧹 {len(orphan_symbols)} yetim sembol tespit edildi")
                for sym in orphan_symbols:
                    await self.cancel_all_orders(sym)
                logger.info(f"✅ Yetim emirler temizlendi!")
                    
        except Exception as e:
            logger.warning(f"⚠️ Yetim emir temizliği atlandi: {e}")

    async def close(self):
        """Exchange bağlantısını kapat"""
        try:
            await self.exchange.close()
        except Exception as e:
            logger.debug(f"Exchange kapatma hatası: {e}")
