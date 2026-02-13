"""
🔍 Market Tarayıcı
Top 100 coin'i sürekli tarar, strateji sinyallerini üretir
"""
import pandas as pd
import logging
import time
import asyncio
from .exchange import ExchangeClient
from .strategy import Strategy
from .config import TIMEFRAME, OHLCV_LIMIT, TOP_COINS_COUNT, MIN_24H_VOLUME

from .redis_client import redis_client

logger = logging.getLogger("scanner")


class MarketScanner:
    """Sürekli çalışan piyasa tarayıcı"""

    def __init__(self, exchange: ExchangeClient):
        self.exchange = exchange
        self.strategy = Strategy()
        self.symbols: list[str] = []
        
        # 🛡️ FİLTRE LİSTESİ (Stabil ve Pegged Coinler)
        self.IGNORED_COINS = {
            'USDC', 'FDUSD', 'TUSD', 'USDP', 'DAI', 'EUR', 'BUSD', 'USDD', 'PYUSD',
            'WBTC', 'BTCST', 'BETH' # Pegged varlıklar (Hareketi ana coine bağlı)
        }
        self.IGNORED_KEYWORDS = ['DOWN', 'UP', 'BEAR', 'BULL'] # Kaldıraçlı token isimleri
        self.last_refresh = 0
        self.refresh_interval = 3600  # Her saat coin listesini yenile

    def refresh_symbols(self):
        """Top coin listesini güncelle"""
        now = time.time()
        if now - self.last_refresh < self.refresh_interval and self.symbols:
            return

        logger.info(f"🔄 Top {TOP_COINS_COUNT} coin listesi yenileniyor...")
        
        try:
            # Tüm futures sembollerini ve hacimlerini çek
            tickers_list = self.exchange.exchange.fapiPublicGetTicker24hr()
        except Exception as e:
            logger.error(f"⚠️ Futures ticker bilgileri çekilirken hata oluştu: {e}")
            return

        # Hacme göre sırala
        tickers_list.sort(key=lambda x: float(x.get('quoteVolume', 0)), reverse=True)
        
        top_coins = []
        limit = TOP_COINS_COUNT
        for t in tickers_list:
            symbol = t['symbol']
            
            # 🛡️ FİLTRELEME MANTIĞI
            # USDT paritelerini hedefliyoruz ve base asset'i çıkarıyoruz
            if not symbol.endswith('USDT'):
                continue

            base_asset = symbol.replace('USDT', '')
            
            # 1. Stabil Coin Kontrolü
            if base_asset in self.IGNORED_COINS:
                continue
                
            # 2. İsim Kontrolü (DOWN/UP vb.)
            if any(k in base_asset for k in self.IGNORED_KEYWORDS):
                continue
            
            # 3. Hacim Kontrolü (Minimum 24s hacim)
            quote_vol = float(t.get('quoteVolume', 0))
            if quote_vol < MIN_24H_VOLUME: 
                continue
            
            top_coins.append(symbol)
            if len(top_coins) >= limit:
                break
        
        self.symbols = top_coins
        self.last_refresh = now
        logger.info(f"✅ {len(self.symbols)} coin yüklendi (Filtrelendi)")

    async def scan_symbol(self, symbol: str) -> dict | None:
        """Tek bir coin'i tara ve sinyal üret"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, TIMEFRAME, OHLCV_LIMIT)
            if not ohlcv or len(ohlcv) < 20:
                return None

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # İndikatörleri hesapla
            df = self.strategy.calculate_indicators(df)

            # Sinyal üret
            signal = self.strategy.generate_signal(symbol, df)
            
            if signal.get('side') != 'WAIT':
                return signal
            
            return None

        except Exception as e:
            logger.debug(f"⚠️ {symbol} tarama hatası: {e}")
            return None

    async def scan_all(self) -> list[dict]:
        """Tüm coinleri paralel tara ve aktif sinyalleri dön"""
        self.refresh_symbols()
        
        logger.info(f"🔍 {len(self.symbols)} parite momentum için taranıyor...")
        
        # Paralel tarama (Batch processing)
        tasks = [self.scan_symbol(sym) for sym in self.symbols]
        results = await asyncio.gather(*tasks)
        
        # None olmayanları (aktif sinyalleri) filtrele
        signals = [s for s in results if s is not None]

        if signals:
            logger.info(f"🎯 {len(signals)} MOMENTUM SİNYALİ BULUNDU!")
            for sig in signals:
                logger.info(f"✅ {sig['symbol']}: {sig['action']} | {sig['reason']}")
        else:
            logger.info("🔍 Kriterlere uygun momentum hareketi bulunamadı.")

        return signals
