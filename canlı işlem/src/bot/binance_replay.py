"""
==============================================================================
BINANCE REPLAY MODE - Geçmiş Veri Replay
18.02.2026.py ile uyumlu - Binance Futures (USDT-M)
==============================================================================
"""
import pandas as pd
import logging
import json
import hashlib
import aiohttp
from datetime import datetime, timedelta
from typing import Optional
import asyncio
import ccxt.async_support as ccxt
from .redis_client import redis_client

logger = logging.getLogger("replay")


def _make_binance_replay_exchange(demo: bool = False) -> ccxt.binance:
    """
    Ana dosyadaki (18.02.2026.py) DNS fix mantığıyla Binance exchange oluştur.
    Public data için API key gerekmez.
    """
    session = None
    try:
        resolver = aiohttp.AsyncResolver(nameservers=["8.8.8.8", "1.1.1.1", "8.8.4.4"])
        connector = aiohttp.TCPConnector(resolver=resolver, limit=20, ttl_dns_cache=300)
        session = aiohttp.ClientSession(connector=connector)
    except Exception:
        try:
            resolver = aiohttp.resolver.ThreadedResolver()
            connector = aiohttp.TCPConnector(resolver=resolver, limit=20, ttl_dns_cache=300)
            session = aiohttp.ClientSession(connector=connector)
        except Exception:
            session = None

    opts = {
        "enableRateLimit": True,
        "timeout": 30_000,
        "options": {"defaultType": "future"},  # USDT-M futures
    }

    ex = ccxt.binance(opts)

    if demo:
        ex.enable_demo_trading(True)
        logger.info("🧪 Replay: Demo mode aktif")

    if session is not None:
        ex.session = session
    return ex


class BinanceReplayProvider:
    """
    Binance Futures API'den geçmiş veri çekerek replay yapar.
    18.02.2026.py stratejisiyle tam uyumlu.
    Redis cache + paralel fetching ile hızlı başlangıç.
    """
    
    def __init__(self, speed_multiplier: float = 100.0, demo: bool = False):
        self.speed_multiplier = speed_multiplier
        self.current_time: Optional[datetime] = None
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.data_cache: dict[str, pd.DataFrame] = {}
        self.symbols: list[str] = []
        self._running = False
        
        # Binance bağlantısı (public - API key gerekmez)
        self.exchange = _make_binance_replay_exchange(demo=demo)
        
    def _get_cache_key(self, symbol: str, start: datetime, end: datetime) -> str:
        """Cache key oluştur: symbol + tarih aralığı"""
        key_data = f"{symbol}:{start.isoformat()}:{end.isoformat()}"
        return f"replay:cache:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    async def _get_cached_data(self, symbol: str, start: datetime, end: datetime) -> Optional[pd.DataFrame]:
        """Redis'ten cache'lenmiş veriyi al"""
        try:
            cache_key = self._get_cache_key(symbol, start, end)
            cached = await redis_client.get(cache_key)
            
            if cached and 'data' in cached:
                # JSON'dan DataFrame'e çevir
                df_data = json.loads(cached['data'])
                df = pd.DataFrame(df_data)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                logger.info(f"💾 {symbol}: Cache'den yüklendi ({len(df)} mum)")
                return df
        except Exception as e:
            logger.debug(f"Cache okuma hatası {symbol}: {e}")
        return None
    
    async def _cache_data(self, symbol: str, start: datetime, end: datetime, df: pd.DataFrame):
        """Veriyi Redis'e cachele"""
        try:
            cache_key = self._get_cache_key(symbol, start, end)
            # DataFrame'i JSON'a çevir
            df_copy = df.copy()
            df_copy['timestamp'] = df_copy['timestamp'].astype(str)
            cache_data = {
                'symbol': symbol,
                'start': start.isoformat(),
                'end': end.isoformat(),
                'data': df_copy.to_json(orient='records'),
                'cached_at': datetime.now().isoformat()
            }
            # 7 gün cache'de tut
            await redis_client.set(cache_key, cache_data, expire=604800)
            logger.debug(f"💾 {symbol}: Cache'lendi")
        except Exception as e:
            logger.debug(f"Cache yazma hatası {symbol}: {e}")
        
    async def initialize(self, symbols: list[str], start_date: datetime, 
                         end_date: datetime, speed: float = 100.0,
                         top_coins: int = 0):
        """
        Replay'i başlat - veriyi Binance API'den çek
        
        Args:
            symbols: İzlenecek coinler (top_coins=0 ise kullanılır)
            start_date: Başlangıç tarihi
            end_date: Bitiş tarihi  
            speed: Hız çarpanı
            top_coins: Otomatik coin sayısı (50/100/200), 0=symbols kullan
        """
        # Top coins modu - Binance'den çek
        logger.info(f"🔧 Initialize: top_coins={top_coins}, symbols={len(symbols)}")
        
        if top_coins > 0:
            logger.info(f"🏆 Top {top_coins} coin çekiliyor...")
            self.symbols = await self._fetch_top_coins(top_coins)
            logger.info(f"📊 Binance'den {len(self.symbols)} coin çekildi")
        else:
            self.symbols = symbols
            logger.info(f"📊 Manuel {len(self.symbols)} coin kullanılıyor")
            
        self.start_time = start_date
        self.end_time = end_date
        self.current_time = start_date
        self.speed_multiplier = speed
        
        logger.info(f"📼 Binance Replay Başlatılıyor...")
        logger.info(f"   📅 {start_date} → {end_date}")
        logger.info(f"   🚀 {speed}x hız")
        logger.info(f"   📊 {len(self.symbols)} coin")
        
        # Önce cache kontrolü yap, eksik coinleri belirle
        cached_count = 0
        fetch_symbols = []
        
        for symbol in self.symbols:
            cached_df = await self._get_cached_data(symbol, start_date, end_date)
            if cached_df is not None:
                self.data_cache[symbol] = cached_df
                cached_count += 1
            else:
                fetch_symbols.append(symbol)
        
        if cached_count > 0:
            logger.info(f"💾 {cached_count} coin cache'den yüklendi")
        
        # Eksik coinleri paralel çek
        if fetch_symbols:
            logger.info(f"🌐 {len(fetch_symbols)} coin API'den çekiliyor (paralel)...")
            await self._fetch_all_history_parallel(fetch_symbols, start_date, end_date)
        
        if not self.data_cache:
            raise ValueError("Hiçbir coin verisi çekilemedi!")
        
        logger.info(f"✅ Replay hazır: {len(self.data_cache)} coin yüklendi")
    
    async def _fetch_all_history_parallel(self, symbols: list[str], start: datetime, end: datetime):
        """
        Tüm coinleri paralel olarak çek - hızlı başlangıç için
        """
        semaphore = asyncio.Semaphore(5)  # Aynı anda max 5 istek
        
        async def fetch_with_limit(symbol: str):
            async with semaphore:
                df = await self._fetch_history(symbol, start, end)
                if not df.empty:
                    self.data_cache[symbol] = df
                    # Cache'e kaydet
                    await self._cache_data(symbol, start, end, df)
                await asyncio.sleep(0.1)  # Kısa bekleme
        
        # Tüm coinleri paralel başlat
        tasks = [fetch_with_limit(sym) for sym in symbols]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _fetch_top_coins(self, count: int = 50) -> list[str]:
        """
        Binance Futures'ten hacme göre top coinleri çek
        Ana dosyadaki (18.02.2026.py) fetch_universe mantığıyla uyumlu
        """
        try:
            # Markets yükle
            markets = await self.exchange.load_markets(True)
            
            # USDT-M futures filtrele (18.02.2026.py mantığı)
            universe = []
            for sym, mkt in markets.items():
                if not mkt.get("active"):
                    continue
                if mkt.get("quote") != "USDT":
                    continue
                if mkt.get("type") not in ("swap", "future"):
                    continue
                if mkt.get("linear") is not True:
                    continue
                # Major-cap hariç (BTC, ETH, BNB...)
                base = mkt.get("base", "")
                if base in {"BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE"}:
                    continue
                universe.append(sym)
            
            # Tickers çek ve hacme göre sırala
            tickers = await self.exchange.fetch_tickers(universe)
            
            sorted_symbols = sorted(
                universe,
                key=lambda s: float(tickers.get(s, {}).get('quoteVolume', 0) or 0),
                reverse=True
            )
         inance Futures'ten geçmiş OHLCV verisi çek
        Ana dosyadaki (18.02.2026.py) fetch_ohlcv mantığıyla uyumlu
        """
        try:
            # Sembol formatı kontrolü (CCXT standart: BTC/USDT)
            if '/' not in symbol:
                # BTCUSDT formatı -> BTC/USDT'ye çevir
                ccxt_symbol = f"{symbol.replace('USDT', '')}/USDT"
            else:
                ccxt_symbol = symbol
                
            since = int(start.timestamp() * 1000)
            
            # Veriyi çek (pagination ile) - 4H timeframe (ana strateji)
            all_ohlcv = []
            current_since = since
            
            while True:
                ohlcv = await self.exchange.fetch_ohlcv(
                    ccxt_symbol, 
                    timeframe='4h',  # Ana strateji timeframe
                    since=current_since,
                    limit=1000  # Binance max limit
                )
                
                if not ohlcv:
                    break
                    
                all_ohlcv.extend(ohlcv)
                
                # Sonraki batch
                current_since = ohlcv[-1][0] + 1
                
                # Bitiş tarihini geçtik mi?
                if current_since > int(end.timestamp() * 1000):
                    break
                    
                await asyncio.sleep(0.3)  # Rate limit (Binance)
            
            if not all_ohlcv:
                logger.warning(f"⚠️ {symbol}: Veri alınamadı")
                return pd.DataFrame()
            
            # DataFrame oluştur (18.02.2026.py formatı)
            df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
            df.set_index('timestamp', inplace=True)
            
            # Tarih filtresi
            df = df[(df.index >= start) & (df.index
                
                # Bitiş tarihini geçtik mi?
                if current_since > int(end.timestamp() * 1000):
                    break
                    
                await asyncio.sleep(0.2)  # Rate limit
            
            if not all_ohlcv:
                logger.warning(f"⚠️ {symbol}: Veri alınamadı")
                return pd.DataFrame()
            
            # DataFrame oluştur
            df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Tarih filtresi
            df = df[(df['timestamp'] >= start) & (df['timestamp'] <= end)]
            
            logger.info(f"📊 {symbol}: {len(df)} mum yüklendi")
            return df
            
        except Exception as e:
            logger.error(f"❌ {symbol} veri hatası: {e}")
            return pd.DataFrame()
    
    def start(self):
        """Replay'i başlat"""
        self._running = True
        logger.info(f"▶️ Replay başlatıldı @ {self.current_time}")
    
    def stop(self):
        """Replay'i durdur"""
        self._running = False
        logger.info(f"⏹️ Replay durduruldu @ {self.current_time}")
    
    def is_running(self) -> bool:
        """Replay çalışıyor mu?"""
        return self._running and self.current_time < self.end_time
    
    def get_progress(self) -> float:
        """İlerleme yüzdesi (0-100)"""
        if not self.current_time or not self.end_time:
            return 0.0
        total = (self.end_time - self.start_time).total_seconds()
        current = (self.current_time - self.start_time).total_seconds()
        if total <= 0:
            return 100.0
        return min(100.0, (current / total) * 100)
    
    def get_current_data(self, symbol: str, lookback: int = 50) -> pd.DataFrame:
        """
        Mevcut replay zamanına kadar olan veriyi getir
        """
        if symbol not in self.data_cache:
            return pd.DataFrame()
        
        df = self.data_cache[symbol]
        mask = df['timestamp'] <= self.current_time
        available = df[mask]
        
        if len(available) < lookback:
            return available
        
        return available.tail(lookback)
    
    def get_current_ticker(self, symbol: str) -> Optional[dict]:
        """
        Mevcut zamandaki son fiyat
        Ana dosyadaki fetch_ticker formatıyla uyumlu
        """
        df = self.get_current_data(symbol, lookback=1)
        if df.empty:
            return None
        
        last = df.iloc[-1]
        last_price = float(last['close'])
        
        return {
            'symbol': symbol,
            'last': last_price,
            'bid': last_price * 0.9999,
            'ask': last_price * 1.0001,
            'close': last_price,
            'timestamp': self.current_time.isoformat(),
            'datetime': self.current_time.isoformat()
        }
    
    async def tick(self, real_time_seconds: float = 1.0) -> bool:
        """
        Replay zamanını ilerlet
        
    18.02.2026.py PumpSnifferBot ile uyumlu
    """
    
    def __init__(self, data_provider: Binance
        if not self._running or self.current_time >= self.end_time:
            return False
        
        # Hızlandırılmış zaman
        time_step = timedelta(seconds=real_time_seconds * self.speed_multiplier)
        self.current_time += time_step
        
        if self.current_time > self.end_time:
            self.current_time = self.end_time
            return False
        
        return True


class ReplayExchangeClient:
    """
    Replay için simüle edilmiş exchange client
    """
    
    def __init__(self, data_provider: BybitReplayProvider):
        self.data_provider = data_provider
        self.simulated_positions: dict = {}
        self.balance = {'total': 10000.0, 'free': 10000.0, 'used': 0.0}
        4h', limit: int = 100) -> list:
        """Ana strateji timeframe: 4h"""
        df = self.data_provider.get_current_data(symbol, lookback=limit)
        if df.empty:
            return []
        
        ohlcv = []
        for idx, row in df.iterrows():
            ohlcv.append([
                int(idx.timestamp() * 1000),  # index = timestamp
        ohlcv = []
        for _, row in df.iterrows():
            ohlcv.append([
                int(row['timestamp'].timestamp() * 1000),
                float(row['open']),
                float(row['high']),
                float(row['low']),
                float(row['close']),
                float(row['volume'])
            ])
        return ohlcv
    
    def get_balance(self) -> dict:
        return self.balance
    
    def get_positions(self) -> list:
        return list(self.simulated_positions.values())
    
    def open_long(self, symbol: str, amount: float) -> dict:
        ticker = self.fetch_ticker(symbol)
        if not ticker:
            return None
        
        price = ticker['last']
        self.simulated_positions[symbol] = {
            'symbol': symbol,
            'side': 'LONG',
            'contracts': amount,
            'entryPrice': price,
            'markPrice': price,
            'unrealizedPnl': 0.0
        }
        
        logger.info(f"📈 [REPLAY] LONG: {symbol} @ {price} | {amount}")
        return {'id': f'replay_{symbol}_long', 'average': price}
    
    def open_short(self, symbol: str, amount: float) -> dict:
        ticker = self.fetch_ticker(symbol)
        if not ticker:
            return None
        
        price = ticker['last']
        self.simulated_positions[symbol] = {
            'symbol': symbol,
            'side': 'SHORT',
            'contracts': amount,
            'entryPrice': price,
            'markPrice': price,
            'unrealizedPnl': 0.0
        }
        
        logger.info(f"📉 [REPLAY] SHORT: {symbol} @ {price} | {amount}")
        return {'id': f'replay_{symbol}_short', 'average': price}
    
    def close_position(self, symbol: str, side: str, amount: float) -> dict:
        if symbol in self.simulated_positions:
            del self.simulated_positions[symbol]
            logger.info(f"✅ [REPLAY] KAPATILDI: {symbol}")
        return {'id': f'replay_close_{symbol}'}
    
    def set_stop_loss(self, symbol: str, side: str, stop_price: float) -> dict:
        logger.debug(f"🛑 [REPLAY] SL: {symbol} @ {stop_price}")
        return {'id': f'replay_sl_{symbol}'}
    
    def cancel_all_orders(self, symbol: str):
        pass
    
    def cleanup_orphan_orders(self, active_symbols: set):
        """Replay modunda yetim emir temizliği (no-op)"""
        pass
    
    def set_leverage(self, symbol: str, leverage: int):
        pass
    
    def set_margin_mode(self, symbol: str, mode: str = "isolated"):
        pass
    
    def sanitize_amount(self, symbol: str, amount: float) -> float:
        """Miktarı market limitlerine uygun hale getir (simüle edilmiş)"""
        # Replay modunda basit bir doğrulama yap
        if amount <= 0:
            return 0.0
        # Minimum 0.001, maksimum 1M limit
        ret
        Binance Futures API formatında ticker listesi
        Ana dosyadaki universe taraması için gerekli
        """
        tickers = []
        for symbol in self.data_provider.symbols:
            ticker = self.fetch_ticker(symbol)
            if ticker:
                # Binance Futures API formatı
                raw_symbol = symbol.replace('/', '')  # BTC/USDT -> BTCUSDT
                tickers.append({
                    'symbol': raw_symbol,
                    'lastPrice': str(ticker['last']),
                    'quoteVolume': '10000000',  # Simulated - min volume içinrs for replay symbols"""
        tickers = []
        for symbol in self.data_provider.symbols:
            ticker = self.fetch_ticker(symbol)
           
        Binance Futures market yapısı
        Ana dosyadaki fetch_universe için gerekli
        """
        markets = {}
        for symbol in self.data_provider.symbols:
            base = symbol.replace('/USDT', '').replace('USDT', '')
            markets[symbol] = {
                'symbol': symbol,
                'base': base,
                'quote': 'USDT',
                'active': True,
                'type': 'swap',
                'linear': True,
                'limits': {
                    'amount': {'min': 0.001, 'max': 1000000}
                },
                'precision': {
                    'amount': 0.001,
                    'price': 0.01
                }
            }
        return markets
    
    def load_markets(self, reload: bool = False):
        """Market yükleme (simüle edilmiş)"""
        return self.market symbol in self.data_provider.symbols:
            markets[symbol] = {
                'symbol': symbol,
                'active': True,
                'limits': {
                    'amount': {'min': 0.001, 'max': 1000000}
                }
            }
        return markets
    
    def load_markets(self, reload: bool = False):
        """Scanner compatibility - no-op"""
        pass
