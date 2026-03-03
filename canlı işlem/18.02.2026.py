"""
==============================================================================
PUMP & DUMP REVERSION BOT — Binance Futures (USDT-M)
Tarih : 18 Şubat 2026
Geliştirici: Buğra Türkoğlu
Strateji : Agresif pump yapan low/mid-cap altcoinlerde dağıtım (distribution)
             onayı ile SHORT giriş, Bollinger + Fibonacci hedefleriyle çıkış.
Timeframe : 4H
Kütüphaneler: ccxt (async), pandas, pandas_ta (opsiyonel), numpy
==============================================================================

KULLANIM:
  Backtest  →  python 18.02.2026.py --backtest
  Canlı Bot →  python 18.02.2026.py --live
  Sadece Watchlist → python 18.02.2026.py --scan

==============================================================================
"""

# ── Standart Kütüphaneler ────────────────────────────────────────────────
import asyncio
import logging
import sys
import time
import os
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ── 3. Parti Kütüphaneler ───────────────────────────────────────────────
import numpy as np
import pandas as pd

try:
    import pandas_ta as ta          # opsiyonel; yoksa manuel hesaplayacağız
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False

import aiohttp
import ccxt.async_support as ccxt

# ── Telegram Notifier (Opsiyonel) ───────────────────────────────────
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from src.bot import notifier
    NOTIFIER_AVAILABLE = True
except ImportError:
    NOTIFIER_AVAILABLE = False
    class notifier:
        """Dummy notifier - httpx yoksa hiçbir şey yapmaz"""
        @staticmethod
        def send(text): pass
        @staticmethod
        def notify_trade_open(*args, **kwargs): pass
        @staticmethod
        def notify_trade_close(*args, **kwargs): pass

# ── Logging Ayarları ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

log = logging.getLogger("PumpDumpBot")

# ── params.py yükleyici ──────────────────────────────────────────────────
# canlı işlem/params.py varsa oradan yükler, dosya yoksa varsayılan değerler kullanılır.
def _load_params():
    import importlib.util
    _here = os.path.dirname(os.path.abspath(__file__))
    # Arama sırası: ayarlar.py önce (Türkçe açıklamalı), sonra params.py
    candidates = [
        ("ayarlar", os.path.join(_here, "ayarlar.py")),
        ("ayarlar", os.path.join(_here, "..", "ayarlar.py")),
        ("params",  os.path.join(_here, "params.py")),
        ("params",  os.path.join(_here, "..", "params.py")),
    ]
    for _mod_name, _candidate in candidates:
        _path = os.path.normpath(_candidate)
        if os.path.exists(_path):
            spec = importlib.util.spec_from_file_location(_mod_name, _path)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            log.info(f"⚙️  Ayarlar yüklendi: {_path}")
            return mod
    log.warning("⚠️  ayarlar.py / params.py bulunamadı — Config varsayılan değerleri kullanılıyor")
    return None

_P = _load_params()

def _p(name, default):
    """params.py'de tanımlıysa kullan, yoksa default döndür."""
    return getattr(_P, name, default) if _P is not None else default

# ── Demo / Canlı Exchange Factory ─────────────────────────────────────────────────────
def _make_binance_exchange(extra_opts: dict = None, demo: bool = False) -> ccxt.binance:
    """
    Binance Futures exchange örneği oluşturur.

    DNS fix: aiodns yerine sistemin DefaultResolver’ını kullanır (Türkiye DNS sorunu).

    demo=True  → Binance Demo Trading (demo.binance.com) — gerçek para yok.
                  Dokümana göre: sandbox/testnet DEGİL, enable_demo_trading(True) kullan.
    demo=False → Canlı Binance Futures (API key varsa geçerli işlem açar).
    """
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
        "timeout": 30_000,
        "options": {
            "defaultType": "future",
            "adjustForTimeDifference": True,  # Clock drift fix (-1000 unknown error)
            "recvWindow": 10000,              # Binance zaman toleransını 10sn'ye çıkar
        },
    }
    if extra_opts:
        opts.update(extra_opts)

    ex = ccxt.binance(opts)

    if demo:
        # Doküman önerisi: enable_demo_trading(True) — tüm URL’leri otomatik demo-fapi.binance.com’a yönlendirir.
        # set_sandbox_mode(True) KULLANMA — eski testnet’e gider, hata alırsın.
        ex.enable_demo_trading(True)
        log.info("🧪 Demo Trading modu aktif (demo-fapi.binance.com)")

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


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 0 — YARDIMCI HESAPLAMA FONKSİYONLARI (pandas_ta yoksa fallback)
# ══════════════════════════════════════════════════════════════════════════

def calc_bollinger_bands(close: pd.Series, length: int = 20, std_mult: float = 2.0) -> pd.DataFrame:
    """
    Bollinger Bands hesapla.
    Döndürür: DataFrame  →  BBU, BBM, BBL sütunları
    """
    if HAS_PANDAS_TA:
        bb = ta.bbands(close, length=length, std=std_mult)
        if bb is not None:
            # pandas_ta sütun adları versiyona göre değişebilir; düzeltelim
            cols = bb.columns.tolist()
            upper_col = [c for c in cols if "BBU" in c.upper()][0]
            mid_col   = [c for c in cols if "BBM" in c.upper()][0]
            low_col   = [c for c in cols if "BBL" in c.upper()][0]
            return pd.DataFrame({
                "BBU": bb[upper_col],
                "BBM": bb[mid_col],
                "BBL": bb[low_col],
            }, index=close.index)

    # ── fallback: manuel hesaplama ────────────────────────────────────
    sma   = close.rolling(window=length).mean()
    rstd  = close.rolling(window=length).std(ddof=0)
    upper = sma + std_mult * rstd
    lower = sma - std_mult * rstd
    return pd.DataFrame({"BBU": upper, "BBM": sma, "BBL": lower}, index=close.index)


def calc_rsi(close: pd.Series, length: int = 14) -> pd.Series:
    """RSI (Relative Strength Index) hesapla."""
    if HAS_PANDAS_TA:
        rsi = ta.rsi(close, length=length)
        if rsi is not None:
            return rsi
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(window=length).mean()
    loss  = (-delta.clip(upper=0)).rolling(window=length).mean()
    rs    = gain / loss
    return 100 - (100 / (1 + rs))


def calc_volume_avg(volume: pd.Series, length: int = 5) -> pd.Series:
    """Son N mumun ortalama hacmini hesapla."""
    return volume.rolling(window=length).mean()


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 0.5 — VERİ MODELLERİ (Dataclass'lar)
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class WatchlistItem:
    """Watchlist'teki bir coinin verisi."""
    symbol: str
    pump_pct: float            # Tespit edilen pump yüzdesi
    pump_low: float            # Pump'ın başlangıç (en düşük) fiyatı
    pump_high: float           # Pump'ın zirve (en yüksek) fiyatı — SL hesabında kullanılır
    added_at: str              # Listeye eklenme zamanı (ISO)
    last_checked: str = ""    # Son tarama zamanı
    reentry_count: int = 0    # Bu pump döngüsünde yapılan yeniden giriş sayısı


@dataclass
class TradeRecord:
    """Açılan / kapanan bir ticaretin kaydı."""
    symbol: str
    side: str = "SHORT"
    entry_time: str = ""
    entry_price: float = 0.0
    stop_loss: float = 0.0
    initial_stop_loss: float = 0.0  # Başlangıç SL değeri (değişmez, rapor için)
    tp1_price: float = 0.0          # Kullanılmıyor — TSL ile kapatılıyor
    tp2_price: float = 0.0          # Kullanılmıyor (v3'te tek TP)
    position_size_usdt: float = 0.0
    remaining_pct: float = 1.0      # Her zaman 1.0 (v2: tek TP, %100 kapama)
    exit_time: str = ""
    exit_price: float = 0.0
    exit_reason: str = ""
    pnl_usdt: float = 0.0
    pnl_pct: float = 0.0
    sl_moved_to_be: bool = False    # SL break-even'a çekildi mi?
    breakeven_triggered: bool = False  # Stage 1: %4 düşüşte BE tetiklendi mi?
    tsl_active: bool = False           # Stage 2: Trailing Stop aktif mi? (%8 düşüşte devreye girer)
    lowest_low_reached: float = 0.0   # TSL için takip edilen en düşük fiyat
    entry_candle_open: float = 0.0  # Giriş mumunun açılış fiyatı
    reentry_count: int = 0          # Bu pump döngüsünde kaçıncı giriş
    consec_green_loss: int = 0      # Zararda arka arkaya yeşil mum sayacı (2'de çık)
    _last_checked_ts: str = ""       # Son değerlendirilen kapanmış mum timestamp'i (aynı mumu tekrar saymamak için)

    # Backtest ekstra alanları
    pump_pct: float = 0.0
    pump_high: float = 0.0
    pump_low: float = 0.0
    leverage: int = 3              # Pozisyonda kullanılan kaldıraç (dinamik)
    portfolio_after: float = 0.0   # İşlem kapandıktan sonraki toplam kasa
    pnl_4h_est: float = 0.0        # 4H tahmini PnL (5m sim karşılaştırması için)


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 1 — KONFİGÜRASYON
# ══════════════════════════════════════════════════════════════════════════

class Config:
    """
    Tüm bot parametrelerini tek yerde topluyoruz.

    STRATEJİ (v3 — Refined Scalper):
      Module 1: Top 10 Rolling Pump (24H/6×4H bazlı) → Watchlist
      Module 2: 4H Kapanan Kırmızı Mum → SHORT (pump sonrası giriş)
      Module 3: SL entry'nin %15 üstü (entry × 1.15), BE @ %7 düşüş, TSL @ %7 düşüş
      Module 4: Çıkış yalnızca SL / BE / TSL ile (dinamik yönetim)
      Module 5: Yeni pump sonrası yeniden giriş (fresh push koşulu)
    """

    # ── Exchange bağlantı ─────────────────────────────────────────────
    EXCHANGE_ID         = "binance"
    DEFAULT_TYPE        = "future"       # USDT-M futures
    TIMEOUT_MS          = 30_000
    RATE_LIMIT          = True
    DEMO_MODE           = os.environ.get("EXCHANGE_SANDBOX", "true").lower() in ("true", "1", "yes")
    MIN_NOTIONAL_USDT   = 5.0            # Binance minimum emir değeri (USDT)

    # ── Module 1 — RADAR (Top 10 Rolling Pump - 24H/6×4H) ──────────────
    EXCLUDED_BASES      = {
        # Major-cap coinleri hariç tut
        "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE",
    }
    PUMP_MIN_PCT                 = _p("PUMP_MIN_PCT",                30.0)
    TOP_N_GAINERS                = _p("TOP_N_GAINERS",               10)
    # SCAN_INTERVAL_SEC kaldırıldı — _prep_scan_loop mum kapanışından 5dk önce tara yapıyor
    MANAGER_INTERVAL_SEC         = _p("MANAGER_INTERVAL_SEC",        5)
    WATCHLIST_CHECK_INTERVAL_SEC = _p("WATCHLIST_CHECK_INTERVAL_SEC", int(os.environ.get("WATCHLIST_CHECK_SECONDS", "60")))

    # ── Module 2 — TRIGGER (Pure Price Action) ───────────────────────
    TIMEFRAME                    = _p("TIMEFRAME",                   os.environ.get("TIMEFRAME", "4h"))
    BB_LENGTH                    = 20
    BB_STD                       = 2.0
    PRE_ENTRY_GREEN_CANDLES      = 4
    PUMP_CONSECUTIVE_GREEN       = 4
    PUMP_WINDOW_CANDLES          = _p("PUMP_WINDOW_CANDLES",         7)
    PUMP_MIN_GREEN_COUNT         = _p("PUMP_MIN_GREEN_COUNT",        4)
    ENTRY_RED_BODY_MIN_PCT       = _p("ENTRY_RED_BODY_MIN_PCT",      4.0)
    # ENTRY_RED_BODY_MAX_PCT kaldırıldı — büyük kırmızı mum daha güçlü reversal sinyalidir
    PRE_CANDLE_GREEN_BODY_MAX_PCT = _p("PRE_CANDLE_GREEN_BODY_MAX_PCT", 30.0)
    GREEN_LOSS_MIN_BODY_PCT      = _p("GREEN_LOSS_MIN_BODY_PCT",     6.0)
    GREEN_LOSS_SINGLE_BODY_PCT   = _p("GREEN_LOSS_SINGLE_BODY_PCT",  10.0)
    ANTI_ROCKET_SINGLE_CANDLE_PCT = _p("ANTI_ROCKET_SINGLE_CANDLE_PCT", 22.0)
    MIN_VOLUME_USDT              = _p("MIN_VOLUME_USDT",             10_000_000.0)

    # ── Module 3 — TRADE MANAGEMENT ─────────────────────────────────
    LEVERAGE                     = _p("LEVERAGE",                    int(os.environ.get("LEVERAGE", "3")))
    MAX_ACTIVE_TRADES            = _p("MAX_ACTIVE_TRADES",           int(os.environ.get("MAX_ACTIVE_TRADES", "5")))
    # RISK_PER_TRADE_PCT kaldırıldı — gerçek risk otomatik hesaplanır
    @classmethod
    def risk_per_trade_pct(cls) -> float:
        """Gerçek max kayip % (kasa bazı): (1/MAX_ACTIVE_TRADES) x LEVERAGE x SL_ABOVE_ENTRY_PCT"""
        return round((1.0 / cls.MAX_ACTIVE_TRADES) * cls.LEVERAGE * cls.SL_ABOVE_ENTRY_PCT, 2)
    SL_ABOVE_ENTRY_PCT           = _p("SL_ABOVE_ENTRY_PCT",          15.0)
    BREAKEVEN_DROP_PCT           = _p("BREAKEVEN_DROP_PCT",          5.0)
    TSL_ACTIVATION_DROP_PCT      = _p("TSL_ACTIVATION_DROP_PCT",     8.0)
    TSL_TRAIL_PCT                = _p("TSL_TRAIL_PCT",               4.0)

    # ── Module 4 — Çıkış yalnızca SL / BE / TSL ile ─────────────────
    # ── Module 5 — RE-ENTRY (Fresh Pump Koşulu) ─────────────────────

    # ── Backtest ──────────────────────────────────────────────────────
    BACKTEST_DAYS            = _p("BACKTEST_DAYS",            31)
    BACKTEST_INITIAL_CAPITAL = _p("BACKTEST_INITIAL_CAPITAL", 1000.0)
    BACKTEST_SYMBOLS         = _p("BACKTEST_SYMBOLS", [
        "TRB/USDT", "GAS/USDT", "CYBER/USDT", "LOOM/USDT",
        "YGG/USDT", "VANRY/USDT", "ORDI/USDT", "BIGTIME/USDT",
    ])


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 2 — ANA BOT SINIFI  (PumpSnifferBot)
# ══════════════════════════════════════════════════════════════════════════

class PumpSnifferBot:
    """
    Pump & Dump Reversion canlı botun iskelet sınıfı.
    • Universe tarama   (Module 1)
    • Exhaustion tetik   (Module 2)
    • Risk yönetimi      (Module 3)
    """

    # ─────────────────────────────────────────────────────────────────
    # 2.0  KURUCU
    # ─────────────────────────────────────────────────────────────────
    def __init__(self):
        api_key, api_secret = self._load_credentials()
        self.exchange: ccxt.binance = _make_binance_exchange(
            extra_opts={"apiKey": api_key, "secret": api_secret},
            demo=Config.DEMO_MODE,   # demo.binance.com veya canlı borsa
        )
        self.watchlist: Dict[str, WatchlistItem] = {}
        self.active_trades: Dict[str, TradeRecord] = {}
        self.trade_history: List[TradeRecord] = []
        self._post_exit_price: Dict[str, float] = {}   # sym → son çıkış fiyatı (yeni push takibi)
        self._new_push: Dict[str, bool] = {}            # sym → çıkış sonrası yeni push görüldü mü?
        self._processed_signals: Dict[str, str] = {}    # sym → son sinyal timestamp (Tekilleştirme)
        self._prep_done: Optional[asyncio.Event] = None  # PREP→TRIGGER senkronizasyonu
        self._hedge_mode: Optional[bool] = None          # Hedge/One-way mode cache
        self.running = False

    # ─────────────────────────────────────────────────────────────────
    # 2.0.1  API ANAHTAR YÜKLEME
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def _load_credentials() -> Tuple[str, str]:
        """config.py'den veya ortam değişkenlerinden API anahtarlarını yükle."""
        try:
            import config as cfg
            key    = getattr(cfg, "BINANCE_API_KEY", "")
            secret = getattr(cfg, "BINANCE_API_SECRET", "")
            if key and secret:
                return key, secret
        except ImportError:
            pass

        key    = os.environ.get("BINANCE_API_KEY", "")
        secret = os.environ.get("BINANCE_API_SECRET", "")
        return key, secret

    # ─────────────────────────────────────────────────────────────────
    # 2.0.2  GÜVENLI API ÇAĞRISI YARDIMCISI (retry + rate-limit)
    # ─────────────────────────────────────────────────────────────────
    async def _safe_call(self, coro_func, *args, retries: int = 3, **kwargs):
        """
        Bir async exchange fonksiyonunu güvenli şekilde çağır.
        Network timeout ve rate-limit hatalarında otomatik yeniden dene.
        Coğrafi kısıtlama (HTTP 451) hatalarını yakala ve bildir.
        """
        for attempt in range(1, retries + 1):
            try:
                return await coro_func(*args, **kwargs)
            
            except ccxt.AuthenticationError as e:
                # API key hatası — retry yapma
                log.error(f"🔐 API key hatası: {e}")
                log.error("   Lütfen BINANCE_API_KEY ve BINANCE_API_SECRET kontrolü yapın!")
                raise
            
            except ccxt.PermissionDenied as e:
                # Coğrafi kısıtlama (HTTP 451) — retry yapma
                log.error(f"🚫 Binance erişim engeli (HTTP 451): {e}")
                log.error("   Sunucu coğrafi olarak kısıtlanmış bölgede!")
                log.error("   ⚡ Çözüm 1: Railway.app kullanın (RAILWAY_DEPLOYMENT.md)")
                log.error("   ⚡ Çözüm 2: Türkiye/Asya lokasyonlu VPS")
                raise
            
            except (ccxt.NetworkError, ccxt.RequestTimeout) as e:
                log.warning(f"[Ağ Hatası] Deneme {attempt}/{retries}: {e}")
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)
            
            except ccxt.RateLimitExceeded:
                wait = 5 * attempt
                log.warning(f"[Rate-Limit] {wait}s bekleniyor…")
                await asyncio.sleep(wait)
            
            except ccxt.ExchangeError as e:
                log.error(f"[Exchange Hatası] {e}")
                raise
        
        raise ccxt.NetworkError(f"{retries} deneme sonrası başarısız oldu.")

    # ─────────────────────────────────────────────────────────────────
    # 2.1  MODÜL 1 — UNIVERSE & RADAR
    # ─────────────────────────────────────────────────────────────────

    async def fetch_universe(self) -> List[str]:
        """
        Binance Futures'taki tüm aktif USDT-M çiftlerini getir.
        Major-cap coinleri hariç tut.
        Döndürür: ['SYMBOL/USDT', ...] listesi
        """
        markets = await self._safe_call(self.exchange.load_markets, True)
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
            base = mkt.get("base", "")
            if base in Config.EXCLUDED_BASES:
                continue
            universe.append(sym)
        log.info(f"📡 Universe: {len(universe)} USDT-M futures çifti bulundu.")
        return universe

    async def fetch_ohlcv(self, symbol: str, timeframe: str = "4h",
                          limit: int = 50) -> pd.DataFrame:
        """
        Mum verilerini çek ve DataFrame olarak döndür.
        Sütunlar: timestamp, open, high, low, close, volume
        """
        raw = await self._safe_call(
            self.exchange.fetch_ohlcv, symbol, timeframe, limit=limit
        )
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        return df

    def _remove_live_candle(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        Eğer son mum henüz kapanmamışsa (canlı mum), onu DataFrame'den at.
        Kapanmış mumları korur.
        
        Timeframe'e göre mumun kapanış zamanını hesaplar:
          - Son mumun timestamp'i = mum başlangıcı
          - Mum bitişi = başlangıç + timeframe süresi
          - Eğer şu an < mum bitişi → canlı mum, at
          - Eğer şu an >= mum bitişi → kapanmış mum, koru
        """
        if len(df) == 0:
            return df
        
        # Timeframe süresini hesapla
        tf_str = timeframe.lower()
        if 'h' in tf_str:
            tf_delta = timedelta(hours=int(tf_str.replace('h', '')))
        elif 'm' in tf_str:
            tf_delta = timedelta(minutes=int(tf_str.replace('m', '')))
        elif 'd' in tf_str:
            tf_delta = timedelta(days=int(tf_str.replace('d', '')))
        else:
            tf_delta = timedelta(hours=4)  # Default 4h
        
        # Son mumun timestamp'i (başlangıç zamanı)
        last_candle_start = df.index[-1]
        
        # Mumun kapanış zamanı
        last_candle_end = last_candle_start + tf_delta
        
        # Şu anki zaman (UTC)
        now_utc = datetime.now(timezone.utc)
        
        # Eğer mum henüz kapanmadıysa (şu an < kapanış zamanı), canlı mumdur → at
        if now_utc < last_candle_end:
            log.debug(f"  Canlı mum tespit edildi ({last_candle_start}), atılıyor...")
            return df.iloc[:-1]
        else:
            # Mum zaten kapanmış, tüm veriyi döndür
            return df

    async def detect_pump(self, symbol: str) -> Optional[WatchlistItem]:
        """
        Module 1 — THE RADAR: Son 6×4H mumda (24 saatlik rolling pencere)
        net yükseliş >= %30 ve en az 4 yeşil mum kontrolü.

        Koşullar:
        1. Son 6×4H mumda en az 4 yeşil mum olmalı
        2. rolling_high - rolling_low arası >= %30 kazanç
        3. 6 mumdaki toplam hacim >= 10M USDT (kod içinde kontrol edilmiyor, opsiyonel)
        """
        n = Config.PUMP_WINDOW_CANDLES  # 6
        try:
            df_4h = await self.fetch_ohlcv(symbol, Config.TIMEFRAME, limit=n + 5)
            df_4h = self._remove_live_candle(df_4h, Config.TIMEFRAME)  # Canlı mumu doğru şekilde tespit et ve at
        except Exception as e:
            log.debug(f"  {symbol} {Config.TIMEFRAME.upper()} veri çekilemedi: {e}")
            return None

        if len(df_4h) < n + 1:
            return None

        # Son n kapanan mum (en son mum canlı olabilir — haricel)
        window = [df_4h.iloc[-(n + 1) + k] for k in range(n)]

        if any(c["low"] <= 0 or pd.isna(c["high"]) for c in window):
            return None

        # Koşul 1: En az 4 yeşil mum (sıralı olması şart değil)
        green_count = sum(1 for c in window if c["close"] > c["open"])
        if green_count < Config.PUMP_MIN_GREEN_COUNT:  # 4
            return None

        # Koşul 2: 1. mumun gövde tabanı → giriş mumunun kapanışı >= PUMP_MIN_PCT
        # pump_start_ref : 1. mum kırmızıysa close, yeşilse open  (wick dahil etme)
        # entry_close    : giriş kırmızı mumunun kapanışı — pump hala ayakta mı diye kontrol
        pump_high      = max(c["high"] for c in window)
        pump_start_ref = min(window[0]["open"], window[0]["close"])  # Gövde tabanı
        pump_start_low = window[0]["low"]   # WatchlistItem/rapor için saklanır
        entry_close    = df_4h.iloc[-1]["close"]   # giriş mumu kapanışı
        if pump_start_ref <= 0:
            return None
        net_gain_pct   = (entry_close - pump_start_ref) / pump_start_ref * 100.0
        if net_gain_pct < Config.PUMP_MIN_PCT:
            return None

        return WatchlistItem(
            symbol=symbol,
            pump_pct=round(net_gain_pct, 2),
            pump_low=pump_start_low,
            pump_high=pump_high,
            added_at=datetime.now(timezone.utc).isoformat(),
        )


    async def scan_universe(self):
        """
        Module 1 — THE RADAR: Tüm universe'ü tara → Top 10 rolling pump (24H/6×4H) → watchlist.
        Son 6×4H mumda (24 saat) en yüksek %30+ pump yapan 10 coin izlenir.
        """
        universe = await self.fetch_universe()
        log.info(f"🔍 {len(universe)} coin taranıyor "
                 f"(pump ≥ %{Config.PUMP_MIN_PCT}, "
                 f"{Config.PUMP_WINDOW_CANDLES}×{Config.TIMEFRAME.upper()} bazlı)…")

        all_pumps: List[WatchlistItem] = []

        batch_size = 8
        for i in range(0, len(universe), batch_size):
            batch = universe[i : i + batch_size]
            tasks = [self.detect_pump(sym) for sym in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for sym, result in zip(batch, results):
                if isinstance(result, Exception):
                    continue
                if result is not None:
                    all_pumps.append(result)

            await asyncio.sleep(0.5)

        # TOP 10 en yüksek kazançlıları seç
        all_pumps.sort(key=lambda x: x.pump_pct, reverse=True)
        top_n = all_pumps[:Config.TOP_N_GAINERS]

        # Watchlist güncelle — aktif trade olanlar DA dahil (reentry destekli)
        new_watchlist: Dict[str, WatchlistItem] = {}
        for item in top_n:
            new_watchlist[item.symbol] = item
            tag = "(TRADE AÇİK)" if item.symbol in self.active_trades else ""
            log.info(
                f"  🚨 TOP GAINER: {item.symbol}  |  "
                f"+{item.pump_pct:.1f}%  |  "
                f"Zirve: {item.pump_high:.6f}  {tag}"
            )
        # Eski watchlist'teki coinleri koru — scan arasında watchlist boşalıp
        # reentry fırsatını kaçırmamak için
        for sym, item in self.watchlist.items():
            if sym not in new_watchlist:
                new_watchlist[sym] = item
                log.info(f"  📌 KORUNAN: {sym} (önceki scan'den)")
        self.watchlist = new_watchlist
        log.info(f"📋 Aktif Watchlist (Top {Config.TOP_N_GAINERS}): {len(self.watchlist)} coin")

    # ─────────────────────────────────────────────────────────────────
    # 2.2  MODÜL 2 — EXHAUSTION TRIGGER (4H Short Giriş Mantığı)
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def check_entry_signal(df: pd.DataFrame, pump_high: float, reentry: bool = False) -> dict:
        """
        Module 2 — THE TRIGGER: Pump sonrası ilk KIRMIZI 4H mum kapanışında SHORT.

        KOŞULLAR:
        1. Mevcut 4H mum KIRMIZI kapanmalı (close < open).
        2. Fiyat pump zirvesinin altında olmalı (peak teyidi).
        Pump tespiti (detect_pump) zaten son 4 4H mumun yeşil + %30+ yükseliş
        olduğunu doğrulamaktadır; burada tekrar kontrol gerekmez.
        """
        result = {
            "triggered": False,
            "score": 0,
            "entry_price": 0.0,
            "entry_candle_open": 0.0,
            "reasons": [],
        }

        if len(df) < 2:
            return result

        # ── KOŞUL 0: Tazelik Kontrolü (Freshness Window) — Maks 5 Dakika ──────
        # CCXT timestamp'i mumun BAŞLANGIÇ zamanıdır. (Örn: 16:00:00)
        # Kapanış zamanı = başlangıç + timeframe. (Örn: 20:00:00)
        candle_start_dt = df.index[-1]
        
        # Timeframe'e göre süre hesapla
        tf_str = Config.TIMEFRAME.lower()
        if 'h' in tf_str:
            tf_delta = timedelta(hours=int(tf_str.replace('h', '')))
        elif 'm' in tf_str:
            tf_delta = timedelta(minutes=int(tf_str.replace('m', '')))
        elif 'd' in tf_str:
            tf_delta = timedelta(days=int(tf_str.replace('d', '')))
        else:
            tf_delta = timedelta(hours=4) # Default 4h
            
        candle_end_dt = candle_start_dt + tf_delta
        now_utc = datetime.now(timezone.utc)
        diff_mins = (now_utc - candle_end_dt).total_seconds() / 60.0
        
        if diff_mins > 5.0:
            result["reasons"].append(f"BAYAT SİNYAL ({diff_mins:.1f} dk önce kapandı) — Fırsat kaçtı (5dk kuralı)")
            return result
        # ──────────────────────────────────────────────────────────────────

        curr = df.iloc[-1]  # en son kapanan 4H mum

        # KOŞUL 1: Kırmızı mum (close < open)
        if curr["close"] >= curr["open"]:
            result["reasons"].append("YEŞİL MUM — giriş yok (kırmızı bekleniyor)")
            return result

        # KOŞUL 1b: Solid Red — gövde en az %2 (doji filtresi)
        red_body_pct = (curr["open"] - curr["close"]) / curr["open"] * 100.0
        if red_body_pct < Config.ENTRY_RED_BODY_MIN_PCT:
            result["reasons"].append(f"ZAYIF KIRMIZI (gövde %{red_body_pct:.1f} < %{Config.ENTRY_RED_BODY_MIN_PCT}) — doji, giriş yok")
            return result
        # KOŞUL 2: Pump zirvesinin altına düşmüş olmalı (peak teyidi)
        if curr["close"] >= pump_high:
            result["reasons"].append("PUMP ZİRVESİ GEÇİLMEDİ — fiyat hâlâ zirve üstünde")
            result["new_peak"] = curr["high"]
            return result

        # KOŞUL 3: Giriş öncesi mum YEŞİL olmalı (trend dönüşü teyidi)
        if len(df) >= 2:
            prev = df.iloc[-2]
            if prev["close"] <= prev["open"]:
                result["reasons"].append("ÖNCEKİ MUM YEŞİL DEĞİL — giriş yok")
                return result

            # KOŞUL 3b: ANTI-ROCKET FİLTRE — önceki tek mum >= %30 çıktıysa giriş yok
            # Tek mumda devasa pump = sahte düşüş riski (fiyat pump öncesine dönebilir).
            # Config.ANTI_ROCKET_SINGLE_CANDLE_PCT (varsayılan: %30)
            prev_body_pct = (prev["close"] - prev["open"]) / prev["open"] * 100.0
            if prev_body_pct >= Config.ANTI_ROCKET_SINGLE_CANDLE_PCT:
                result["reasons"].append(
                    f"ANTI-ROCKET: Önceki mum tek başına %{prev_body_pct:.1f} çıktı "
                    f"(≥%{Config.ANTI_ROCKET_SINGLE_CANDLE_PCT}) — sahte düşüş riski, giriş yok"
                )
                return result

        # Tüm koşullar sağlandı → SHORT sinyali
        result["triggered"] = True
        result["score"] = 1
        result["entry_price"] = curr["close"]
        result["entry_candle_open"] = curr["open"]
        result["signal_ts"] = df.index[-1]  # Sinyal mumunun kapanış zamanı
        result["reasons"].append("KIRMIZI MUM ✓ → SHORT")
        return result

    def calculate_position(self, equity: float, entry_price: float,
                           pump_high: float) -> dict:
        """
        Module 3: Pozisyon büyüklüğü ve SL hesapla.

        KESİN ORANSAL BOYUTLAMA — bakiyeden bağımsız:
          pos_margin = equity / MAX_ACTIVE_TRADES  (%20 sabit dilim)
          leverage   = Config.LEVERAGE             (daima 3x, asla artmaz)

        Örnekler:
          equity=1000$ → marjin=200$, notional=600$
          equity=200$  → marjin=40$,  notional=120$
          equity=100$  → marjin=20$,  notional=60$

        NOT: Sadece Binance MIN_NOTIONAL (5$) kontrolü caller tarafında yapılır.
        """
        leverage   = Config.LEVERAGE  # Sabit 3x — düşen bakiyede artırılmaz
        sl         = entry_price * (1 + Config.SL_ABOVE_ENTRY_PCT / 100.0)
        pos_margin = equity / Config.MAX_ACTIVE_TRADES  # Her zaman %20 dilim
        notional   = pos_margin * leverage
        qty        = notional / entry_price if entry_price > 0 else 0

        return {
            "sl": sl,
            "position_size_usdt": pos_margin,
            "notional_usdt": notional,
            "qty": qty,
            "leverage": leverage,
        }

    async def _cancel_algo_orders(self, symbol: str, retry: bool = True) -> bool:
        """
        FULL ANNIHILATION v6.0
        Binance Futures'ta emirler 2 sekmeye ayrılır:
          - Basic      : Limit/Market → standart fetch_open_orders görür
          - Conditional: STOP_MARKET, TAKE_PROFIT_MARKET (closePosition=True)
                         → standart çağrılar GÖRMEZ, explicit params gerektirir

        Aşama 1 → Basic sekme temizliği   (cancel_all_orders)
        Aşama 2 → Conditional sekme imhası (STOP_MARKET + TAKE_PROFIT_MARKET
                                              explicit fetch → ID bazı tek tek)
        Aşama 3 → Ultimate Nuke             (fapiPrivateDeleteAllOpenOrders)
        Doğrulama → Temiz mi? Değilse retry döngüsü (max 3 tur)
        """
        max_rounds = 3 if retry else 1

        # Market ID'sini al (BTCUSDT formatı, slash'siz)
        try:
            mkt_id = self.exchange.market(symbol)["id"]
        except Exception:
            mkt_id = symbol.replace("/USDT:USDT", "USDT").replace("/USDT", "USDT")

        async def _cancel_orders_by_type(order_type: str) -> int:
            """Conditional emirleri tip bazında çekip ID ile sil. Kaç emir silindi döndür."""
            count = 0
            try:
                orders = await self._safe_call(
                    self.exchange.fetch_open_orders, symbol,
                    params={"type": order_type, "stop": True}
                )
                for order in (orders or []):
                    oid = order.get("id")
                    if not oid:
                        continue
                    try:
                        await self._safe_call(
                            self.exchange.cancel_order, oid, symbol,
                            params={"type": order_type, "stop": True}
                        )
                        count += 1
                        log.debug(f"  🟥 Conditional iptal: {symbol} {order_type} ID:{oid}")
                    except Exception as e:
                        if "-2011" not in str(e):  # Zaten iptal
                            log.debug(f"  ⚠️ ID iptal hatası ({oid}): {e}")
            except Exception as e:
                log.debug(f"  ⚠️ fetch {order_type} hatası ({symbol}): {e}")
            return count

        for round_num in range(1, max_rounds + 1):
            cleaned = 0

            # ── Aşama 1: Basic sekme — standart cancel_all ────────────────────
            try:
                await self._safe_call(self.exchange.cancel_all_orders, symbol)
            except Exception:
                pass

            # ── Aşama 2: Conditional sekme — explicit tip bazı imha ──────────
            cleaned += await _cancel_orders_by_type("STOP_MARKET")
            cleaned += await _cancel_orders_by_type("TAKE_PROFIT_MARKET")
            cleaned += await _cancel_orders_by_type("STOP")           # bazı ccxt versiyonları
            cleaned += await _cancel_orders_by_type("TAKE_PROFIT")    # dönüşüm alternatifleri

            await asyncio.sleep(0.4)

            # ── Aşama 3: Ultimate Nuke — arka kapı fapi toplu silme ────────
            try:
                await self.exchange.fapiPrivateDeleteAllOpenOrders({"symbol": mkt_id})
            except Exception:
                pass

            await asyncio.sleep(0.5)  # Binance matching engine sync

            # ── Doğrulama — Basic + Conditional birlikte kontrol ────────────
            try:
                remaining_basic = await self._safe_call(
                    self.exchange.fetch_open_orders, symbol
                ) or []
                remaining_stop  = await self._safe_call(
                    self.exchange.fetch_open_orders, symbol,
                    params={"type": "STOP_MARKET", "stop": True}
                ) or []
                remaining = remaining_basic + remaining_stop

                if not remaining:
                    if cleaned > 0:
                        log.info(f"  🗑️ Full Annihilation OK: {symbol} ({cleaned} emir temizlendi)")
                    return True

                if round_num < max_rounds:
                    log.warning(
                        f"  ⚠️ {symbol}: {len(remaining)} emir hala açık — "
                        f"tur {round_num}/{max_rounds}, tekrar..."
                    )
                    await asyncio.sleep(1.0)
                else:
                    log.warning(
                        f"  ❌ {symbol}: {len(remaining)} emir {max_rounds} turda silinemedi — "
                        f"RAM SL devreye girecek."
                    )
            except Exception:
                return True  # Doğrulama yapılamadı, iyimser devam

        return False

    async def _detect_position_mode(self) -> bool:
        """
        Binance hesabının Hedge Mode'da olup olmadığını tespit eder.
        Sonucu cache'ler — sadece ilk çağrıda Binance'e gider.
        Returns: True = Hedge Mode, False = One-Way Mode
        """
        if self._hedge_mode is not None:
            return self._hedge_mode
        try:
            resp = await self._safe_call(
                self.exchange.fapiPrivateGetPositionSideDual
            )
            self._hedge_mode = bool(resp.get("dualSidePosition", False))
        except Exception as e:
            log.warning(f"⚠️ Position mode tespit edilemedi: {e} — One-Way varsayılıyor.")
            self._hedge_mode = False
        mode_str = "HEDGE MODE 🔀" if self._hedge_mode else "ONE-WAY MODE ↔️"
        log.info(f"📍 Binance Position Mode: {mode_str}")
        return self._hedge_mode

    async def open_short(self, symbol: str, entry_price: float,
                         pump_item: WatchlistItem, equity: float,
                         entry_candle_open: float = 0.0) -> Optional[TradeRecord]:
        """
        Module 3: SHORT pozisyon aç.

        SL  : Giriş fiyatının %15 üstü (entry × 1.15)
        TSL : %8 düşüşte aktif — SL = lowest_low × 1.03 (otomatik izler)
        """
        if equity < 100.0:
            log.warning(f"⛔ EQUİTY < 100$ ({equity:.0f}$) — {symbol} atlandı.")
            return None

        if len(self.active_trades) >= Config.MAX_ACTIVE_TRADES:
            log.warning(f"⛔ MAX_ACTIVE_TRADES ({Config.MAX_ACTIVE_TRADES}) aşıldı — "
                        f"{symbol} atlandı.")
            return None

        pos = self.calculate_position(equity, entry_price, pump_item.pump_high)

        trade = TradeRecord(
            symbol=symbol,
            side="SHORT",
            entry_time=datetime.now(timezone.utc).isoformat(),
            entry_price=entry_price,
            stop_loss=pos["sl"],
            initial_stop_loss=pos["sl"],
            tp1_price=0.0,          # TSL ile yönetilir — sabit TP yok
            tp2_price=0.0,
            position_size_usdt=pos["position_size_usdt"],
            remaining_pct=1.0,
            pump_pct=pump_item.pump_pct,
            pump_high=pump_item.pump_high,
            pump_low=pump_item.pump_low,
            entry_candle_open=entry_candle_open or entry_price,
            leverage=pos["leverage"],
        )

        # ── Exchange emir gönderimi ───────────────────────────────────
        order_placed = False  # Market emri gerçekten açıldı mı?
        try:
            await self._safe_call(self.exchange.load_markets)
            market      = self.exchange.markets.get(symbol, {})
            price_prec  = get_digits(market.get("precision", {}).get("price"))
            amount_prec = get_digits(market.get("precision", {}).get("amount"))

            qty = round(pos["qty"], amount_prec)
            calculated_qty = qty  # Log için orijinal değeri sakla

            # ── maxQty kontrolü (-4005 fix) ───────────────────────────
            limits  = market.get("limits", {})
            # limits.amount.max  → genel pozisyon limiti
            # limits.market.max  → market emrine özel limit (daha kısıtlayıcı olabilir)
            max_qty_amount = (limits.get("amount") or {}).get("max")
            max_qty_market = (limits.get("market")  or {}).get("max")
            caps = [v for v in [max_qty_amount, max_qty_market] if v is not None]
            max_qty = float(min(caps)) if caps else None

            if max_qty and qty > max_qty:
                qty = round(max_qty, amount_prec)

            log.info(
                f"  🧮 {symbol} Emir Hazırlığı: "
                f"Hesaplanan={calculated_qty}  "
                f"MaxLimit={max_qty if max_qty else 'limitsiz'}  "
                f"Girilecek={qty}"
            )

            if qty * entry_price < Config.MIN_NOTIONAL_USDT:
                log.warning(f"  ⚠️ {symbol}: Notional < {Config.MIN_NOTIONAL_USDT} USDT — atlanıyor.")
                return None

            # Margin modunu ISOLATED olarak ayarla (CROSS değil)
            try:
                await self._safe_call(self.exchange.set_margin_mode, "isolated", symbol)
            except ccxt.ExchangeError as e:
                if "-4046" not in str(e):
                    log.warning(f"  ⚠️ Margin mode ayarlanamadı ({symbol}): {e}")

            await self._safe_call(self.exchange.set_leverage, pos["leverage"], symbol)

            # Position mode (hedge vs one-way) belirle — emri doğru params ile gönder
            hedge = await self._detect_position_mode()

            # İşlem açılmadan HEMEN ÖNCE eski algo emirleri temizle (-4130 fix)
            await self._cancel_algo_orders(symbol)

            if hedge:
                open_params = {"positionSide": "SHORT"}
                sl_params   = {"stopPrice": None, "positionSide": "SHORT",
                               "closePosition": True, "workingType": "MARK_PRICE"}
            else:
                open_params = {"reduceOnly": False}
                sl_params   = {"stopPrice": None, "closePosition": True,
                               "workingType": "MARK_PRICE"}

            # ── Market emri — 3'lü Geniş Ağ Retry (Catch-All) ─────────────────
            # Mantık: SADECE kalıcı hatalarda iptal et,
            #         bunlar dışındaki HER HATADA (-1000, timeout, CCXT obje vb.) tekrar dene.
            FATAL_ERRORS = ["-4005", "-2019", "-1102", "-4003",
                            "insufficient", "margin", "max quantity", "balance"]
            max_retries = 3
            order = None
            for attempt in range(max_retries):
                try:
                    order = await self._safe_call(
                        self.exchange.create_order,
                        symbol, "market", "sell", qty,
                        params=open_params
                    )
                    order_placed = True
                    log.info(f"  📤 Market SHORT emir: {order.get('id', 'N/A')} "
                             f"(deneme {attempt+1}/{max_retries})")
                    break  # Başarılı — döngüden çık
                except Exception as e:
                    err = str(e).lower()
                    if any(f.lower() in err for f in FATAL_ERRORS):
                        # Kalıcı hata — tekrar denemek işe yaramaz
                        log.error(f"  ❌ Kalıcı/Kritik emir hatası ({symbol}): {e}")
                        break
                    else:
                        # Anlık hata (-1000, timeout, CCXT obje, ağ vs.) — tekrar dene
                        log.warning(
                            f"  ⚠️ Anlık hata/gecikme — "
                            f"deneme {attempt+1}/{max_retries} ({symbol}): {str(e)[:80]}"
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1.5 * (attempt + 1))  # 1.5s, 3s

            if not order_placed:
                log.warning(f"  ⛔ {symbol}: Market emri {max_retries} denemede başarısız — trade kaydı oluşturulmadı.")
                return None

            await self._cancel_algo_orders(symbol)

            sl_price = round(pos["sl"], price_prec)
            sl_params["stopPrice"] = sl_price
            try:
                await self._safe_call(
                    self.exchange.create_order,
                    symbol, "stop_market", "buy", None,
                    params=sl_params
                )
                log.info(f"  🟥 SL koyuldu: {sl_price:.{price_prec}f}")
            except ccxt.ExchangeError as e:
                if "-4130" in str(e):
                    await self._cancel_algo_orders(symbol)
                    await self._safe_call(
                        self.exchange.create_order,
                        symbol, "stop_market", "buy", None,
                        params=sl_params
                    )
                else:
                    raise

        except Exception as e:
            log.error(f"  ❌ Emir gönderilemedi ({symbol}): {e}")

        # Market emri gönderilmediyse active_trades'e ekleme — hayalet trade önlemi
        if not order_placed:
            log.warning(f"  ⛔ {symbol}: Market emri başarısız — trade kaydı oluşturulmadı.")
            return None
        self.active_trades[symbol] = trade
        log.info(
            f"  ✅ SHORT AÇILDI [{('DEMO 🧪' if Config.DEMO_MODE else 'CANLI ⚠️')}]: {symbol}\n"
            f"     Giriş : {entry_price:.6f}\n"
            f"     SL    : {pos['sl']:.6f}  (+{Config.SL_ABOVE_ENTRY_PCT}% giriş üstü)\n"
            f"     TSL   : %{Config.TSL_ACTIVATION_DROP_PCT} düşüşte aktif → lowest_low × {1 + Config.TSL_TRAIL_PCT/100:.2f}\n"
            f"     Boyut : {pos['position_size_usdt']:.4f} USDT  "
            f"(x{pos['leverage']} → {pos['notional_usdt']:.4f} notional)"
        )
        
        # 📲 Telegram bildirim
        try:
            notifier.notify_trade_open(
                symbol=symbol,
                side="SHORT",
                amount=pos["qty"],
                price=entry_price,
                margin=pos["position_size_usdt"]
            )
        except Exception as e:
            log.debug(f"📵 Telegram bildirim hatası (görmezden gelindi): {e}")
        
        return trade

    # ─────────────────────────────────────────────────────────────────
    # 2.3.1  FİZİKSEL BİNANCE STOP EMRİ GÜNCELLEME YARDIMCISI
    # ─────────────────────────────────────────────────────────────────

    async def _update_binance_sl(self, symbol: str, new_sl_price: float):
        """
        Binance'teki mevcut STOP_MARKET emrini iptal edip yeni fiyattan tekrar oluşturur.
        BE / TSL tetiklendiğinde çağrılır — SL sadece RAM'de değil, borsada da güncellenir.

        v3.8: -4130 hatası için retry mekanizması eklendi.
        """
        try:
            await self._safe_call(self.exchange.load_markets)
            market     = self.exchange.markets.get(symbol, {})
            price_prec = get_digits(market.get("precision", {}).get("price"))
            sl_rounded = round(new_sl_price, price_prec)

            # 1) Eski stop emrini sil
            await self._cancel_algo_orders(symbol, retry=True)
            await asyncio.sleep(0.2)  # Binance senkronizasyon bekleme

            # 2) Yeni stop emrini koy
            try:
                await self._safe_call(
                    self.exchange.create_order,
                    symbol, "stop_market", "buy", None,
                    params={
                        "stopPrice"    : sl_rounded,
                        "closePosition": True,
                        "workingType"  : "MARK_PRICE",
                    }
                )
                log.info(f"  🔄 SL GÜNCELLENDI (Binance): {symbol}  → {sl_rounded:.{price_prec}f}")
            except ccxt.ExchangeError as e:
                if "-4130" in str(e):
                    # -4130: Orphan stop hala duruyor — force temizle ve tekrar dene
                    log.warning(f"  ⚠️ -4130 yakalandı, orphan cleanup + retry: {symbol}")
                    await self._cancel_algo_orders(symbol, retry=True)
                    await asyncio.sleep(0.3)
                    await self._safe_call(
                        self.exchange.create_order,
                        symbol, "stop_market", "buy", None,
                        params={
                            "stopPrice"    : sl_rounded,
                            "closePosition": True,
                            "workingType"  : "MARK_PRICE",
                        }
                    )
                    log.info(f"  🔄 SL GÜNCELLENDI (retry sonrası): {symbol}  → {sl_rounded:.{price_prec}f}")
                else:
                    raise
        except Exception as e:
            log.error(f"  ❌ Binance SL güncelleme hatası ({symbol}): {e}")

    # ─────────────────────────────────────────────────────────────────
    # 2.3.2  FİZİKSEL MARKET CLOSE YARDIMCISI
    # ─────────────────────────────────────────────────────────────────

    async def _market_close_position(self, symbol: str):
        """
        Binance'teki açık SHORT pozisyonu kapatır (market buy, reduceOnly).
        Yeşil mum acil çıkışlarında (GREEN-10 / 2xGREEN-LOSS) ve SL/TSL-HIT'te çağrılır.
        """
        try:
            # Önce algo emirleri temizle (hayalet stop'lar kalmasın)
            await self._cancel_algo_orders(symbol)

            # Açık pozisyon miktarını Binance'ten al
            positions = await self._safe_call(self.exchange.fetch_positions, [symbol])
            open_qty = 0.0
            for pos in positions:
                if pos.get("symbol") == symbol and abs(float(pos.get("contracts", 0))) > 0:
                    open_qty = abs(float(pos.get("contracts", 0)))
                    break

            if open_qty > 0:
                await self._safe_call(
                    self.exchange.create_order,
                    symbol, "market", "buy", open_qty,
                    params={"reduceOnly": True}
                )
                # İşlem kapandıktan HEMEN SONRA tekrar temizle
                await self._cancel_algo_orders(symbol)
                log.info(f"  📤 MARKET CLOSE: {symbol}  Miktar: {open_qty}")
            else:
                log.info(f"  ℹ️ {symbol}: Binance'te açık pozisyon bulunamadı (zaten kapanmış).")

        except Exception as e:
            log.error(f"  ❌ Market close hatası ({symbol}): {e}")

    # ─────────────────────────────────────────────────────────────────
    # 2.3.3  TRADE YÖNETİMİ (Fiziksel Binance Emirleriyle)
    # ─────────────────────────────────────────────────────────────────

    async def manage_open_trades(self, equity: float):
        """
        The Shadow Tracker v4.0 — TICKER BAZLI Dinamik Stop-Loss Yönetimi.

        ÖNCEKİ SORUNLAR VE ÇÖZÜMLER:
          • dict iteration crash      → list() kopyası üzerinden iterasyon
          • Phantom Stop (fitil)     → OHLCV yerine TICKER (mark price) kullanımı
          • -4130 orphan stop         → Kesin emir hiyerarşisi (önce temizle, sonra koy)
          • Yanlış PnL (double-close) → Binance pozisyon kontrolü + gerçek çıkış fiyatı

        Stage 1 — Breakeven  : %{BREAKEVEN_DROP_PCT} düşüşte SL = entry
        Stage 2 — TSL Aktif  : %{TSL_ACTIVATION_DROP_PCT} düşüşte Trailing Stop devreye girer
        Stage 3 — SL Kontrol : current_price >= SL → fiziksel market close
        Stage 4 — Zararda yeşil mum → fiziksel market close (sadece KAPANMIŞ mumlar)

        Stage 1-3: TICKER (mark/last price) kullanır — OHLCV çekmez.
        Stage 4  : Sadece bu aşamada OHLCV çeker (kapanmış mum kontrolü).
        """
        closed = []

        # ── KURAL 1: Async-safe iterasyon ──────────────────────────────
        for sym, trade in list(self.active_trades.items()):
            try:
                # ── KURAL 2: OHLCV yerine TICKER — anlık mark/last price ──
                ticker = await self._safe_call(self.exchange.fetch_ticker, sym)
                if not ticker:
                    continue
                current_price = ticker.get("mark") or ticker.get("last")
                if current_price is None:
                    continue
                current_price = float(current_price)

                old_sl = trade.stop_loss  # SL değişimini takip etmek için

                # ── Stage 1: Breakeven — düşüş >= %BREAKEVEN_DROP_PCT → SL = entry ─
                if not trade.breakeven_triggered:
                    drop_pct = (trade.entry_price - current_price) / trade.entry_price * 100.0
                    if drop_pct >= Config.BREAKEVEN_DROP_PCT:
                        trade.stop_loss = trade.entry_price
                        trade.breakeven_triggered = True
                        trade.sl_moved_to_be = True
                        log.info(f"  ⚡ BREAKEVEN: {sym}  Düşüş: %{drop_pct:.1f}  "
                                 f"SL → {trade.entry_price:.6f}")
                        try:
                            notifier.send(f"⚡ BREAKEVEN\n🪙 {sym}\n📉 Düşüş: {drop_pct:.1f}%\n🛡️ SL → Giriş fiyatı")
                        except Exception:
                            pass

                # ── Stage 2: TSL — düşüş >= %TSL_ACTIVATION_DROP_PCT → trailing ───
                drop_pct = (trade.entry_price - current_price) / trade.entry_price * 100.0
                if not trade.tsl_active:
                    if drop_pct >= Config.TSL_ACTIVATION_DROP_PCT:
                        trade.tsl_active = True
                        trade.lowest_low_reached = current_price
                        new_sl = trade.lowest_low_reached * (1 + Config.TSL_TRAIL_PCT / 100.0)
                        trade.stop_loss = min(trade.stop_loss, new_sl)
                        log.info(f"  🎯 TSL AKTİF: {sym}  Düşüş: %{drop_pct:.1f}  "
                                 f"Low: {trade.lowest_low_reached:.6f}  SL → {trade.stop_loss:.6f}")
                        try:
                            notifier.send(f"🎯 TSL AKTİF\n🪙 {sym}\n📉 Düşüş: {drop_pct:.1f}%\n🛡️ Trailing stop başlatıldı")
                        except Exception:
                            pass
                else:
                    # TSL zaten aktif — yeni dip takibi
                    if current_price < trade.lowest_low_reached:
                        trade.lowest_low_reached = current_price
                        new_sl = trade.lowest_low_reached * (1 + Config.TSL_TRAIL_PCT / 100.0)
                        trade.stop_loss = min(trade.stop_loss, new_sl)
                        log.info(f"  📉 TSL GÜNCELLE: {sym}  "
                                 f"YeniLow: {trade.lowest_low_reached:.6f}  SL → {trade.stop_loss:.6f}")

                # ── KURAL 3: SL değiştiyse → ÖNCE temizle, SONRA güncelle ─────
                if trade.stop_loss != old_sl:
                    await self._cancel_algo_orders(sym, retry=True)
                    await asyncio.sleep(0.2)
                    await self._update_binance_sl(sym, trade.stop_loss)

                # ── Stage 3: SL-Hit Kontrolü — current_price >= SL → kapat ────
                if current_price >= trade.stop_loss:
                    # Binance'te gerçek pozisyon var mı kontrol et
                    real_exit_price = None
                    try:
                        positions = await self._safe_call(self.exchange.fetch_positions, [sym])
                        has_position = False
                        for pos in positions:
                            if pos.get("symbol") == sym and abs(float(pos.get("contracts", 0))) > 0:
                                has_position = True
                                break
                        if has_position:
                            # KURAL 3: Önce temizle, sonra kapat
                            await self._cancel_algo_orders(sym, retry=True)
                            await asyncio.sleep(0.2)
                            await self._market_close_position(sym)
                        else:
                            # Binance SL zaten tetiklenmiş — gerçek çıkış fiyatını al
                            log.info(f"  ℹ️ {sym}: Pozisyon zaten Binance SL ile kapanmış.")
                            try:
                                recent_trades = await self._safe_call(
                                    self.exchange.fetch_my_trades, sym, limit=5
                                )
                                if recent_trades:
                                    last_t = recent_trades[-1]
                                    real_exit_price = float(last_t.get("price", current_price))
                            except Exception:
                                pass
                            # Yine de orphan emirleri temizle
                            await self._cancel_algo_orders(sym, retry=False)
                    except Exception:
                        await self._cancel_algo_orders(sym, retry=True)
                        await asyncio.sleep(0.2)
                        await self._market_close_position(sym)

                    exit_p  = real_exit_price if real_exit_price else current_price
                    pnl_pct = (trade.entry_price - exit_p) / trade.entry_price
                    pnl_usd = trade.position_size_usdt * trade.leverage * pnl_pct
                    reason  = "TSL-HIT" if trade.tsl_active else "STOP-LOSS"
                    trade.exit_time   = datetime.now(timezone.utc).isoformat()
                    trade.exit_price  = exit_p
                    trade.exit_reason = reason
                    trade.pnl_pct     = round(pnl_pct * 100, 4)
                    trade.pnl_usdt    = round(pnl_usd, 2)
                    self.trade_history.append(trade)
                    closed.append(sym)
                    self._post_exit_price[sym] = exit_p
                    self._new_push[sym] = False
                    log.info(f"  🔴 {reason}: {sym}  |  PnL: {trade.pnl_usdt:+.2f} USDT")
                    try:
                        notifier.notify_trade_close(sym, reason, trade.pnl_pct, trade.pnl_usdt)
                    except Exception:
                        pass
                    continue  # Stage 3'te kapandı — Stage 4'e geçme

                # ── KURAL 4: Stage 4 İZOLASYONU — Sadece burada OHLCV çek ─────
                # İşlem hâlâ açık → kapanmış mum kontrolü için minimal OHLCV
                try:
                    df_raw = await self.fetch_ohlcv(sym, Config.TIMEFRAME, limit=3)
                    if df_raw.empty:
                        continue
                    df_closed = self._remove_live_candle(df_raw, Config.TIMEFRAME)
                    if df_closed.empty:
                        continue
                    closed_candle = df_closed.iloc[-1]
                except Exception:
                    continue

                # Aynı kapanmış mumu tekrar saymamak için timestamp kontrolü
                candle_ts = str(df_closed.index[-1])
                if candle_ts == trade._last_checked_ts:
                    pass  # Bu mum zaten değerlendirildi
                elif closed_candle["close"] > closed_candle["open"] and closed_candle["close"] > trade.entry_price:
                    trade._last_checked_ts = candle_ts
                    green_body_pct = (closed_candle["close"] - closed_candle["open"]) / closed_candle["open"] * 100.0

                    # Zararda tek yeşil mum gövdesi >= %10 → anında kapat
                    if green_body_pct >= Config.GREEN_LOSS_SINGLE_BODY_PCT:
                        exit_p  = closed_candle["close"]
                        pnl_pct = (trade.entry_price - exit_p) / trade.entry_price
                        pnl_usd = trade.position_size_usdt * trade.leverage * pnl_pct
                        trade.exit_time   = datetime.now(timezone.utc).isoformat()
                        trade.exit_price  = exit_p
                        trade.exit_reason = "GREEN-10"
                        trade.pnl_pct     = round(pnl_pct * 100, 4)
                        trade.pnl_usdt    = round(pnl_usd, 2)
                        self.trade_history.append(trade)
                        closed.append(sym)
                        self._post_exit_price[sym] = exit_p
                        self._new_push[sym] = False
                        # KURAL 3: Önce temizle, sonra kapat
                        await self._cancel_algo_orders(sym, retry=True)
                        await asyncio.sleep(0.2)
                        await self._market_close_position(sym)
                        log.info(f"  🟠 GREEN-10: {sym}  Gövde: %{green_body_pct:.1f}  Close: {exit_p:.6f}  PnL: {trade.pnl_usdt:+.2f} USDT")
                        try:
                            notifier.notify_trade_close(sym, "GREEN-10", trade.pnl_pct, trade.pnl_usdt)
                        except Exception:
                            pass
                        continue

                    # Küçük zararda yeşil → sayacı artır, 2'de kapat
                    trade.consec_green_loss += 1
                    if trade.consec_green_loss >= 2:
                        exit_p  = closed_candle["close"]
                        pnl_pct = (trade.entry_price - exit_p) / trade.entry_price
                        pnl_usd = trade.position_size_usdt * trade.leverage * pnl_pct
                        trade.exit_time   = datetime.now(timezone.utc).isoformat()
                        trade.exit_price  = exit_p
                        trade.exit_reason = "2xGREEN-LOSS"
                        trade.pnl_pct     = round(pnl_pct * 100, 4)
                        trade.pnl_usdt    = round(pnl_usd, 2)
                        self.trade_history.append(trade)
                        closed.append(sym)
                        self._post_exit_price[sym] = exit_p
                        self._new_push[sym] = False
                        # KURAL 3: Önce temizle, sonra kapat
                        await self._cancel_algo_orders(sym, retry=True)
                        await asyncio.sleep(0.2)
                        await self._market_close_position(sym)
                        log.info(f"  🟠 2xGREEN-LOSS: {sym}  Close: {exit_p:.6f}  PnL: {trade.pnl_usdt:+.2f} USDT")
                        try:
                            notifier.notify_trade_close(sym, "2xGREEN-LOSS", trade.pnl_pct, trade.pnl_usdt)
                        except Exception:
                            pass
                        continue
                else:
                    trade._last_checked_ts = candle_ts
                    trade.consec_green_loss = 0  # Kırmızı veya kârda yeşil → sayacı sıfırla

            except Exception as e:
                log.error(f"  Trade yönetim hatası ({sym}): {e}")

        for sym in closed:
            del self.active_trades[sym]

    # ─────────────────────────────────────────────────────────────────
    # 2.4  ZAMAN AYARLI 4H MİMARİSİ  (v3.9)
    #      3 Asenkron Görev: Prep-Scan + Trigger + Manager
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _tf_to_minutes() -> int:
        """Config.TIMEFRAME → dakika cinsinden periyot."""
        tf = Config.TIMEFRAME.lower()
        if tf.endswith("m"):
            return int(tf[:-1])
        if tf.endswith("h"):
            return int(tf[:-1]) * 60
        return 240  # fallback 4h

    @staticmethod
    def _prep_offset_sec() -> int:
        """Timeframe'e göre dinamik PREP offset (kapanıştan kaç saniye önce tara)."""
        tf_min = PumpSnifferBot._tf_to_minutes()
        if tf_min <= 15:  return 2 * 60
        if tf_min <= 30:  return 3 * 60
        if tf_min <= 60:  return 5 * 60
        if tf_min <= 120: return 8 * 60
        return _p("PREP_SCAN_OFFSET_MIN", 5) * 60  # 4h+ — varsayılan 5dk

    @staticmethod
    def _seconds_until_next_close() -> float:
        """Sonraki mum kapanış zamanına kalan saniye (Config.TIMEFRAME'e göre)."""
        period_min = PumpSnifferBot._tf_to_minutes()
        now = datetime.now(timezone.utc)
        total_sec = now.hour * 3600 + now.minute * 60 + now.second + now.microsecond / 1e6
        period_sec = period_min * 60
        elapsed = total_sec % period_sec
        remaining = period_sec - elapsed
        return max(remaining, 0)

    @staticmethod
    def _next_close_utc() -> datetime:
        """Sonraki mum kapanış zamanını datetime olarak döndürür (Config.TIMEFRAME'e göre)."""
        period_min = PumpSnifferBot._tf_to_minutes()
        now = datetime.now(timezone.utc)
        total_min = now.hour * 60 + now.minute
        elapsed_min = total_min % period_min
        remaining_min = period_min - elapsed_min
        return (now.replace(second=0, microsecond=0) + timedelta(minutes=remaining_min))

    # Geriye dönük uyumluluk aliasları
    @staticmethod
    def _seconds_until_next_4h() -> float:
        return PumpSnifferBot._seconds_until_next_close()

    @staticmethod
    def _next_4h_close_utc() -> datetime:
        return PumpSnifferBot._next_close_utc()

    # ── GÖREV 1: PREP_SCAN_LOOP (Hazırlık Radarı) ────────────────────

    async def _prep_scan_loop(self):
        """
        GÖREV 1 — HAZIRLIK RADARI: Universe taraması + watchlist doldurma.

        ÇALIŞMA ZAMANI: Her 4H mum kapanışından TAM 10 DAKİKA ÖNCE çalışır.
          → 23:50, 03:50, 07:50, 11:50, 15:50, 19:50 UTC

        MANTIK:
          1. Sonraki 4H kapanışa kalan süreyi hesapla.
          2. Kapanışa 10 dakika kalana kadar uyu.
          3. scan_universe() çalıştır → watchlist hazırla.
          4. Orphan algo emirleri temizle.
          5. Kapanış saatini geç → sonraki döngüye devam.

        Böylece trigger_loop 4H kapanışında uyanınca watchlist HAZIR olur.
        10 dakika ~300 coin taramak için yeterli süre sağlar.
        """
        PREP_OFFSET_SEC = self._prep_offset_sec()  # Timeframe'e göre dinamik

        while self.running:
            try:
                secs_to_close = self._seconds_until_next_close()
                prep_wait = secs_to_close - PREP_OFFSET_SEC

                if prep_wait > 0:
                    # Henüz prep penceresine girmedik → kapanışa 10dk kalana kadar uyu
                    wake_time = datetime.now(timezone.utc) + timedelta(seconds=prep_wait)
                    log.info(f"⏳ [PREP] Sonraki tarama {wake_time.strftime('%H:%M:%S')} UTC'de "
                             f"({prep_wait:.0f}s sonra)")
                    await asyncio.sleep(prep_wait)
                # else: Zaten prep penceresi içindeyiz → hemen tara

                close_dt = self._next_close_utc()
                prep_min = self._prep_offset_sec() // 60
                log.info(f"🔍 [PREP] {close_dt.strftime('%H:%M')} kapanışına {prep_min}dk kala — "
                         f"Universe taraması başlıyor…")

                # Yeni Event oluştur — bu döngünün trigger'ı bunu bekleyecek
                self._prep_done = asyncio.Event()

                await self.scan_universe()

                # 🧹 ORPHAN CLEANER — Watchlist'te olup active trade'i OLMAYAN coinlerin stoplarını temizle
                for sym in list(self.watchlist.keys()):
                    if sym not in self.active_trades:
                        await self._cancel_algo_orders(sym, retry=False)
                        await asyncio.sleep(0.1)

                # PREP bitti → Trigger'a "watchlist hazır" sinyali ver
                self._prep_done.set()

                now_utc = datetime.now(timezone.utc)
                if now_utc >= close_dt:
                    # PREP taraması kapanış saatinden SONRA bitti
                    log.warning(
                        f"⚠️ [PREP] Tarama tamamlandı — {len(self.watchlist)} coin watchlist'te. "
                        f"UYARI: Tarama {close_dt.strftime('%H:%M')} kapanışından SONRA bitti "
                        f"({now_utc.strftime('%H:%M:%S')} UTC). "
                        f"Trigger zaten ateşlendi, bir sonraki 4H kapanışı bekleniyor.")
                else:
                    secs_left = (close_dt - now_utc).total_seconds()
                    log.info(
                        f"✅ [PREP] Tarama tamamlandı — {len(self.watchlist)} coin watchlist'te. "
                        f"Trigger {close_dt.strftime('%H:%M:%S')} UTC'de ateşlenecek "
                        f"({secs_left:.0f}s sonra).")

                # Kapanış saatini geç → sonraki döngünün TF hesabı doğru olsun
                remaining = self._seconds_until_next_close()
                await asyncio.sleep(remaining + 5)

            except Exception as e:
                log.error(f"🔴 Prep Scan hatası: {e}")
                await asyncio.sleep(60)

    # ── GÖREV 2: TRIGGER_LOOP (Keskin Nişancı Girişi) ─────────────────

    async def _trigger_loop(self):
        """
        GÖREV 2 — KESKİN NİŞANCI GİRİŞİ: Watchlist'teki coinlerin son KAPANMIŞ
        mumunu kontrol eder, koşullar uygunsa SHORT açar.

        ÇALIŞMA ZAMANI: Her 4H mum kapanışından TAM 2 SANİYE SONRA çalışır.
          → 00:00:02, 04:00:02, 08:00:02, 12:00:02, 16:00:02, 20:00:02 UTC

        MANTIK:
          1. Sonraki 4H kapanışa kalan süre + 2 saniye bekle.
          2. Watchlist'teki coinlerin OHLCV'sini çek (limit=3 yeterli).
          3. Canlı mumu at → KAPANMIŞ son mumu al (iloc[-1] after _remove_live_candle).
          4. check_entry_signal → kırmızı mum kontrolü.
          5. Sinyal varsa open_short.
          6. Sonraki 4H kapanışa kadar tekrar uyu.

        NOT: _processed_signals (Tek Kurşun kilidi) kullanılmaya devam eder.
        """
        TRIGGER_OFFSET_SEC = 2  # Kapanıştan 2 saniye sonra

        while self.running:
            try:
                secs_to_close = self._seconds_until_next_close()
                wait_secs = secs_to_close + TRIGGER_OFFSET_SEC

                if wait_secs > 5:
                    trigger_time = datetime.now(timezone.utc) + timedelta(seconds=wait_secs)
                    log.info(f"⏳ [TRIGGER] Sonraki kontrol {trigger_time.strftime('%H:%M:%S')} UTC'de "
                             f"({wait_secs:.0f}s sonra)")

                await asyncio.sleep(wait_secs)

                # PREP taraması henüz bitmemişse bekle (max 120 saniye)
                if self._prep_done and not self._prep_done.is_set():
                    log.info("⏳ [TRIGGER] PREP taraması henüz bitmedi — watchlist hazır olana kadar bekleniyor…")
                    try:
                        await asyncio.wait_for(self._prep_done.wait(), timeout=120)
                        log.info("✅ [TRIGGER] PREP tamamlandı — devam ediliyor.")
                    except asyncio.TimeoutError:
                        log.warning("⚠️ [TRIGGER] PREP 120s içinde bitmedi — mevcut watchlist ile devam ediliyor.")

                log.info(f"🎯 [TRIGGER] {Config.TIMEFRAME.upper()} mum kapandı — {len(self.watchlist)} coin kontrol ediliyor…")

                # Watchlist boş veya tüm slotlar doluysa atla
                if not self.watchlist:
                    log.info("  ℹ️ Watchlist boş — sinyal kontrolü atlanıyor")
                    continue
                if len(self.active_trades) >= Config.MAX_ACTIVE_TRADES:
                    log.info(f"  ℹ️ Tüm slotlar dolu ({Config.MAX_ACTIVE_TRADES}/{Config.MAX_ACTIVE_TRADES}) — atlanıyor")
                    continue

                # Equity al (tüm coinler için tek sefer)
                try:
                    balance = await self._safe_call(self.exchange.fetch_balance)
                    equity = float(balance.get("total", {}).get("USDT", 10_000))
                except Exception:
                    equity = 10_000

                # Watchlist'teki her coini kontrol et — en yüksek pump % önce (büyükten küçüğe)
                sorted_watchlist = sorted(
                    self.watchlist.items(),
                    key=lambda x: x[1].pump_pct,
                    reverse=True
                )
                for sym, item in sorted_watchlist:
                    if sym in self.active_trades:
                        continue
                    if len(self.active_trades) >= Config.MAX_ACTIVE_TRADES:
                        break
                    try:
                        df = await self.fetch_ohlcv(sym, Config.TIMEFRAME,
                                                    limit=Config.BB_LENGTH + 10)
                        df = self._remove_live_candle(df, Config.TIMEFRAME)
                        if df.empty:
                            continue

                        # Module 5: Yeni Push kontrolü (çıkış sonrası yeniden giriş)
                        if sym in self._post_exit_price:
                            curr_high = df.iloc[-1]["high"]
                            if curr_high > self._post_exit_price[sym]:
                                self._new_push[sym] = True
                            if not self._new_push.get(sym, True):
                                log.debug(f"  {sym}: çıkış sonrası yeni push bekleniyor")
                                continue

                        # Kapanmış mumun bilgilerini logla
                        last = df.iloc[-1]
                        candle_color = "🟢 YEŞİL" if last["close"] >= last["open"] else "🔴 KIRMIZI"
                        candle_chg = (last["close"] - last["open"]) / last["open"] * 100.0
                        log.info(f"  📊 {sym}: {candle_color}  O:{last['open']:.6f} → C:{last['close']:.6f}  "
                                 f"({candle_chg:+.2f}%)  H:{last['high']:.6f}  L:{last['low']:.6f}")

                        signal = self.check_entry_signal(df, item.pump_high)

                        # Dinamik peak güncelleme
                        if "new_peak" in signal and signal["new_peak"] > item.pump_high:
                            item.pump_high = signal["new_peak"]
                            log.info(f"  📈 PEAK GÜNCELLEME: {sym}  "
                                     f"Yeni zirve: {item.pump_high:.6f}")

                        if signal["triggered"]:
                            # Sinyal Tekilleştirme (Tek Kurşun Kilidi)
                            sig_ts = str(signal["signal_ts"])
                            if self._processed_signals.get(sym) == sig_ts:
                                log.info(f"  ⏭️  {sym}: Bu mum için sinyal zaten işlendi ({sig_ts})")
                                continue

                            log.info(f"  🎯 [v3.9] SİNYAL: {sym}  |  {'  '.join(signal['reasons'])}")
                            self._processed_signals[sym] = sig_ts

                            await self.open_short(
                                sym, signal["entry_price"], item, equity,
                                entry_candle_open=signal.get("entry_candle_open",
                                                             signal["entry_price"]),
                            )
                        else:
                            # Sinyal tetiklenmedi → NEDEN olduğunu logla
                            reasons = signal.get("reasons", ["Bilinmeyen"])
                            log.info(f"  ❌ {sym}: Giriş YOK — {' | '.join(reasons)}")
                    except Exception as e:
                        log.error(f"  Trigger sinyal hatası ({sym}): {e}")

            except Exception as e:
                log.error(f"🔴 Trigger Loop hatası: {e}")
                await asyncio.sleep(60)

    # ── GÖREV 3: MANAGER_LOOP (Risk Yönetimi) ────────────────────────

    async def _manager_loop(self):
        """
        GÖREV 3 — TRADE MANAGER: SADECE açık trade'leri yönetir (SL/TSL/BE/Green çıkış).
        Her 5 saniyede bir çalışır. Rate limit safe — sadece açık pozisyonlar kontrol edilir.
        Geçmiş fitillere bakmama ve anlık fiyatla TSL/BE hesaplama kuralları korunur.
        """
        while self.running:
            try:
                if not self.active_trades:
                    await asyncio.sleep(Config.MANAGER_INTERVAL_SEC)
                    continue

                try:
                    balance = await self._safe_call(self.exchange.fetch_balance)
                    equity  = float(balance.get("total", {}).get("USDT", 10_000))
                except Exception:
                    equity = 10_000

                await self.manage_open_trades(equity)

            except Exception as e:
                log.error(f"🔴 Trade Manager hatası: {e}")

            await asyncio.sleep(Config.MANAGER_INTERVAL_SEC)

    # ── ANA GİRİŞ NOKTASI ────────────────────────────────────────────

    async def run(self):
        """
        v3.9 — ZAMAN AYARLI MİMARİ ({tf})

        Üç bağımsız asenkron görev eşzamanlı başlatılır:

          GÖREV 1 • prep_scan_loop  : {tf} kapanıştan önce → Universe taraması
          GÖREV 2 • trigger_loop    : {tf} kapanıştan 2sn SONRA → Sinyal kontrolü + SHORT
          GÖREV 3 • manager_loop    : Her 5 saniye → Açık trade yönetimi (TSL/BE/SL)
        """
        self.running = True
        tf           = Config.TIMEFRAME.upper()
        next_close   = self._next_close_utc()
        prep_offset  = self._prep_offset_sec()
        prep_time    = next_close - timedelta(seconds=prep_offset)
        log.info("=" * 75)
        log.info(f"  PUMP & DUMP REVERSION BOT v3.9.4 — ZAMAN AYARLI {tf} MİMARİSİ")
        log.info(f"  Kaldıraç: x{Config.LEVERAGE}  |  "
                 f"Top {Config.TOP_N_GAINERS} Gainer  |  "
                 f"Risk/trade: %{Config.risk_per_trade_pct()}")
        log.info(f"  ⏰ Sonraki {tf} kapanış: {next_close.strftime('%H:%M')} UTC  |  "
                 f"Prep: {prep_time.strftime('%H:%M')} UTC")
        log.info(f"  📡 PREP: kapanışa -{prep_offset//60}dk  |  "
                 f"🎯 TRIGGER: kapanışa +2sn  |  "
                 f"⚡ MANAGER: {Config.MANAGER_INTERVAL_SEC}s")
        log.info("=" * 75)

        try:
            await asyncio.gather(
                self._prep_scan_loop(),
                self._trigger_loop(),
                self._manager_loop(),
            )
        except KeyboardInterrupt:
            log.info("Bot durduruldu (Ctrl+C).")
        finally:
            self.running = False
            await self.exchange.close()


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 3 — BACKTESTER SINIFI
# ══════════════════════════════════════════════════════════════════════════

class Backtester:
    """
    Pump & Dump Reversion stratejisini geçmiş veri üzerinde simüle eder.
    • Bar-by-bar iterasyon
    • Watchlist mantığını simüle eder
    • Giriş / SL / TP1 / TP2 mantığını uygular
    • Detaylı terminal raporu çıkarır
    """

    def __init__(self, symbols: List[str] = None, days: int = None,
                 initial_capital: float = None,
                 start_dt: datetime = None, end_dt: datetime = None):
        self.symbols   = symbols or Config.BACKTEST_SYMBOLS
        self.capital   = initial_capital or Config.BACKTEST_INITIAL_CAPITAL
        self.exchange  = None   # async init'te set edilecek
        self.all_data: Dict[str, pd.DataFrame] = {}
        self.all_data_5m: Dict[str, pd.DataFrame] = {}  # sym → 5m DataFrame (intra-bar sim için)
        self.trades: List[TradeRecord] = []
        self.equity_curve: List[float] = []

        # Tarih aralığı: start_dt/end_dt verilmişse kullan, yoksa days'e göre
        if start_dt is not None and end_dt is not None:
            self.start_dt = start_dt.replace(tzinfo=timezone.utc) if start_dt.tzinfo is None else start_dt
            self.end_dt   = end_dt.replace(tzinfo=timezone.utc)   if end_dt.tzinfo is None else end_dt
        else:
            _days = days or Config.BACKTEST_DAYS
            self.end_dt   = datetime.now(timezone.utc)
            self.start_dt = self.end_dt - timedelta(days=_days)

    # ─────────────────────────────────────────────────────────────────
    # 3.1  VERİ ÇEKME
    # ─────────────────────────────────────────────────────────────────

    async def _init_exchange(self):
        """Public data için exchange bağlantısı (API key gereksiz)."""
        self.exchange = _make_binance_exchange()

    async def _fetch_historical(self, symbol: str) -> pd.DataFrame:
        """
        Belirli bir sembolün tarih aralığındaki 4H verilerini çek.
        Pump window için start_dt'den 6 mum (24 saat) önce başla.
        """
        fetch_start = self.start_dt - timedelta(hours=Config.PUMP_WINDOW_CANDLES * 4)
        since_ms    = int(fetch_start.timestamp() * 1000)
        until_ms    = int(self.end_dt.timestamp() * 1000)
        all_candles = []
        limit = 500
        since_cur = since_ms

        while True:
            try:
                candles = await self.exchange.fetch_ohlcv(
                    symbol, Config.TIMEFRAME, since=since_cur, limit=limit
                )
            except Exception as e:
                log.warning(f"  {symbol} veri çekme hatası: {e}")
                break

            if not candles:
                break
            all_candles.extend(candles)
            last_ts = candles[-1][0]
            if last_ts >= until_ms or len(candles) < limit:
                break
            since_cur = last_ts + 1
            await asyncio.sleep(0.3)

        if not all_candles:
            return pd.DataFrame()

        df = pd.DataFrame(all_candles,
                          columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.drop_duplicates(subset="timestamp", inplace=True)
        df.sort_values("timestamp", inplace=True)
        df.set_index("timestamp", inplace=True)
        # end_dt sonrası barlari kes
        df = df[df.index <= pd.Timestamp(self.end_dt)]
        return df

    async def _fetch_historical_5m(self, symbol: str) -> pd.DataFrame:
        """
        5m granüler veri çek — simulate_intra_bar_exit için.
        Her 4H bar içindeki 48 adet 5m mumu SL/TSL tetikleme hassasiyetiyle tarar.
        """
        fetch_start = self.start_dt - timedelta(hours=Config.PUMP_WINDOW_CANDLES * 4)
        since_ms    = int(fetch_start.timestamp() * 1000)
        until_ms    = int(self.end_dt.timestamp() * 1000)
        all_candles: list = []
        since_cur   = since_ms

        while True:
            try:
                candles = await self.exchange.fetch_ohlcv(
                    symbol, '5m', since=since_cur, limit=1000
                )
            except Exception as e:
                log.warning(f"  {symbol} 5m veri hatası: {e}")
                break
            if not candles:
                break
            all_candles.extend(candles)
            last_ts = candles[-1][0]
            if last_ts >= until_ms or len(candles) < 1000:
                break
            since_cur = last_ts + 1
            await asyncio.sleep(0.2)

        if not all_candles:
            return pd.DataFrame()

        df5 = pd.DataFrame(all_candles,
                           columns=["timestamp","open","high","low","close","volume"])
        df5["timestamp"] = pd.to_datetime(df5["timestamp"], unit="ms", utc=True)
        df5.drop_duplicates(subset="timestamp", inplace=True)
        df5.sort_values("timestamp", inplace=True)
        df5.set_index("timestamp", inplace=True)
        df5 = df5[df5.index <= pd.Timestamp(self.end_dt)]
        return df5

    async def load_data(self):
        """Tüm backtest sembollerinin verisini çek."""
        await self._init_exchange()
        _period = f"{self.days} günlük" if hasattr(self, 'days') else f"{self.start_dt.strftime('%d.%m.%Y')} → {self.end_dt.strftime('%d.%m.%Y')}"
        log.info(f"📥 {len(self.symbols)} sembol için {_period} 4H veri çekiliyor…")

        for sym in self.symbols:
            df = await self._fetch_historical(sym)
            if df.empty:
                log.warning(f"  ⚠️ {sym}: Veri bulunamadı — atlanıyor.")
                continue
            self.all_data[sym] = df
            log.info(f"  ✔ {sym}: {len(df)} mum yüklendi  "
                     f"({df.index[0].strftime('%d.%m.%Y')} → {df.index[-1].strftime('%d.%m.%Y')})")
            # 5m granüler veri (intra-bar SL/TSL simülasyonu için)
            df5 = await self._fetch_historical_5m(sym)
            if not df5.empty:
                self.all_data_5m[sym] = df5
                log.info(f"  ✔ {sym} [5m]: {len(df5)} mum yüklendi")
            await asyncio.sleep(0.3)

        await self.exchange.close()
        log.info(f"📦 Toplam {len(self.all_data)} sembol yüklendi ({len(self.all_data_5m)} adet 5m verisi mevcut).\n")

    # ─────────────────────────────────────────────────────────────────
    # 3.2  5m İNTRA-BAR ÇİKIŞ SİMÜLASYONU
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def simulate_intra_bar_exit(
        bar_4h_ts: "pd.Timestamp",
        trade: "TradeRecord",
        df_5m: "pd.DataFrame",
        be_drop_pct: float,
    ) -> "Optional[dict]":
        """
        Look-ahead bias olmadan 4H bar içindeki 48 adet 5m mumu sırasıyla kontrol eder.

        Teknik gereksinimler:
          • Execution Priority — 5m bar içinde HIGH >= SL → önce STOP (muhafazakar mod).
          • Wick Sensitivity   — SL/TSL tetikleyicisi olarak 5m HIGH ve LOW kullanılır.
          • TSL/BE state trade nesnesine doğrudan yazılır (intra-bar granüler güncelleme).

        Döndürür:
          {"exit_time", "exit_price", "exit_reason"}  — çıkış tetiklendiyse
          None                                         — bu 4H bar içinde çıkış yok
        """
        if df_5m is None or df_5m.empty:
            return None

        bar_end = bar_4h_ts + pd.Timedelta(hours=4)
        mask    = (df_5m.index >= bar_4h_ts) & (df_5m.index < bar_end)
        sub     = df_5m.loc[mask]
        if sub.empty:
            return None

        for ts5, b5 in sub.iterrows():
            # ── Break-even (close bazlı, hassas) ─────────────────────
            if not trade.breakeven_triggered:
                drop_pct = (trade.entry_price - b5["close"]) / trade.entry_price * 100.0
                if drop_pct >= be_drop_pct:
                    trade.stop_loss         = trade.entry_price
                    trade.breakeven_triggered = True
                    trade.sl_moved_to_be    = True

            # ── TSL aktivasyon / güncelleme (low bazlı) ──────────────
            low_drop = (trade.entry_price - b5["low"]) / trade.entry_price * 100.0
            if not trade.tsl_active:
                if low_drop >= Config.TSL_ACTIVATION_DROP_PCT:
                    trade.tsl_active           = True
                    trade.lowest_low_reached   = b5["low"]
                    new_sl = trade.lowest_low_reached * (1 + Config.TSL_TRAIL_PCT / 100.0)
                    trade.stop_loss = min(trade.stop_loss, new_sl)
            else:
                if b5["low"] < trade.lowest_low_reached:
                    trade.lowest_low_reached = b5["low"]
                    new_sl = trade.lowest_low_reached * (1 + Config.TSL_TRAIL_PCT / 100.0)
                    trade.stop_loss = min(trade.stop_loss, new_sl)

            # ── Conservative: HIGH >= SL → derhal çıkış ──────────────
            # (TP ve SL aynı 5m bar'da çakışırsa SL önce kabul edilir)
            if b5["high"] >= trade.stop_loss:
                reason = "TSL-HIT" if trade.tsl_active else "STOP-LOSS"
                return {
                    "exit_time":   ts5.strftime("%d.%m.%Y %H:%M"),
                    "exit_price":  trade.stop_loss,
                    "exit_reason": reason,
                }

        return None  # Bu 4H bar içinde çıkış tetiklenmedi

    # ─────────────────────────────────────────────────────────────────
    # 3.3  PUMP TESPİTİ (statik — geçmiş 4H veriden günlük kazanç)
    # ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_daily_from_4h(df: pd.DataFrame) -> pd.DataFrame:
        """4H barları günlük barlara dönüştür."""
        daily = df.resample('1D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
        }).dropna()
        return daily

    @staticmethod
    def detect_pump_at_bar(df: pd.DataFrame, bar_idx: int,
                           daily_df: pd.DataFrame = None) -> Optional[dict]:
        """
        Module 1 (Backtest): Son 7 adet 4H mumda (28 saatlik rolling pencere)
        net yükseliş >= %30 ve en az 4 yeşil mum koşulu aranır.

        rolling_low  = 7 mumun en düşük LOW'ı
        rolling_high = 7 mumun en yüksek HIGH'ı
        net_gain = (rolling_high - rolling_low) / rolling_low
        daily_df parametresi kullanılmıyor (geriye dönük uyumluluk).
        """
        n = Config.PUMP_WINDOW_CANDLES  # 7
        if bar_idx < n:
            return None

        window = [df.iloc[bar_idx - n + k] for k in range(n)]

        if any(c["low"] <= 0 or pd.isna(c["high"]) for c in window):
            return None

        # Koşul 1: En az 4 yeşil mum (sıralı olması şart değil)
        green_count = sum(1 for c in window if c["close"] > c["open"])
        if green_count < Config.PUMP_MIN_GREEN_COUNT:  # 4
            return None

        # Koşul 2: 1. mumun gövde tabanı → giriş mumunun kapanışı >= PUMP_MIN_PCT
        # pump_start_ref : 1. mum kırmızıysa close, yeşilse open  (wick dahil etme)
        # entry_close    : giriş kırmızı mumunun kapanışı — pump hala ayakta mı diye kontrol
        pump_high      = max(c["high"] for c in window)
        pump_start_ref = min(window[0]["open"], window[0]["close"])  # Gövde tabanı
        pump_start_low = window[0]["low"]   # Rapor/SL referansı için saklanır
        entry_close    = df.iloc[bar_idx]["close"]   # giriş mumu kapanışı
        if pump_start_ref <= 0:
            return None
        net_gain_pct   = (entry_close - pump_start_ref) / pump_start_ref * 100.0
        if net_gain_pct < Config.PUMP_MIN_PCT:
            return None

        return {"pump_pct": net_gain_pct, "pump_low": pump_start_low, "pump_high": pump_high}

    # ─────────────────────────────────────────────────────────────────
    # 3.3  BAR-BY-BAR SİMÜLASYON (v3 — Refined Scalper)
    # ─────────────────────────────────────────────────────────────────

    def run_backtest(self):
        """
        Module 1-5 uyumlu bar-by-bar simülasyon (v3) — KRONOLOJİK UNİFİED TİMELİNE.

        Tüm semboller tek bir zaman ekseni üzerinde işlenir.
        MAX_ACTIVE_TRADES limiti gerçek zamanlı olarak tüm coinlere uygulanır.
        Sembol A'nın işlemi kapanmadan Sembol B'de yeni slot açılmaz.
        """
        log.info("=" * 68)
        log.info("  BACKTEST v3 — Refined Scalper (Unified Timeline)")
        log.info(f"  Sermaye: {self.capital:.2f} USDT  |  "
                 f"Kaldıraç: x{Config.LEVERAGE}  |  Risk/trade: %{Config.risk_per_trade_pct()}")
        log.info("=" * 68)

        equity = self.capital
        self.equity_curve = [equity]
        active: Dict[str, TradeRecord] = {}
        max_concurrent = 0
        be_price_drop_pct = Config.BREAKEVEN_DROP_PCT

        # Her sembol için ayrı state
        sym_dfs: Dict[str, pd.DataFrame] = {sym: df.copy() for sym, df in self.all_data.items()}
        sym_state: Dict[str, dict] = {}
        sym_ts_to_idx: Dict[str, dict] = {}
        for sym, df in sym_dfs.items():
            sym_state[sym] = {
                "in_watchlist": False,
                "pump_info": None,
                "last_exit_price": None,
                "new_push_seen": True,
                "pump_cooldown_until_ts": None,   # timestamp bazlı cooldown
                # 4H gölge state (5m sim karşılaştırması için)
                "sl_4h":  None,
                "tsl_4h": False,
                "be_4h":  False,
                "ll_4h":  0.0,
            }
            sym_ts_to_idx[sym] = {ts: idx for idx, ts in enumerate(df.index)}

        # Tüm sembollerin timestamplarını birleştir → kronolojik sıralı
        all_ts = sorted(set().union(*[set(df.index) for df in sym_dfs.values()]))

        log.info(f"\n  🕐 Unified timeline: {len(all_ts)} timestamp, {len(sym_dfs)} sembol\n")

        start_bar = Config.BB_LENGTH + 2

        for ts in all_ts:
            for sym, df in sym_dfs.items():
                if ts not in sym_ts_to_idx[sym]:
                    continue
                i = sym_ts_to_idx[sym][ts]
                if i < start_bar:
                    continue

                bar      = df.iloc[i]
                bar_dt   = ts
                bar_time = ts.strftime("%d.%m.%Y %H:%M")
                state    = sym_state[sym]
                in_watchlist      = state["in_watchlist"]
                pump_info         = state["pump_info"]
                last_exit_price   = state["last_exit_price"]
                new_push_seen     = state["new_push_seen"]
                pump_cooldown_ts  = state["pump_cooldown_until_ts"]

                # ═══════════════════════════════════════════════════════
                # (A) AKTİF TRADE → TSL / GREEN CANDLE KONTROL
                #     ★ KÖTÜMSERKurgu (Pessimistic Execution) ★
                # ═══════════════════════════════════════════════════════
                if sym in active:
                    trade = active[sym]

                    # ── KURAL 1-3: SL/TSL (5m granüler sim veya 4H fallback) ────
                    _df5m = self.all_data_5m.get(sym)
                    if _df5m is not None:
                        # ── 4H GÖLGE: Paralel 4H tahmini (karşılaştırma için) ────
                        _sl_4h  = sym_state[sym].get("sl_4h") or trade.stop_loss
                        _tsl_4h = sym_state[sym].get("tsl_4h", False)
                        _be_4h  = sym_state[sym].get("be_4h",  False)
                        _ll_4h  = sym_state[sym].get("ll_4h",  0.0)
                        if bar["high"] >= _sl_4h and trade.pnl_4h_est == 0.0:
                            _p4h = (trade.position_size_usdt * trade.leverage *
                                    (trade.entry_price - _sl_4h) / trade.entry_price)
                            trade.pnl_4h_est = round(max(_p4h, -trade.position_size_usdt), 2)
                        else:
                            if not _be_4h:
                                if (trade.entry_price - bar["close"]) / trade.entry_price * 100.0 >= be_price_drop_pct:
                                    _sl_4h = trade.entry_price
                                    _be_4h = True
                            _ld = (trade.entry_price - bar["low"]) / trade.entry_price * 100.0
                            if not _tsl_4h:
                                if _ld >= Config.TSL_ACTIVATION_DROP_PCT:
                                    _tsl_4h = True
                                    _ll_4h  = bar["low"]
                                    _sl_4h  = min(_sl_4h, _ll_4h * (1 + Config.TSL_TRAIL_PCT / 100.0))
                            else:
                                if bar["low"] < _ll_4h:
                                    _ll_4h = bar["low"]
                                    _sl_4h = min(_sl_4h, _ll_4h * (1 + Config.TSL_TRAIL_PCT / 100.0))
                        sym_state[sym].update({"sl_4h": _sl_4h, "tsl_4h": _tsl_4h,
                                               "be_4h": _be_4h, "ll_4h":  _ll_4h})

                        # ── 5m İNTRA-BAR SİMÜLASYON ──────────────────────────
                        _exit = self.simulate_intra_bar_exit(ts, trade, _df5m, be_price_drop_pct)
                        if _exit:
                            exit_p  = _exit["exit_price"]
                            exit_t  = _exit["exit_time"]
                            reason  = _exit["exit_reason"]
                            pnl_pct = (trade.entry_price - exit_p) / trade.entry_price
                            pnl_usd = trade.position_size_usdt * trade.leverage * pnl_pct
                            pnl_usd = max(pnl_usd, -trade.position_size_usdt)
                            if trade.pnl_4h_est == 0.0:
                                trade.pnl_4h_est = round(pnl_usd, 2)
                            trade.exit_time   = exit_t
                            trade.exit_price  = exit_p
                            trade.exit_reason = reason
                            trade.pnl_pct     = round(pnl_pct * 100, 4)
                            trade.pnl_usdt    = round(pnl_usd, 2)
                            equity += pnl_usd
                            self.equity_curve.append(equity)
                            trade.portfolio_after = round(equity, 2)
                            self.trades.append(trade)
                            del active[sym]
                            last_exit_price = exit_p
                            new_push_seen   = False
                            pump_info       = self.detect_pump_at_bar(df, i, None)
                            in_watchlist    = pump_info is not None
                            log.info(f"  [{exit_t}] 🔴 {reason}[5m] — {sym}  Exit: {exit_p:.6f}  PnL: {pnl_usd:+.2f}  Kasa: {equity:.0f}$")
                            sym_state[sym].update({
                                "in_watchlist": in_watchlist, "pump_info": pump_info,
                                "last_exit_price": last_exit_price, "new_push_seen": new_push_seen,
                                "sl_4h": None, "tsl_4h": False, "be_4h": False, "ll_4h": 0.0,
                            })
                            continue
                        # 5m simülasyonunda bu bar'da çıkış yok → KURAL 4'e devam

                    else:
                        # ── 4H FALLBACK: 5m veri yoksa orijinal KURAL 1/2/3 ──
                        if bar["high"] >= trade.stop_loss:
                            exit_p  = trade.stop_loss
                            pnl_pct = (trade.entry_price - exit_p) / trade.entry_price
                            pnl_usd = trade.position_size_usdt * trade.leverage * pnl_pct
                            pnl_usd = max(pnl_usd, -trade.position_size_usdt)
                            reason  = "TSL-HIT" if trade.tsl_active else "STOP-LOSS"
                            trade.pnl_4h_est  = round(pnl_usd, 2)
                            trade.exit_time   = bar_time
                            trade.exit_price  = exit_p
                            trade.exit_reason = reason
                            trade.pnl_pct     = round(pnl_pct * 100, 4)
                            trade.pnl_usdt    = round(pnl_usd, 2)
                            equity += pnl_usd
                            self.equity_curve.append(equity)
                            trade.portfolio_after = round(equity, 2)
                            self.trades.append(trade)
                            del active[sym]
                            last_exit_price = exit_p
                            new_push_seen   = False
                            pump_info       = self.detect_pump_at_bar(df, i, None)
                            in_watchlist    = pump_info is not None
                            log.info(f"  [{bar_time}] 🔴 {reason} — {sym}  Exit: {exit_p:.6f}  PnL: {pnl_usd:+.2f}  Kasa: {equity:.0f}$")
                            sym_state[sym]["in_watchlist"]    = in_watchlist
                            sym_state[sym]["pump_info"]       = pump_info
                            sym_state[sym]["last_exit_price"] = last_exit_price
                            sym_state[sym]["new_push_seen"]   = new_push_seen
                            continue

                        if not trade.breakeven_triggered:
                            drop_pct = (trade.entry_price - bar["close"]) / trade.entry_price * 100.0
                            if drop_pct >= be_price_drop_pct:
                                trade.stop_loss = trade.entry_price
                                trade.breakeven_triggered = True
                                trade.sl_moved_to_be = True
                                log.info(f"  [{bar_time}] ⚡ BE: {sym}  Düşüş: %{drop_pct:.1f}")

                        low_drop_pct = (trade.entry_price - bar["low"]) / trade.entry_price * 100.0
                        if not trade.tsl_active:
                            if low_drop_pct >= Config.TSL_ACTIVATION_DROP_PCT:
                                trade.tsl_active = True
                                trade.lowest_low_reached = bar["low"]
                                new_sl = trade.lowest_low_reached * (1 + Config.TSL_TRAIL_PCT / 100.0)
                                trade.stop_loss = min(trade.stop_loss, new_sl)
                                log.info(f"  [{bar_time}] 🎯 TSL AKTİF: {sym}  "
                                         f"Low: {trade.lowest_low_reached:.6f}  SL → {trade.stop_loss:.6f}")
                        else:
                            if bar["low"] < trade.lowest_low_reached:
                                trade.lowest_low_reached = bar["low"]
                                new_sl = trade.lowest_low_reached * (1 + Config.TSL_TRAIL_PCT / 100.0)
                                trade.stop_loss = min(trade.stop_loss, new_sl)

                        if trade.tsl_active and bar["close"] >= trade.stop_loss:
                            exit_p  = trade.stop_loss
                            pnl_pct = (trade.entry_price - exit_p) / trade.entry_price
                            pnl_usd = trade.position_size_usdt * trade.leverage * pnl_pct
                            pnl_usd = max(pnl_usd, -trade.position_size_usdt)
                            trade.pnl_4h_est  = round(pnl_usd, 2)
                            trade.exit_time   = bar_time
                            trade.exit_price  = exit_p
                            trade.exit_reason = "TSL-HIT"
                            trade.pnl_pct     = round(pnl_pct * 100, 4)
                            trade.pnl_usdt    = round(pnl_usd, 2)
                            equity += pnl_usd
                            self.equity_curve.append(equity)
                            trade.portfolio_after = round(equity, 2)
                            self.trades.append(trade)
                            del active[sym]
                            last_exit_price = exit_p
                            new_push_seen   = False
                            pump_info       = self.detect_pump_at_bar(df, i, None)
                            in_watchlist    = pump_info is not None
                            log.info(f"  [{bar_time}] 🎯 TSL-HIT (bounce): {sym}  Exit: {exit_p:.6f}  PnL: {pnl_usd:+.2f}  Kasa: {equity:.0f}$")
                            sym_state[sym]["in_watchlist"]    = in_watchlist
                            sym_state[sym]["pump_info"]       = pump_info
                            sym_state[sym]["last_exit_price"] = last_exit_price
                            sym_state[sym]["new_push_seen"]   = new_push_seen
                            continue

                    # ── KURAL 4: ZARARDA YEŞİL MUM (GREEN-10) ────────────
                    if bar["close"] > bar["open"] and bar["close"] > trade.entry_price:
                        green_body_pct = (bar["close"] - bar["open"]) / bar["open"] * 100.0
                        if green_body_pct >= Config.GREEN_LOSS_SINGLE_BODY_PCT:
                            exit_p  = bar["close"]
                            pnl_pct = (trade.entry_price - exit_p) / trade.entry_price
                            pnl_usd = trade.position_size_usdt * trade.leverage * pnl_pct
                            pnl_usd = max(pnl_usd, -trade.position_size_usdt)
                            trade.exit_time   = bar_time
                            trade.exit_price  = exit_p
                            trade.exit_reason = "GREEN-10"
                            trade.pnl_pct     = round(pnl_pct * 100, 4)
                            trade.pnl_usdt    = round(pnl_usd, 2)
                            equity += pnl_usd
                            self.equity_curve.append(equity)
                            trade.portfolio_after = round(equity, 2)
                            self.trades.append(trade)
                            del active[sym]
                            last_exit_price = exit_p
                            new_push_seen   = False
                            pump_info       = self.detect_pump_at_bar(df, i, None)
                            in_watchlist    = pump_info is not None
                            log.info(f"  [{bar_time}] 🟠 GREEN-10: {sym}  Gövde: %{green_body_pct:.1f}  Exit: {exit_p:.6f}  PnL: {pnl_usd:+.2f}  Kasa: {equity:.0f}$")
                            sym_state[sym]["in_watchlist"]    = in_watchlist
                            sym_state[sym]["pump_info"]       = pump_info
                            sym_state[sym]["last_exit_price"] = last_exit_price
                            sym_state[sym]["new_push_seen"]   = new_push_seen
                            continue
                        trade.consec_green_loss += 1
                        if trade.consec_green_loss >= 2:
                            exit_p  = bar["close"]
                            pnl_pct = (trade.entry_price - exit_p) / trade.entry_price
                            pnl_usd = trade.position_size_usdt * trade.leverage * pnl_pct
                            pnl_usd = max(pnl_usd, -trade.position_size_usdt)
                            trade.exit_time   = bar_time
                            trade.exit_price  = exit_p
                            trade.exit_reason = "2xGREEN-LOSS"
                            trade.pnl_pct     = round(pnl_pct * 100, 4)
                            trade.pnl_usdt    = round(pnl_usd, 2)
                            equity += pnl_usd
                            self.equity_curve.append(equity)
                            trade.portfolio_after = round(equity, 2)
                            self.trades.append(trade)
                            del active[sym]
                            last_exit_price = exit_p
                            new_push_seen   = False
                            pump_info       = self.detect_pump_at_bar(df, i, None)
                            in_watchlist    = pump_info is not None
                            log.info(f"  [{bar_time}] 🟠 2xGREEN-LOSS: {sym}  Exit: {exit_p:.6f}  PnL: {pnl_usd:+.2f}  Kasa: {equity:.0f}$")
                            sym_state[sym]["in_watchlist"]    = in_watchlist
                            sym_state[sym]["pump_info"]       = pump_info
                            sym_state[sym]["last_exit_price"] = last_exit_price
                            sym_state[sym]["new_push_seen"]   = new_push_seen
                            continue
                    else:
                        trade.consec_green_loss = 0

                    continue  # Trade hâlâ açık

                # ═══════════════════════════════════════════════════════
                # (B) PUMP TESPİTİ — WATCHLIST
                # ═══════════════════════════════════════════════════════
                if last_exit_price is not None and not new_push_seen:
                    if bar["high"] > last_exit_price:
                        new_push_seen = True
                        log.info(f"  [{bar_time}] 🔄 YENİ PUSH: {sym}  H: {bar['high']:.6f}")
                if not in_watchlist:
                    # Cooldown: timestamp bazlı
                    if pump_cooldown_ts is not None and ts < pump_cooldown_ts:
                        pass  # Cooldown aktif
                    else:
                        pump_info = self.detect_pump_at_bar(df, i, None)
                        if pump_info:
                            in_watchlist = True
                            log.info(f"  [{bar_time}] 🚨 Pump: {sym}  "
                                     f"+{pump_info['pump_pct']:.1f}%  "
                                     f"Zirve: {pump_info['pump_high']:.6f}")
                else:
                    check = self.detect_pump_at_bar(df, i, None)
                    if check is None:
                        in_watchlist = False
                        pump_info    = None
                        sym_state[sym]["in_watchlist"] = False
                        sym_state[sym]["pump_info"]    = None
                        continue
                    pump_info["pump_high"] = max(pump_info["pump_high"], check["pump_high"])

                # ═══════════════════════════════════════════════════════
                # (C) GİRİŞ: Kırmızı mum → SHORT
                # ═══════════════════════════════════════════════════════
                if not in_watchlist or pump_info is None:
                    sym_state[sym]["in_watchlist"] = in_watchlist
                    sym_state[sym]["pump_info"]    = pump_info
                    sym_state[sym]["new_push_seen"] = new_push_seen
                    continue
                if not new_push_seen:
                    sym_state[sym]["in_watchlist"] = in_watchlist
                    sym_state[sym]["pump_info"]    = pump_info
                    sym_state[sym]["new_push_seen"] = new_push_seen
                    continue

                # Tarih aralığı filtresi: start_dt öncesi barlarda giriş açma
                if bar_dt < self.start_dt:
                    sym_state[sym]["in_watchlist"] = in_watchlist
                    sym_state[sym]["pump_info"]    = pump_info
                    sym_state[sym]["new_push_seen"] = new_push_seen
                    continue

                if bar["close"] >= bar["open"]:
                    sym_state[sym]["in_watchlist"] = in_watchlist
                    sym_state[sym]["pump_info"]    = pump_info
                    sym_state[sym]["new_push_seen"] = new_push_seen
                    continue

                red_body_pct = (bar["open"] - bar["close"]) / bar["open"] * 100.0

                # ── GERÇEKÇİ GİRİŞ FİYATI: Sinyal mumunun kapanışında değil,
                #    Sinyal barı kapatıktan sonraki ilk 5m mumun AÇILIŞI kullanılır.
                #    Önceliğ: 5m veri → sonraki 4H bar openı → fallback bar["close"]
                _entry_ts5 = ts + pd.Timedelta(hours=4)
                _df5m_sym  = self.all_data_5m.get(sym)
                if _df5m_sym is not None and _entry_ts5 in _df5m_sym.index:
                    entry_p       = _df5m_sym.loc[_entry_ts5]["open"]
                    entry_time_bt = _entry_ts5.strftime("%d.%m.%Y %H:%M")
                elif i + 1 < len(df):
                    entry_p       = df.iloc[i + 1]["open"]
                    entry_time_bt = df.index[i + 1].strftime("%d.%m.%Y %H:%M")
                else:
                    entry_p       = bar["close"]
                    entry_time_bt = bar_time

                if entry_p >= pump_info["pump_high"]:
                    pump_info["pump_high"] = max(pump_info["pump_high"], bar["high"])
                    sym_state[sym]["in_watchlist"] = in_watchlist
                    sym_state[sym]["pump_info"]    = pump_info
                    sym_state[sym]["new_push_seen"] = new_push_seen
                    continue

                if red_body_pct < Config.ENTRY_RED_BODY_MIN_PCT:
                    sym_state[sym]["in_watchlist"] = in_watchlist
                    sym_state[sym]["pump_info"]    = pump_info
                    sym_state[sym]["new_push_seen"] = new_push_seen
                    continue
                prev_bar = df.iloc[i - 1]
                if prev_bar["close"] <= prev_bar["open"]:
                    sym_state[sym]["in_watchlist"] = in_watchlist
                    sym_state[sym]["pump_info"]    = pump_info
                    sym_state[sym]["new_push_seen"] = new_push_seen
                    continue
                prev_body_pct = (prev_bar["close"] - prev_bar["open"]) / prev_bar["open"] * 100.0
                if prev_body_pct >= Config.ANTI_ROCKET_SINGLE_CANDLE_PCT:
                    sym_state[sym]["in_watchlist"] = in_watchlist
                    sym_state[sym]["pump_info"]    = pump_info
                    sym_state[sym]["new_push_seen"] = new_push_seen
                    continue

                pi_saved     = pump_info
                in_watchlist = False
                pump_info    = None
                # Cooldown: PUMP_CONSECUTIVE_GREEN × 4H = timestamp
                pump_cooldown_ts = ts + timedelta(hours=Config.PUMP_CONSECUTIVE_GREEN * 4)

                pos_margin = equity / Config.MAX_ACTIVE_TRADES
                if pos_margin < 10.0:
                    log.info(f"  [{bar_time}] ⛔ SLOT BOÜÇ ({pos_margin:.0f}$ < 10$): {sym} — sinyal iptal")
                    sym_state[sym]["in_watchlist"]          = in_watchlist
                    sym_state[sym]["pump_info"]             = pump_info
                    sym_state[sym]["new_push_seen"]         = new_push_seen
                    sym_state[sym]["pump_cooldown_until_ts"]= pump_cooldown_ts
                    continue

                if len(active) >= Config.MAX_ACTIVE_TRADES:
                    log.info(f"  [{bar_time}] ⛔ SLOT DOLU ({len(active)}/{Config.MAX_ACTIVE_TRADES}) — {sym} sinyal iptal")
                    sym_state[sym]["in_watchlist"]          = in_watchlist
                    sym_state[sym]["pump_info"]             = pump_info
                    sym_state[sym]["new_push_seen"]         = new_push_seen
                    sym_state[sym]["pump_cooldown_until_ts"]= pump_cooldown_ts
                    continue

                lev = Config.LEVERAGE
                sl  = entry_p * (1 + Config.SL_ABOVE_ENTRY_PCT / 100.0)

                trade = TradeRecord(
                    symbol=sym, side="SHORT",
                    entry_time=entry_time_bt, entry_price=entry_p,
                    stop_loss=sl, initial_stop_loss=sl,
                    tp1_price=0.0, tp2_price=0.0,
                    position_size_usdt=pos_margin, remaining_pct=1.0,
                    pump_pct=pi_saved["pump_pct"],
                    pump_high=pi_saved["pump_high"],
                    pump_low=pi_saved["pump_low"],
                    entry_candle_open=entry_p,
                    leverage=lev,
                )
                active[sym] = trade
                max_concurrent = max(max_concurrent, len(active))
                # 4H gölge SL state'ini başlat (5m sim karşılaştırması için)
                sym_state[sym]["sl_4h"]  = sl
                sym_state[sym]["tsl_4h"] = False
                sym_state[sym]["be_4h"]  = False
                sym_state[sym]["ll_4h"]  = 0.0
                log.info(f"  [{entry_time_bt}] ✅ SHORT: {sym}  "
                         f"Giriş: {entry_p:.6f}  SL: {sl:.6f}  "
                         f"Pump: +{pi_saved['pump_pct']:.1f}%  Kaldıraç: x{lev}  "
                         f"Bağlanan: {pos_margin:.0f}$  Kasa: {equity:.0f}$  "
                         f"Slot: {len(active)}/{Config.MAX_ACTIVE_TRADES}  [Sinyal: {bar_time}]")

                sym_state[sym]["in_watchlist"]           = in_watchlist
                sym_state[sym]["pump_info"]              = pump_info
                sym_state[sym]["new_push_seen"]          = new_push_seen
                sym_state[sym]["pump_cooldown_until_ts"] = pump_cooldown_ts

        # ── Backtest sonu: açık kalan trade'leri kapat ────────────────
        for sym, trade in list(active.items()):
            if sym in self.all_data and not self.all_data[sym].empty:
                df_sim = self.all_data[sym]
                df_sim = df_sim[df_sim.index <= pd.Timestamp(self.end_dt)]
                if df_sim.empty:
                    continue
                exit_p  = df_sim["close"].iloc[-1]
                pnl_pct = (trade.entry_price - exit_p) / trade.entry_price
                pnl_usd = trade.position_size_usdt * trade.leverage * pnl_pct
                pnl_usd = max(pnl_usd, -trade.position_size_usdt)
                trade.exit_time   = df_sim.index[-1].strftime("%d.%m.%Y %H:%M")
                trade.exit_price  = exit_p
                trade.exit_reason = "BT-END"
                trade.pnl_pct     = round(pnl_pct * 100, 4)
                trade.pnl_usdt    = round(pnl_usd, 2)
                equity += pnl_usd
                self.equity_curve.append(equity)
                trade.portfolio_after = round(equity, 2)
                self.trades.append(trade)
                log.info(f"  [BT-END] 🔵 {sym}  PnL: {pnl_usd:+.2f}  Kasa: {equity:.0f}$")

        self.equity_curve.append(equity)
        log.info(f"\n  Max eşzamanlı trade: {max_concurrent}")

    # ─────────────────────────────────────────────────────────────────
    # 3.4  RAPOR OLUŞTURMA
    # ─────────────────────────────────────────────────────────────────

    def print_report(self):
        """Detaylı backtest raporunu terminale yazdır."""
        print("\n")
        print("═" * 80)
        print("  📊  PUMP & DUMP REVERSION v3 — BACKTEST RAPORU")
        print("═" * 80)

        if not self.trades:
            print("  Hiç trade oluşmadı.")
            print("═" * 80)
            return

        total     = len(self.trades)
        winners   = [t for t in self.trades if t.pnl_usdt > 0]
        losers    = [t for t in self.trades if t.pnl_usdt <= 0]
        win_rate  = (len(winners) / total) * 100 if total > 0 else 0

        total_pnl    = sum(t.pnl_usdt for t in self.trades)
        gross_profit = sum(t.pnl_usdt for t in winners) if winners else 0
        gross_loss   = abs(sum(t.pnl_usdt for t in losers)) if losers else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        avg_win  = (gross_profit / len(winners)) if winners else 0
        avg_loss = (gross_loss / len(losers)) if losers else 0

        ec = self.equity_curve if self.equity_curve else [self.capital]
        peak = ec[0]
        max_dd = 0
        for val in ec:
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100
            if dd > max_dd:
                max_dd = dd

        final_equity = ec[-1]
        total_return = ((final_equity - self.capital) / self.capital) * 100

        print(f"""
  Başlangıç Sermayesi : {self.capital:>12,.2f} USDT
  Son Öz-Varlık       : {final_equity:>12,.2f} USDT
  Toplam Getiri       : {total_return:>+11.2f} %
  ─────────────────────────────────────────────
  Toplam Trade        : {total:>5}
  Kazanan             : {len(winners):>5}   ({win_rate:.1f}%)
  Kaybeden            : {len(losers):>5}   ({100 - win_rate:.1f}%)
  ─────────────────────────────────────────────
  Brüt Kâr            : {gross_profit:>+12,.2f} USDT
  Brüt Zarar          : {-gross_loss:>+12,.2f} USDT
  Net PnL             : {total_pnl:>+12,.2f} USDT
  ─────────────────────────────────────────────
  Profit Factor       : {profit_factor:>10.2f}
  Ort. Kazanç/Trade   : {avg_win:>+12,.2f} USDT
  Ort. Kayıp/Trade    : {-avg_loss:>+12,.2f} USDT
  Max Drawdown        : {max_dd:>10.2f} %
""")

        # ── Trade-by-Trade Log ────────────────────────────────────────
        has_4h = any(t.pnl_4h_est != 0.0 for t in self.trades)
        if has_4h:
            print("  ┌─────┬────────────┬──────────────────┬────────────┬────────────┬────────────┬────────────┬────────────────┬────────────┬────────────┐")
            print("  │  #  │  Sembol    │  Giriş Zamanı    │  Giriş Fiy │  İlk SL    │  Son SL    │  Çıkış Fiy │  Çıkış Nedeni  │ PnL 5m(USDT│ PnL 4H Est │")
            print("  ├─────┼────────────┼──────────────────┼────────────┼────────────┼────────────┼────────────┼────────────────┼────────────┼────────────┤")
        else:
            print("  ┌─────┬────────────┬──────────────────┬────────────┬────────────┬────────────┬────────────┬────────────────┬────────────┐")
            print("  │  #  │  Sembol    │  Giriş Zamanı    │  Giriş Fiy │  İlk SL    │  Son SL    │  Çıkış Fiy │  Çıkış Nedeni  │  PnL (USDT)│")
            print("  ├─────┼────────────┼──────────────────┼────────────┼────────────┼────────────┼────────────┼────────────────┼────────────┤")

        for idx, t in enumerate(self.trades, 1):
            sym_short  = t.symbol.replace("/USDT", "").ljust(10)
            entry_t    = t.entry_time[:16].ljust(16)
            entry_p    = f"{t.entry_price:<10.6f}"
            sl_p       = f"{t.initial_stop_loss:<10.6f}"
            tp_p       = f"{t.stop_loss:<10.6f}"
            exit_p_str = f"{t.exit_price:<10.6f}"
            reason     = t.exit_reason[:14].ljust(14)
            pnl_str    = f"{t.pnl_usdt:>+10.2f}"
            if has_4h:
                pnl_4h_str = f"{t.pnl_4h_est:>+10.2f}"
                diff_sign  = "↑" if t.pnl_4h_est > t.pnl_usdt else ("↓" if t.pnl_4h_est < t.pnl_usdt else " ")
                print(f"  │ {idx:>3} │ {sym_short}│ {entry_t} │ {entry_p} │ {sl_p} │ {tp_p} │ {exit_p_str} │ {reason} │ {pnl_str} │ {pnl_4h_str}{diff_sign}│")
            else:
                print(f"  │ {idx:>3} │ {sym_short}│ {entry_t} │ {entry_p} │ {sl_p} │ {tp_p} │ {exit_p_str} │ {reason} │ {pnl_str} │")

        if has_4h:
            print("  └─────┴────────────┴──────────────────┴────────────┴────────────┴────────────┴────────────┴────────────────┴────────────┴────────────┘")
            print("  (↑ = 4H tahmini daha iyi  |  ↓ = 4H tahmini daha kötü  |  4H Est gerçekçi değil, karşılaştırma içindir)")
        else:
            print("  └─────┴────────────┴──────────────────┴────────────┴────────────┴────────────┴────────────┴────────────────┴────────────┘")

        # ── Sembol Bazlı Özet ─────────────────────────────────────────
        print("\n  📈 Sembol Bazlı Özet:")
        print("  ─────────────────────────────────────────")
        sym_groups: Dict[str, List[TradeRecord]] = {}
        for t in self.trades:
            sym_groups.setdefault(t.symbol, []).append(t)

        for sym, trades_list in sym_groups.items():
            s_total = len(trades_list)
            s_wins  = len([t for t in trades_list if t.pnl_usdt > 0])
            s_pnl   = sum(t.pnl_usdt for t in trades_list)
            print(f"  {sym:<16}  Trade: {s_total:>3}  |  "
                  f"Kazanma: {s_wins}/{s_total}  |  Net PnL: {s_pnl:>+10.2f} USDT")

        # ── 5m Simülasyon vs 4H Tahmini Karşılaştırması ──────────────
        trades_with_cmp = [t for t in self.trades if t.pnl_4h_est != 0.0]
        if trades_with_cmp:
            pnl_5m_total = sum(t.pnl_usdt    for t in self.trades)
            pnl_4h_total = sum(t.pnl_4h_est  for t in self.trades)
            diff         = pnl_5m_total - pnl_4h_total

            # 4H tahmini equity eğrisi
            eq_4h   = [self.capital]
            for t in self.trades:
                eq_4h.append(eq_4h[-1] + t.pnl_4h_est)
            peak_4h = eq_4h[0]; mdd_4h = 0.0
            for v in eq_4h:
                if v > peak_4h:
                    peak_4h = v
                dd = (peak_4h - v) / peak_4h * 100.0 if peak_4h > 0 else 0.0
                if dd > mdd_4h:
                    mdd_4h = dd

            sign = "+" if diff >= 0 else ""
            print(f"""
  ┌──────────────────────────────────────────────────────┐
  │     5m SİMÜLASYON  vs  4H TAHMİN KARŞILAŞTIRMASI   │
  ├──────────────────────────────────────────────────────┤
  │  Gerçekçi Net PnL (5m)  : {pnl_5m_total:>+12,.2f} USDT        │
  │  Tahmini Net PnL  (4H)  : {pnl_4h_total:>+12,.2f} USDT        │
  │  Fark  (5m – 4H)        : {sign}{abs(diff):>11,.2f} USDT        │
  ├──────────────────────────────────────────────────────┤
  │  5m Maks Drawdown       : {max_dd:>10.2f} %              │
  │  4H Tahmini Maks DD     : {mdd_4h:>10.2f} %              │
  └──────────────────────────────────────────────────────┘""")

        print("\n" + "═" * 80)

    # ─────────────────────────────────────────────────────────────────
    # 3.4  5m DOĞRULAMA — Kârlı tradeler (backtest bittikten sonra)
    # ─────────────────────────────────────────────────────────────────

    def verify_profits_5m(self):
        """
        İki aşamalı backtest doğrulama motoru.

        AŞAMA 1 — 4H Kaba Analiz (Baseline)
          Backtest'ten gelen tüm işlemleri 4H sonuçlarıyla tablola.
          Toplam bakiye, win-rate, kâr/zarar dağılımı.

        AŞAMA 2 — 5m Hassas Doğrulama (Refinement)
          Filtre: pnl_usdt > 0 VEYA exit_reason == 'TSL-HIT'
          Her işlem için entry_time → 4H exit_time arasındaki 5m mumları tara.
          HIGH-first kötümser sıra:
            1) HIGH >= mevcut SL → anında çıkış (TSL/BE değişmeden önce)
            2) Breakeven: close %BE_PCT düştüyse SL=entry; tekrar HIGH kontrolü
            3) TSL aktivasyon + güncelleme (low bazlı)
          Çıkış nedeni: '5m_TSL_HIT' veya '5m_SL_HIT'

        AŞAMA 3 — Karşılaştırmalı Rapor
          df_4h_results  : 4H iyimser tablo (tüm işlemler)
          df_5m_results  : 5m doğrulanmış tablo (filtreli işlemler, güncel PnL)
          Net kâr/zarar karşılaştırması
        """
        be_p  = Config.BREAKEVEN_DROP_PCT
        tsl_a = Config.TSL_ACTIVATION_DROP_PCT
        tsl_t = Config.TSL_TRAIL_PCT
        sl_i  = Config.SL_ABOVE_ENTRY_PCT

        # ══════════════════════════════════════════════════════════════
        # AŞAMA 1 — 4H Baseline Tablosu
        # ══════════════════════════════════════════════════════════════
        print("\n")
        print("═" * 100)
        print("  📊  AŞAMA 1 — 4H KABA ANALİZ (Baseline)")
        print("═" * 100)

        rows_4h = []
        for t in self.trades:
            rows_4h.append({
                "Sembol":      t.symbol.replace("/USDT","").replace(":USDT",""),
                "Giriş":       t.entry_time,
                "Giriş Fiy":   t.entry_price,
                "İlk SL":      t.initial_stop_loss,
                "Son SL":      t.stop_loss,
                "Çıkış Fiy":   t.exit_price,
                "Çıkış Ned":   t.exit_reason,
                "PnL (USDT)":  t.pnl_usdt,
                "Durum":       "✅ KÂR" if t.pnl_usdt > 0 else "🔴 ZARAR",
            })

        df_4h = pd.DataFrame(rows_4h)
        total_4h   = len(df_4h)
        winners_4h = (df_4h["PnL (USDT)"] > 0).sum()
        net_4h     = df_4h["PnL (USDT)"].sum()

        print(f"\n  Toplam: {total_4h}  |  Kârlı: {winners_4h}  |  Zararlı: {total_4h-winners_4h}  |  Win Rate: %{winners_4h/total_4h*100:.1f}" if total_4h else "\n  Trade yok.")
        print(f"  4H Net PnL: {net_4h:>+.2f} USDT\n")

        # Tablo başlığı
        W = 109
        print("  ┌" + "─"*(W-2) + "┐")
        h = f"  {'#':>3}  {'Sembol':<12}  {'Giriş Zamanı':>16}  {'Giriş Fiy':>11}  {'İlk SL':>11}  {'Son SL':>11}  {'Çıkış Fiy':>11}  {'Çıkış Nedeni':<14}  {'PnL':>10}  {'Durum'}"
        print("  │" + h + " "*(W-2-len(h)) + "│")
        print("  ├" + "─"*(W-2) + "┤")
        for i, t in enumerate(self.trades, 1):
            sym = t.symbol.replace("/USDT","").replace(":USDT","")
            pnl_str = f"{t.pnl_usdt:>+10.2f}"
            icon    = "✅" if t.pnl_usdt > 0 else "🔴"
            row = (f"  {i:>3}  {sym:<12}  {t.entry_time[:16]:>16}  "
                   f"{t.entry_price:>11.6f}  {t.initial_stop_loss:>11.6f}  "
                   f"{t.stop_loss:>11.6f}  {t.exit_price:>11.6f}  "
                   f"{t.exit_reason:<14}  {pnl_str}  {icon}")
            print("  │" + row + " "*(W-2-len(row)) + "│")
        print("  ├" + "═"*(W-2) + "┤")
        foot = f"  {'TOPLAM':<16}  {'':>16}  {'':>11}  {'':>11}  {'':>11}  {'':>11}  {'':>14}  {net_4h:>+10.2f}"
        print("  │" + foot + " "*(W-2-len(foot)) + "│")
        print("  └" + "─"*(W-2) + "┘")

        # ══════════════════════════════════════════════════════════════
        # AŞAMA 2 — 5m Hassas Doğrulama
        # ══════════════════════════════════════════════════════════════
        print("\n")
        print("═" * 100)
        print("  🔍  AŞAMA 2 — 5m HASSAS DOĞRULAMA (Refinement)")
        print("═" * 100)
        print(f"  Parametreler: BE@%{be_p:.0f}  TSL-Akt@%{tsl_a:.0f}  TSL-Trail@%{tsl_t:.0f}  İlk-SL@%{sl_i:.0f}")

        # Filtre: pnl > 0 VEYA exit_reason == TSL-HIT
        candidates = [t for t in self.trades if t.pnl_usdt > 0 or t.exit_reason == "TSL-HIT"]
        print(f"  Filtre (pnl>0 VEYA TSL-HIT): {len(candidates)}/{total_4h} işlem seçildi")

        if not candidates:
            print("\n  ⚠  Doğrulanacak işlem yok.")
            print("═" * 100)
            return

        if not self.all_data_5m:
            print("\n  ⚠  5m veri mevcut değil — Aşama 2 atlanıyor.")
            print("═" * 100)
            return

        syms_missing = set(t.symbol for t in candidates if self.all_data_5m.get(t.symbol) is None)
        if syms_missing:
            print(f"  ⚠  5m verisi eksik: {', '.join(s.replace('/USDT','') for s in syms_missing)}")
        print()

        verified = []   # (trade, exit_info_or_None, note)

        for idx, trade in enumerate(candidates, 1):
            sym_short = trade.symbol.replace("/USDT","").replace(":USDT","")
            print(f"  [{idx:>2}/{len(candidates)}] {sym_short:<12}  "
                  f"4H: {trade.exit_reason:<10} {trade.pnl_usdt:>+8.2f}$  →  ",
                  end="", flush=True)

            df5 = self.all_data_5m.get(trade.symbol)
            if df5 is None or df5.empty:
                print("⚠  5m veri yok")
                verified.append((trade, None, "5m veri yok"))
                continue

            try:
                # entry_time = 4H bar open zamanı (UTC) = gerçek giriş anı
                entry_ts = pd.Timestamp(
                    datetime.strptime(trade.entry_time[:16], "%d.%m.%Y %H:%M"), tz="UTC"
                )
                # 4H exit zamanı: bitiş sınırı olarak kullan + 4H buffer
                if trade.exit_time:
                    exit_ts = pd.Timestamp(
                        datetime.strptime(trade.exit_time[:16], "%d.%m.%Y %H:%M"), tz="UTC"
                    ) + pd.Timedelta(hours=4)
                else:
                    exit_ts = entry_ts + pd.Timedelta(days=14)
            except Exception:
                print("⚠  zaman parse hatası")
                verified.append((trade, None, "zaman parse hatası"))
                continue

            # Entry ile 4H exit arasındaki 5m mumları izole et
            sub = df5[(df5.index >= entry_ts) & (df5.index <= exit_ts)]
            if sub.empty:
                print("⚠  izole edilecek 5m veri yok")
                verified.append((trade, None, "5m veri boş"))
                continue

            # ── Simülasyon: HIGH-first, kötümser ─────────────────────
            ep       = trade.entry_price
            sl       = ep * (1 + sl_i / 100.0)
            be_done  = False
            tsl_on   = False
            lowest   = 0.0
            exit_info = None
            _pos = trade.position_size_usdt
            _lev = trade.leverage

            def _pnl(xp: float, _ep=ep, _pos=_pos, _lev=_lev) -> float:
                raw = _pos * _lev * (_ep - xp) / _ep
                return round(max(raw, -_pos), 2)

            # Büyük fark olasılığı için trace buffer (çıkışta karar veririz)
            trace_buf = []

            for ts5, b5 in sub.iterrows():
                hi = b5["high"];  lo = b5["low"];  cl = b5["close"]
                sl_before   = sl
                tsl_was_on  = tsl_on   # bu bar başındaki TSL durumu

                # Adım 1: HIGH >= mevcut SL → erken çıkış (BE/TSL henüz değişmeden)
                if hi >= sl:
                    reason = "5m_TSL_HIT" if tsl_on else "5m_SL_HIT"
                    exit_info = {"exit_time": ts5.strftime("%d.%m.%Y %H:%M"),
                                 "exit_price": sl, "exit_reason": reason,
                                 "pnl_usdt": _pnl(sl)}
                    trace_buf.append(f"    EXIT  {ts5.strftime('%H:%M')}  H={hi:.6f} L={lo:.6f} C={cl:.6f}  SL={sl:.6f}  → {reason}")
                    break

                # Adım 2: TSL aktivasyon / güncelleme — LOW bazlı
                ld = (ep - lo) / ep * 100.0
                if not tsl_on:
                    if ld >= tsl_a:
                        tsl_on = True;  lowest = lo
                        sl = min(sl, lowest * (1 + tsl_t / 100.0))
                        trace_buf.append(f"    TSL♻  {ts5.strftime('%H:%M')}  H={hi:.6f} L={lo:.6f} C={cl:.6f}  ld={ld:.1f}%  SL={sl_before:.6f}→{sl:.6f}  lowest={lowest:.6f}")
                else:
                    if lo < lowest:
                        lowest = lo
                        sl = min(sl, lowest * (1 + tsl_t / 100.0))
                        trace_buf.append(f"    TSL↓  {ts5.strftime('%H:%M')}  H={hi:.6f} L={lo:.6f} C={cl:.6f}  SL={sl_before:.6f}→{sl:.6f}  lowest={lowest:.6f}")

                # Adım 3: Breakeven — CLOSE bazlı
                if not be_done:
                    drop_cl = (ep - cl) / ep * 100.0
                    if drop_cl >= be_p:
                        sl = min(sl, ep)
                        be_done = True
                        trace_buf.append(f"    BE✓   {ts5.strftime('%H:%M')}  H={hi:.6f} L={lo:.6f} C={cl:.6f}  drop={drop_cl:.1f}%  SL={sl_before:.6f}→{sl:.6f}")

                # Adım 4: TSL sonrası HIGH hit
                # SADECE bar başında TSL zaten aktifse kontrol et.
                # Bu bar içinde yeni aktifleşen TSL'nin SL seviyesi HIGH'tan SONRA
                # oluştu (HIGH açılış civarında, LOW dip noktada) — aynı barda hit imkansız.
                if tsl_was_on and hi >= sl:
                    exit_info = {"exit_time": ts5.strftime("%d.%m.%Y %H:%M"),
                                 "exit_price": sl, "exit_reason": "5m_TSL_HIT",
                                 "pnl_usdt": _pnl(sl)}
                    trace_buf.append(f"    EXIT  {ts5.strftime('%H:%M')}  H={hi:.6f} L={lo:.6f} C={cl:.6f}  SL={sl:.6f}  → 5m_TSL_HIT(A4)")
                    break

            if exit_info is None:
                print("⚠  5m'de çıkış tetiklenmedi")
            else:
                icon = "✅" if exit_info["pnl_usdt"] > 0 else "🔴"
                diff = exit_info["pnl_usdt"] - trade.pnl_usdt
                warn = "  ⚠ BÜYÜK FARK" if abs(diff) > 100 else ""
                print(f"{icon} {exit_info['exit_reason']:<12}  "
                      f"Fiy: {exit_info['exit_price']:.6f}  "
                      f"5m PnL: {exit_info['pnl_usdt']:>+8.2f}$  "
                      f"Δ{diff:>+7.2f}${warn}")
                # Büyük fark — bar-by-bar trace bas
                if abs(diff) > 100 and trace_buf:
                    print(f"    ┌── TRACE {sym_short} (entry={ep:.6f}  entry_ts={entry_ts})  "
                          f"sub={len(sub)} bar  İlk bar: {sub.index[0].strftime('%d.%m %H:%M')} ──")
                    for line in trace_buf:
                        print(line)
                    print(f"    └── sub son bar: {sub.index[-1].strftime('%d.%m %H:%M')}")
            verified.append((trade, exit_info, None))

        # ══════════════════════════════════════════════════════════════
        # AŞAMA 3 — Karşılaştırmalı Rapor
        # ══════════════════════════════════════════════════════════════
        print("\n")
        print("═" * 100)
        print("  📋  AŞAMA 3 — KARŞILAŞTIRMALI RAPOR (df_4h_results  vs  df_5m_results)")
        print("═" * 100)

        rows_5m = []
        total_bt_cand  = 0.0
        total_5m_cand  = 0.0
        valid_5m       = 0

        print("\n  ┌" + "─"*(W-2) + "┐")
        hdr = (f"  {'#':>3}  {'Sembol':<12}  {'Giriş Fiy':>11}  "
               f"{'4H Çıkış Fiy':>13}  {'5m Çıkış Fiy':>13}  "
               f"{'4H Neden':<13}  {'5m Neden':<13}  "
               f"{'4H PnL':>10}  {'5m PnL':>10}  {'Δ':>9}")
        print("  │" + hdr + " "*(W-2-len(hdr)) + "│")
        print("  ├" + "─"*(W-2) + "┤")

        for i, (trade, sim, err) in enumerate(verified, 1):
            bt_pnl = trade.pnl_usdt
            total_bt_cand += bt_pnl
            sym = trade.symbol.replace("/USDT","").replace(":USDT","")

            if sim is None:
                note = err or "??"
                row = (f"  {i:>3}  {sym:<12}  {trade.entry_price:>11.6f}  "
                       f"{trade.exit_price:>13.6f}  {'N/A':>13}  "
                       f"{trade.exit_reason:<13}  {'⚠ '+note:<13}  "
                       f"{bt_pnl:>+10.2f}  {'N/A':>10}  {'N/A':>9}")
                rows_5m.append({"Sembol": sym, "4H_PnL": bt_pnl, "5m_PnL": None,
                                 "4H_Neden": trade.exit_reason, "5m_Neden": note})
            else:
                s_pnl = sim["pnl_usdt"]
                diff  = s_pnl - bt_pnl
                flag  = " ⚠" if abs(diff) > 100 else "  "
                total_5m_cand += s_pnl
                valid_5m      += 1
                row = (f"  {i:>3}  {sym:<12}  {trade.entry_price:>11.6f}  "
                       f"{trade.exit_price:>13.6f}  {sim['exit_price']:>13.6f}  "
                       f"{trade.exit_reason:<13}  {sim['exit_reason']:<13}  "
                       f"{bt_pnl:>+10.2f}  {s_pnl:>+10.2f}  {diff:>+9.2f}{flag}")
                rows_5m.append({"Sembol": sym, "4H_PnL": bt_pnl, "5m_PnL": s_pnl,
                                 "4H_Neden": trade.exit_reason, "5m_Neden": sim["exit_reason"],
                                 "Δ_PnL": diff})
            print("  │" + row + " "*(W-2-len(row)) + "│")

        print("  ├" + "═"*(W-2) + "┤")
        foot = (f"  {'TOPLAM filtreli (' + str(valid_5m) + '/' + str(len(verified)) + ' 5m veri)':<42}"
                f"{'':>41}  {total_bt_cand:>+10.2f}  {total_5m_cand:>+10.2f}  {(total_5m_cand-total_bt_cand):>+9.2f}")
        print("  │" + foot + " "*(W-2-len(foot)) + "│")
        print("  └" + "─"*(W-2) + "┘")

        # ── 5m performans metrikleri ───────────────────────────────────
        # Zarar eden ve TSL-HIT olmayan tradeler (5m filtresi dışında kalanlar)
        loss_sum = sum(t.pnl_usdt for t in self.trades
                       if t.pnl_usdt <= 0 and t.exit_reason != "TSL-HIT")
        net_5m   = total_5m_cand + loss_sum
        net_bt   = sum(t.pnl_usdt for t in self.trades)
        capital  = getattr(self, "capital", 1000.0) or 1000.0

        # 5m doğrulanmış tüm işlemler (geçerli sim olanlar)
        pnl_list_5m = []
        for trade, sim, _ in verified:
            if sim is not None:
                pnl_list_5m.append(sim["pnl_usdt"])
            # 5m verisi olmayanlar 4H PnL ile kalır (loss_sum içinde zaten)

        # Zarar eden (5m filtre dışı) tradelerin PnL listesi
        pnl_losses_excl = [t.pnl_usdt for t in self.trades
                           if t.pnl_usdt <= 0 and t.exit_reason != "TSL-HIT"]
        all_pnl_5m = pnl_list_5m + pnl_losses_excl

        total_t   = len(all_pnl_5m)
        win_5m    = [p for p in all_pnl_5m if p > 0]
        lose_5m   = [p for p in all_pnl_5m if p <= 0]
        gross_p   = sum(win_5m)
        gross_l   = sum(lose_5m)
        pf        = (gross_p / abs(gross_l)) if gross_l != 0 else float("inf")
        avg_win   = (gross_p / len(win_5m))  if win_5m  else 0.0
        avg_los   = (gross_l / len(lose_5m)) if lose_5m else 0.0
        wr        = (len(win_5m) / total_t * 100) if total_t else 0.0
        eq_5m     = capital + net_5m
        ret_5m    = (net_5m / capital * 100)
        icon_net  = "🟢" if net_5m >= 0 else "🔴"

        print()
        print("  ┌─────────────────────────────────────────────────────────────────┐")
        print("  │  📊  5m DOĞRULAMA SONUÇ TABLOSU                                 │")
        print("  ├─────────────────────────────────────────────────────────────────┤")
        print(f"  │  Başlangıç Sermayesi  : {capital:>12,.2f} USDT                       │")
        print(f"  │  Son Öz-Varlık (5m)   : {eq_5m:>12,.2f} USDT                       │")
        print(f"  │  Toplam Getiri (5m)   : {ret_5m:>+11.2f} %                          │")
        print("  ├─────────────────────────────────────────────────────────────────┤")
        print(f"  │  Toplam Trade         : {total_t:>12,}                               │")
        print(f"  │  Kazanan              : {len(win_5m):>12,}   ({wr:.1f}%)                  │")
        print(f"  │  Kaybeden             : {len(lose_5m):>12,}   ({100-wr:.1f}%)                  │")
        print("  ├─────────────────────────────────────────────────────────────────┤")
        print(f"  │  Brüt Kâr             : {gross_p:>+12.2f} USDT                       │")
        print(f"  │  Brüt Zarar           : {gross_l:>+12.2f} USDT                       │")
        print(f"  │  Net PnL (5m)         : {net_5m:>+12.2f} USDT                       │")
        print("  ├─────────────────────────────────────────────────────────────────┤")
        print(f"  │  Profit Factor        : {pf:>12.2f}                               │")
        print(f"  │  Ort. Kazanç/Trade    : {avg_win:>+12.2f} USDT                       │")
        print(f"  │  Ort. Kayıp/Trade     : {avg_los:>+12.2f} USDT                       │")
        print("  ├─────────────────────────────────────────────────────────────────┤")
        print(f"  │  4H Net PnL           : {net_bt:>+12.2f} USDT                       │")
        print(f"  │  5m Net PnL           : {net_5m:>+12.2f} USDT                       │")
        print(f"  │  Fark (5m – 4H)       : {(net_5m - net_bt):>+12.2f} USDT                       │")
        print("  ├─────────────────────────────────────────────────────────────────┤")
        print(f"  │  {icon_net}  SONUÇ (5m gerçekçi)  : {net_5m:>+12.2f} USDT                       │")
        print("  └─────────────────────────────────────────────────────────────────┘")
        print("\n" + "═" * 100)


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 3.5 — TAM UNIVERSE BACKTESTER  (--full komutu)
# ══════════════════════════════════════════════════════════════════════════

class FullUniverseBacktester:
    """
    Binance Futures'taki TÜM aktif USDT-M çiftlerini tarar.
    1. Binance'den CANLI olarak güncel universe listesini çeker.
    2. Her coin için 18.01.2026 → 18.02.2026 gerçek 4H mum verisini indirir.
    3. Tüm coinler üzerinde AYNI ZAMAN ÇİZELGESİNDE bar-by-bar simülasyon yapar.
       (MAX_ACTIVE_TRADES limiti global olarak tüm coinler için geçerlidir)
    4. Detaylı rapor basar.

    Varsayılan: son 31 gün, 100$ sermaye, max 4 eş zamanlı trade.
    """

    def __init__(self, days: int = None, initial_capital: float = None,
                 start_dt: datetime = None, end_dt: datetime = None):
        self.capital     = initial_capital or Config.BACKTEST_INITIAL_CAPITAL  # 100
        self.exchange    = None
        self.all_data:    Dict[str, pd.DataFrame] = {}   # sym → 4H DataFrame
        self.all_data_5m: Dict[str, pd.DataFrame] = {}  # sym → 5m DataFrame (sadece kazanılan tradeler)
        self.trades: List[TradeRecord] = []
        self.equity_curve: List[float] = []
        self.universe: List[str] = []

        # Tarih aralığı: start_dt/end_dt verilmişse kullan, yoksa days'e göre hesapla
        if start_dt is not None and end_dt is not None:
            self.start_dt = start_dt.replace(tzinfo=timezone.utc) if start_dt.tzinfo is None else start_dt
            self.end_dt   = end_dt.replace(tzinfo=timezone.utc)   if end_dt.tzinfo is None else end_dt
        else:
            _days = days or Config.BACKTEST_DAYS
            self.end_dt   = datetime.now(timezone.utc)
            self.start_dt = self.end_dt - timedelta(days=_days)

    # ─────────────────────────────────────────────────────────────────
    # A) Exchange bağlantısı (public — API key gerekmez)
    # ─────────────────────────────────────────────────────────────────
    async def _init_exchange(self):
        self.exchange = _make_binance_exchange()

    # ─────────────────────────────────────────────────────────────────
    # B) Aktif universe'ü Binance'den CANLI çek
    # ─────────────────────────────────────────────────────────────────
    async def _fetch_universe(self) -> List[str]:
        """Major-cap hariç tüm aktif USDT-M linear futures çiftlerini getir."""
        print("\n🌐 Binance Futures güncel market listesi çekiliyor…")
        markets = await self.exchange.load_markets(True)
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
            base = mkt.get("base", "")
            if base in Config.EXCLUDED_BASES:
                continue
            universe.append(sym)
        print(f"✅ {len(universe)} adet USDT-M futures çifti bulundu (majors hariç).")
        return universe

    # ─────────────────────────────────────────────────────────────────
    # C) Tek sembol için dönem 4H verisini indir
    # ─────────────────────────────────────────────────────────────────
    async def _fetch_ohlcv(self, symbol: str) -> pd.DataFrame:
        """
        Binance'in herkese açık geçmiş OHLCV API'sinden veri çeker.
        API key GEREKMİYOR — public endpoint kullanır.
        """
        # pump window için start'tan 6 mum (24 saat) önce başla
        fetch_start = self.start_dt - timedelta(hours=Config.PUMP_WINDOW_CANDLES * 4)
        since_ms    = int(fetch_start.timestamp() * 1000)
        until_ms    = int(self.end_dt.timestamp() * 1000)
        limit     = 300
        all_candles: list = []
        since_cur = since_ms

        while True:
            try:
                candles = await self.exchange.fetch_ohlcv(
                    symbol, Config.TIMEFRAME,
                    since=since_cur, limit=limit,
                )
            except ccxt.BadSymbol:
                return pd.DataFrame()
            except Exception as e:
                log.debug(f"  {symbol}: {e}")
                break

            if not candles:
                break

            all_candles.extend(candles)
            last_ts = candles[-1][0]

            if last_ts >= until_ms or len(candles) < limit:
                break

            since_cur = last_ts + 1
            await asyncio.sleep(0.12)

        if not all_candles:
            return pd.DataFrame()

        df = pd.DataFrame(all_candles,
                          columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.drop_duplicates(subset="timestamp", inplace=True)
        df.sort_values("timestamp", inplace=True)
        df.set_index("timestamp", inplace=True)
        return df

    # ─────────────────────────────────────────────────────────────────
    # C2) Tek sembol için 5m verisi indır
    # ─────────────────────────────────────────────────────────────────
    async def _fetch_5m(self, symbol: str) -> pd.DataFrame:
        since_ms = int(self.start_dt.timestamp() * 1000)
        until_ms = int(self.end_dt.timestamp() * 1000)
        candles: list = []
        cur = since_ms
        while True:
            try:
                batch = await self.exchange.fetch_ohlcv(symbol, '5m', since=cur, limit=1000)
            except Exception as e:
                log.warning(f"  {symbol} 5m hata: {e}")
                break
            if not batch:
                break
            candles.extend(batch)
            last_ts = batch[-1][0]
            if last_ts >= until_ms or len(batch) < 1000:
                break
            cur = last_ts + 1
            await asyncio.sleep(0.15)
        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame(candles, columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.drop_duplicates(subset="timestamp", inplace=True)
        df.sort_values("timestamp", inplace=True)
        df.set_index("timestamp", inplace=True)
        return df

    async def fetch_winning_5m(self):
        """
        Backtest bittikten sonra KÂRLI veya TSL-HIT tradelerin sembollerinin
        5m verisini çek. Tüm universe yerine yalnızca gerekli semboller → hızlı.
        Filtre: pnl_usdt > 0 VEYA exit_reason == 'TSL-HIT'
        """
        winners = [t for t in self.trades if t.pnl_usdt > 0 or t.exit_reason == "TSL-HIT"]
        if not winners:
            return
        syms = list(dict.fromkeys(t.symbol for t in winners))  # sıra koruyarak unique
        print(f"\n  📥 5m doğrulama için {len(syms)} sembol çekiliyor: "
              f"{', '.join(s.replace('/USDT','').replace(':USDT','') for s in syms)} ...")
        exchange = _make_binance_exchange()
        for sym in syms:
            df5 = await self._fetch_5m_via(exchange, sym)
            if not df5.empty:
                self.all_data_5m[sym] = df5
                print(f"  ✔ {sym.replace('/USDT','').replace(':USDT','')}: {len(df5)} adet 5m mum")
            else:
                print(f"  ⚠ {sym}: 5m veri boş")
        await exchange.close()
        print()

    async def _fetch_5m_via(self, exchange, symbol: str) -> pd.DataFrame:
        since_ms = int(self.start_dt.timestamp() * 1000)
        until_ms = int(self.end_dt.timestamp() * 1000)
        candles: list = []
        cur = since_ms
        while True:
            try:
                batch = await exchange.fetch_ohlcv(symbol, '5m', since=cur, limit=1000)
            except Exception as e:
                log.warning(f"  {symbol} 5m hata: {e}")
                break
            if not batch:
                break
            candles.extend(batch)
            last_ts = batch[-1][0]
            if last_ts >= until_ms or len(batch) < 1000:
                break
            cur = last_ts + 1
            await asyncio.sleep(0.15)
        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame(candles, columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.drop_duplicates(subset="timestamp", inplace=True)
        df.sort_values("timestamp", inplace=True)
        df.set_index("timestamp", inplace=True)
        return df

    # ─────────────────────────────────────────────────────────────────
    # D) Tüm universe için veri indir (batch — rate-limit dostu)
    # ─────────────────────────────────────────────────────────────────
    async def load_data(self):
        """
        1. Universe'ü canlı çek.
        2. Her coin için tarihsel 4H OHLCV indir.
        3. En az 30 mumu olan coinleri kabul et.
        """
        await self._init_exchange()
        self.universe = await self._fetch_universe()

        start_str = self.start_dt.strftime("%d.%m.%Y")
        end_str   = self.end_dt.strftime("%d.%m.%Y")
        total     = len(self.universe)

        print(f"\n📥 {total} sembol için {start_str} → {end_str} arasındaki 4H veri indiriliyor…")
        print("   (Binance public API — API key gerekmez)")
        print("   (Bu işlem 3-8 dakika sürebilir — sabırlı olun ☕)\n")

        batch_size = 4  # aynı anda 4 sembol (rate-limit dostu)
        loaded = 0
        skipped = 0

        for i in range(0, total, batch_size):
            batch   = self.universe[i : i + batch_size]
            tasks   = [self._fetch_ohlcv(sym) for sym in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Minimum mum: pump window (6) + en az 2 analiz mumu = 8
            min_candles = Config.PUMP_WINDOW_CANDLES + 2

            for sym, df in zip(batch, results):
                if isinstance(df, Exception):
                    skipped += 1
                    continue
                if not isinstance(df, pd.DataFrame) or df.empty or len(df) < min_candles:
                    skipped += 1
                    continue
                self.all_data[sym] = df
                loaded += 1

            # İlerleme çubuğu
            done    = min(i + batch_size, total)
            bar_len = 45
            filled  = int(bar_len * done / total)
            bar     = "█" * filled + "░" * (bar_len - filled)
            print(f"\r  [{bar}] {done}/{total}  ✔ {loaded} yüklendi  ✗ {skipped} atlandı",
                  end="", flush=True)

            await asyncio.sleep(0.25)

        print(f"\n\n✅ {loaded} sembol hazır ({skipped} atlandı, yetersiz veri veya hata).")
        await self.exchange.close()

    # ─────────────────────────────────────────────────────────────────
    # E) Cross-sembol bar-by-bar simülasyon  (v3 — Refined Scalper)
    # ─────────────────────────────────────────────────────────────────
    def run_backtest(self):
        """
        Tüm coinleri AYNI 4H zaman çizelgesinde simüle eder.

        Module 1: Günlük kazanç ≥ %30 → Top 10 gainer watchlist
        Module 2: Kırmızı 4H mum → SHORT
        Module 3: SL = entry + %15 (entry × 1.15), TP = entry×0.92, BE @ %4 düşüş
        Module 4: Çıkış yalnızca SL / BE / TSL ile
        Module 5: 24h cooldown sonra yeniden giriş
        """
        print("\n" + "=" * 68)
        print("  ✦ FULL UNIVERSE BACKTEST v3 — Refined Scalper")
        print(f"  Sermaye    : {self.capital:.2f}$")
        print(f"  Kaldıraç   : x{Config.LEVERAGE}")
        print(f"  Max Trade  : {Config.MAX_ACTIVE_TRADES}  (aynı anda)")
        risk_pct = Config.risk_per_trade_pct()
        print(f"  Risk/Trade : %{risk_pct}  ({self.capital * risk_pct / 100:.2f}$ başlangıç)")
        print(f"  Sembol     : {len(self.all_data)} adet")
        print(f"  Dönem      : {self.start_dt.strftime('%d.%m.%Y')} → {self.end_dt.strftime('%d.%m.%Y')} (4H barlar)")
        print("=" * 68)

        # ── Ön-hesaplamalar ───────────────────────────────────────────
        # 1) Tüm 4H timestamp birleşimi
        #    sim_start: pump penceresi için start_dt'den 6 mum (24 saat) önce başla.
        #    Böylece start_dt sınırına denk gelen pump+ilk kırmızı senaryosu kaçırılmaz.
        sim_start = self.start_dt - timedelta(hours=Config.PUMP_WINDOW_CANDLES * 4)
        all_timestamps = sorted(
            ts for ts in set().union(*[set(df.index) for df in self.all_data.values()])
            if sim_start <= ts <= self.end_dt
        )

        equity         = self.capital
        self.equity_curve = [equity]
        active: Dict[str, TradeRecord] = {}
        watchlist: Dict[str, dict]     = {}   # sym → pump_info
        post_exit_price: Dict[str, float] = {}  # sym → son çıkış fiyatı (yeni push takibi)
        new_push: Dict[str, bool]         = {}  # sym → çıkış sonrası yeni push oldu mu?
        consumed_signals: set             = set()  # İlk kırmızısı tüketilmiş pump sinyalleri
        max_concurrent = 0
        total_bars     = len(all_timestamps)

        # Breakeven price drop threshold: %4 düşüş
        be_price_drop_pct = Config.BREAKEVEN_DROP_PCT

        for bar_num, ts in enumerate(all_timestamps):
            # İlerleme (her 100 barda bir)
            if bar_num % 100 == 0:
                pct = bar_num / total_bars * 100 if total_bars else 0
                print(f"\r  Sim: %{pct:5.1f}  Bar {bar_num}/{total_bars}"
                      f"  Equity: {equity:8.4f}$  Aktif: {len(active)}  "
                      f"Watchlist: {len(watchlist)}",
                      end="", flush=True)

            bar_str = ts.strftime("%d.%m.%Y %H:%M")

            # ══ (1) AÇIK TRADE'LERİN TSL / GREEN KONTROL ════════════
            closed = []
            for sym, trade in list(active.items()):
                if sym not in self.all_data:
                    continue
                df = self.all_data[sym]
                if ts not in df.index:
                    continue
                bar = df.loc[ts]

                # ── KURAL 1: ÖNCE STOP KONTROLÜ (En Kötü Senaryo) ────
                # 4H mum içinde fiyatın önce nereye gittiğini bilemeyiz.
                # Gerçek exchange'de stop_market emri HIGH'a değer değmez
                # tetiklenir; LOW'daki TSL aktivasyonundan ÖNCE gelmiş olabilir.
                # Bu yüzden HIGH stop'a değdiyse → TSL/BE hesabına bakmadan
                # direkt zarar ile kapat. Sahte kârlı TSL çıkışını engeller.
                if bar["high"] >= trade.stop_loss:
                    exit_p  = trade.stop_loss
                    raw_pnl = (trade.entry_price - exit_p) / trade.entry_price
                    pnl_usd = trade.position_size_usdt * trade.leverage * raw_pnl
                    pnl_usd = max(pnl_usd, -trade.position_size_usdt)  # Max kayıp = margin (likit sınırı)
                    reason  = "TSL-HIT" if trade.tsl_active else "STOP-LOSS"
                    trade.exit_time   = bar_str
                    trade.exit_price  = exit_p
                    trade.exit_reason = reason
                    trade.pnl_pct     = round(raw_pnl * 100, 4)
                    trade.pnl_usdt    = round(pnl_usd, 4)
                    equity += pnl_usd
                    self.equity_curve.append(equity)
                    self.trades.append(trade)
                    closed.append(sym)
                    consumed_signals.discard(sym)  # Çıkış sonrası yeniden girişe izin ver
                    post_exit_price[sym] = exit_p
                    new_push[sym] = False
                    print(f"\n  [{bar_str}] 🔴 {reason:<8} {sym:<16}"
                          f" exit: {exit_p:.6f}  PnL: {pnl_usd:>+8.4f}$"
                          f"  Equity: {equity:.4f}$")
                    continue

                # ── KURAL 2: TSL VE BE HESAPLAMASI ───────────────────
                # HIGH stop'a değmediyse fiyat güvenli bölgededir.
                # Artık bar["low"] bazlı Breakeven ve Trailing Stop
                # güncellemelerini güvenle yapabiliriz.

                # Breakeven — %BE_DROP düşüşte SL = entry
                if not trade.breakeven_triggered:
                    drop_pct = (trade.entry_price - bar["close"]) / trade.entry_price * 100.0
                    if drop_pct >= be_price_drop_pct:
                        trade.stop_loss = trade.entry_price
                        trade.sl_moved_to_be = True
                        trade.breakeven_triggered = True
                        print(f"\n  [{bar_str}] ⚡ BE {sym:<16}"
                              f" Düşüş: %{drop_pct:.1f}")

                # TSL aktivasyonu ve güncelleme (low bazlı)
                low_drop_pct = (trade.entry_price - bar["low"]) / trade.entry_price * 100.0
                if not trade.tsl_active:
                    if low_drop_pct >= Config.TSL_ACTIVATION_DROP_PCT:
                        trade.tsl_active = True
                        trade.lowest_low_reached = bar["low"]
                        new_sl = trade.lowest_low_reached * (1 + Config.TSL_TRAIL_PCT / 100.0)
                        trade.stop_loss = min(trade.stop_loss, new_sl)
                        print(f"\n  [{bar_str}] 🎯 TSL-AKT {sym:<14}"
                              f" Low: {trade.lowest_low_reached:.6f}  SL → {trade.stop_loss:.6f}")
                else:
                    if bar["low"] < trade.lowest_low_reached:
                        trade.lowest_low_reached = bar["low"]
                        new_sl = trade.lowest_low_reached * (1 + Config.TSL_TRAIL_PCT / 100.0)
                        trade.stop_loss = min(trade.stop_loss, new_sl)

                # ── KURAL 3: MUM İÇİ BOUNCE (SEKME) KONTROLÜ ─────────
                # TSL aktifleşti/güncellendi ve yeni bir stop belirlendi.
                # Mum kapanışı bu yeni stop seviyesinin ÜSTÜNDE kaldıysa
                # fiyat dip yapıp sekerken TSL'i patlatmış demektir → kapat.
                # (Kural 1'den farkı: burada HIGH değil CLOSE kullanılır;
                #  çünkü stop yeni OLUŞTU ve close zaten üstte kapandı.)
                if trade.tsl_active and bar["close"] >= trade.stop_loss:
                    exit_p  = trade.stop_loss
                    raw_pnl = (trade.entry_price - exit_p) / trade.entry_price
                    pnl_usd = trade.position_size_usdt * trade.leverage * raw_pnl
                    pnl_usd = max(pnl_usd, -trade.position_size_usdt)  # Max kayıp = margin
                    trade.exit_time   = bar_str
                    trade.exit_price  = exit_p
                    trade.exit_reason = "TSL-HIT"
                    trade.pnl_pct     = round(raw_pnl * 100, 4)
                    trade.pnl_usdt    = round(pnl_usd, 4)
                    equity += pnl_usd
                    self.equity_curve.append(equity)
                    self.trades.append(trade)
                    closed.append(sym)
                    consumed_signals.discard(sym)  # Çıkış sonrası yeniden girişe izin ver
                    post_exit_price[sym] = exit_p
                    new_push[sym] = False
                    print(f"\n  [{bar_str}] 🎯 TSL-HIT (bounce) {sym:<12}"
                          f" exit: {exit_p:.6f}  PnL: {pnl_usd:>+8.4f}$"
                          f"  Equity: {equity:.4f}$")
                    continue

                # ── KURAL 4: ZARARDA YEŞİL MUM (GREEN-10) ────────────
                # Kural 1-3 atlatıldıysa trade hâlâ açık; yeşil mum kontrolü yap.
                if bar["close"] > bar["open"] and bar["close"] > trade.entry_price:
                    green_body_pct = (bar["close"] - bar["open"]) / bar["open"] * 100.0
                    # Zararda tek yeşil mum gövdesi >= %10 → anında kapat (reversal olmadı)
                    if green_body_pct >= Config.GREEN_LOSS_SINGLE_BODY_PCT:
                        exit_p  = bar["close"]
                        raw_pnl = (trade.entry_price - exit_p) / trade.entry_price
                        pnl_usd = trade.position_size_usdt * trade.leverage * raw_pnl
                        pnl_usd = max(pnl_usd, -trade.position_size_usdt)  # Max kayıp = margin
                        trade.exit_time   = bar_str
                        trade.exit_price  = exit_p
                        trade.exit_reason = "GREEN-10"
                        trade.pnl_pct     = round(raw_pnl * 100, 4)
                        trade.pnl_usdt    = round(pnl_usd, 4)
                        equity += pnl_usd
                        self.equity_curve.append(equity)
                        self.trades.append(trade)
                        closed.append(sym)
                        consumed_signals.discard(sym)  # Çıkış sonrası yeniden girişe izin ver
                        post_exit_price[sym] = exit_p
                        new_push[sym] = False
                        print(f"\n  [{bar_str}] 🟠 GREEN-10  {sym:<16}"
                              f" Gövde: %{green_body_pct:.1f}  exit: {exit_p:.6f}  PnL: {pnl_usd:>+8.4f}$"
                              f"  Equity: {equity:.4f}$")
                        continue
                    # Küçük zararda yeşil → sayacı artır, 2'de kapat
                    trade.consec_green_loss += 1
                    if trade.consec_green_loss >= 2:
                        exit_p  = bar["close"]
                        raw_pnl = (trade.entry_price - exit_p) / trade.entry_price
                        pnl_usd = trade.position_size_usdt * trade.leverage * raw_pnl
                        pnl_usd = max(pnl_usd, -trade.position_size_usdt)  # Max kayıp = margin
                        trade.exit_time   = bar_str
                        trade.exit_price  = exit_p
                        trade.exit_reason = "2xGREEN-LOSS"
                        trade.pnl_pct     = round(raw_pnl * 100, 4)
                        trade.pnl_usdt    = round(pnl_usd, 4)
                        equity += pnl_usd
                        self.equity_curve.append(equity)
                        self.trades.append(trade)
                        closed.append(sym)
                        consumed_signals.discard(sym)  # Çıkış sonrası yeniden girişe izin ver
                        post_exit_price[sym] = exit_p
                        new_push[sym] = False
                        print(f"\n  [{bar_str}] 🟠 2xGREEN-LOSS {sym:<16}"
                              f" exit: {exit_p:.6f}  PnL: {pnl_usd:>+8.4f}$"
                              f"  Equity: {equity:.4f}$")
                        continue
                else:
                    trade.consec_green_loss = 0  # Kırmızı veya kârda yeşil → sayacı sıfırla

            for sym in closed:
                del active[sym]

            # ══ (2) WATCHLİST GÜNCELLE (6-bar rolling window net pump) ═══════════════
            candidates: List[tuple] = []  # (gain_pct, sym, pump_info)
            n = Config.PUMP_WINDOW_CANDLES  # 6

            for sym, df in self.all_data.items():
                if sym in active:
                    continue
                if ts not in df.index:
                    continue

                ts_idx = df.index.get_loc(ts)
                if ts_idx < n:
                    continue

                window = [df.iloc[ts_idx - n + k] for k in range(n)]

                if any(c["low"] <= 0 or pd.isna(c["high"]) for c in window):
                    continue

                # Koşul 1: En az 4 yeşil mum (sıralı olması şart değil)
                green_count = sum(1 for c in window if c["close"] > c["open"])
                if green_count < Config.PUMP_MIN_GREEN_COUNT:  # 4
                    continue

                # Koşul 2: pencere başlangıcının gövde tabanı → mevcut barın kapanışı >= PUMP_MIN_PCT
                pump_high      = max(c["high"] for c in window)
                pump_start_low = window[0]["low"]   # Rapor/SL referansı için saklanır
                pump_start_ref = min(window[0]["open"], window[0]["close"])  # Gövde tabanı (wick dahil değil)
                current_close  = df.iloc[ts_idx]["close"]
                if pump_start_ref <= 0:
                    continue
                net_gain_pct   = (current_close - pump_start_ref) / pump_start_ref * 100.0
                if net_gain_pct < Config.PUMP_MIN_PCT:
                    continue

                candidates.append((net_gain_pct, sym, {
                    "pump_pct": net_gain_pct,
                    "pump_low": pump_start_low,
                    "pump_high": pump_high,
                }))

            # Top 10 gainer seç
            candidates.sort(key=lambda x: x[0], reverse=True)
            # NOT: consumed_signals pump listesinden geçici düşşe göre temizlenmez.
            # Sadece pozisyon kapatıldığında (SL/TSL/GREEN-LOSS) discard edilir.

            # TOP_N dışındaki pump adaylarının ilk geçerli kırmızı mumunu tüket
            # (coin ileride TOP_N'e girdiğinde 2. kırmızıdan açılmasını önler — VVV bug fix)
            _top_n_syms = {sym for _, sym, _ in candidates[:Config.TOP_N_GAINERS]}
            for _, _sym, _info in candidates:
                if _sym in _top_n_syms or _sym in consumed_signals:
                    continue
                if _sym not in self.all_data:
                    continue
                _df2 = self.all_data[_sym]
                if ts not in _df2.index:
                    continue
                _b2 = _df2.loc[ts]
                if _b2["close"] >= _b2["open"]:
                    continue  # yeşil mum, giriş şartı yok
                _rb2 = (_b2["open"] - _b2["close"]) / _b2["open"] * 100.0
                if _rb2 < Config.ENTRY_RED_BODY_MIN_PCT:
                    continue  # gövde yeterli değil
                if _b2["close"] >= _info["pump_high"]:
                    continue  # kapanış pump_high'ın üstünde
                consumed_signals.add(_sym)  # ilk kırmızı tüketildi

            new_watchlist: Dict[str, dict] = {}
            for _, sym, info in candidates[:Config.TOP_N_GAINERS]:
                if sym in consumed_signals:
                    continue  # İlk kırmızısı tüketildi — yeni pump oluşana kadar bekle
                # Mevcut pump_high'ı koru (sürekli güncelle)
                if sym in watchlist:
                    info["pump_high"] = max(info["pump_high"], watchlist[sym]["pump_high"])
                new_watchlist[sym] = info
            watchlist = new_watchlist

            # ══ (3) GİRİŞ: Kırmızı mum → SHORT ════════════════════
            # Gainers sıralı (en yüksek pump_pct önce)
            sorted_wl = sorted(watchlist.items(), key=lambda x: x[1]["pump_pct"], reverse=True)

            for sym, pump_info in sorted_wl:
                if sym in active or sym not in self.all_data:
                    continue
                df = self.all_data[sym]
                if ts not in df.index:
                    continue

                bar = df.loc[ts]

                # Module 5: Yeni push takibi ve koşulu
                if sym in post_exit_price:
                    if bar["high"] > post_exit_price[sym]:
                        new_push[sym] = True
                    if not new_push.get(sym, True):
                        continue  # Çıkış sonrası yeni push bekleniyor

                # Module 2: Kırmızı mum → SHORT
                if bar["close"] >= bar["open"]:
                    continue  # Yeşil mum, giriş yok

                # Solid Red: gövde en az %X düşüş olmalı (doji filtresi)
                red_body_pct = (bar["open"] - bar["close"]) / bar["open"] * 100.0

                # GERÇEKÇİ GİRİŞ: sinyal barı kapanınca market order → sonraki 5m open
                _entry_ts_fu = ts + pd.Timedelta(hours=4)
                _df5m_fu     = getattr(self, "all_data_5m", {}).get(sym)
                if _df5m_fu is not None and _entry_ts_fu in _df5m_fu.index:
                    entry_p    = _df5m_fu.loc[_entry_ts_fu]["open"]
                    entry_time_fu = _entry_ts_fu.strftime("%d.%m.%Y %H:%M")
                else:
                    _ts_idx_e  = df.index.get_loc(ts)
                    if _ts_idx_e + 1 < len(df):
                        entry_p    = df.iloc[_ts_idx_e + 1]["open"]
                        entry_time_fu = df.index[_ts_idx_e + 1].strftime("%d.%m.%Y %H:%M")
                    else:
                        entry_p    = bar["close"]
                        entry_time_fu = bar_str

                # Module 2b: Pump zirvesinin altına düşmeli (peak geçildi teyidi)
                if entry_p >= pump_info["pump_high"]:
                    pump_info["pump_high"] = max(pump_info["pump_high"], bar["high"])
                    continue  # Fiyat hâlâ pump zirvesinde — peak güncellendi, giriş yok

                # ─── İLK GEÇERLİ KIRMIZI MUM — sinyal bu bar tüketildi ────────────────
                # Gövde küçükse (≤%2) sinyal yanmaz, bir sonraki kırmızı mumda tekrar değerlendirilir
                if red_body_pct < Config.ENTRY_RED_BODY_MIN_PCT:
                    continue  # Cılız kırmızı: bekle, sinyal yanmadı
                # Önceki mum yeşil ve gövdesi max %30 olmalı (sahte kırmızı filtresi)
                _ts_idx = df.index.get_loc(ts)
                if _ts_idx == 0:
                    continue
                prev_bar = df.iloc[_ts_idx - 1]
                if prev_bar["close"] <= prev_bar["open"]:
                    continue  # önceki mum yeşil değil — giriş yok
                prev_body_pct = (prev_bar["close"] - prev_bar["open"]) / prev_bar["open"] * 100.0
                if prev_body_pct >= Config.ANTI_ROCKET_SINGLE_CANDLE_PCT:  # >= : canlı bot ile aynı
                    continue  # önceki yeşil mum fazla büyük — sahte kırmızı riski

                consumed_signals.add(sym)

                if equity < 100.0:
                    print(f"\n  [{bar_str}] ⛔ EQUİTY<100$ ({equity:.0f}$): {sym} — sinyal iptal")
                    continue

                if len(active) >= Config.MAX_ACTIVE_TRADES:
                    print(f"\n  [{bar_str}] ⛔ SLOT DOLU — ilk kırmızı kaçırıldı: {sym} — sinyal iptal")
                    continue

                # Dinamik kaldıraç: 100-200$ arası → 4x, 200$+ → 3x
                lev = 4 if equity < 200.0 else Config.LEVERAGE

                # SL: Giriş fiyatının %15 üstü (entry × 1.15)
                sl = entry_p * (1 + Config.SL_ABOVE_ENTRY_PCT / 100.0)

                # Pozisyon büyüklüğü
                if equity < 200.0:
                    pos_margin = equity  # Tek pozisyon, tüm equity
                else:
                    pos_margin = equity / Config.MAX_ACTIVE_TRADES

                trade = TradeRecord(
                    symbol             = sym,
                    side               = "SHORT",
                    entry_time         = entry_time_fu,
                    entry_price        = entry_p,
                    stop_loss          = sl,
                    initial_stop_loss  = sl,
                    tp1_price          = 0.0,
                    tp2_price          = 0.0,
                    position_size_usdt = pos_margin,
                    remaining_pct      = 1.0,
                    pump_pct           = pump_info["pump_pct"],
                    pump_high          = pump_info["pump_high"],
                    pump_low           = pump_info["pump_low"],
                    entry_candle_open  = entry_p,
                    leverage           = lev,
                )
                active[sym] = trade
                max_concurrent = max(max_concurrent, len(active))

                print(f"\n  [{entry_time_fu}] ✅ SHORT {sym:<16}"
                      f" Giriş: {entry_p:.6f}  SL: {sl:.6f}"
                      f"  Pump: +{pump_info['pump_pct']:.1f}%  [Sinyal: {bar_str}]")

        # ── Backtest sonu: açık trade'leri kapat ─────────────────────
        print("\n\n  ── Açık kalan tradeler kapatılıyor (BT-END) ──")
        for sym, trade in list(active.items()):
            if sym not in self.all_data:
                continue
            df     = self.all_data[sym]
            df_sim = df[df.index <= self.end_dt]
            if df_sim.empty:
                continue
            exit_p = df_sim["close"].iloc[-1]
            raw_pnl = (trade.entry_price - exit_p) / trade.entry_price
            pnl_usd = trade.position_size_usdt * trade.leverage * raw_pnl
            pnl_usd = max(pnl_usd, -trade.position_size_usdt)  # Max kayıp = margin
            trade.exit_time   = df_sim.index[-1].strftime("%d.%m.%Y %H:%M")
            trade.exit_price  = exit_p
            trade.exit_reason = "BT-END"
            trade.pnl_pct     = round(raw_pnl * 100, 4)
            trade.pnl_usdt    = round(pnl_usd, 4)
            equity           += pnl_usd
            self.equity_curve.append(equity)
            self.trades.append(trade)
            print(f"  [BT-END] 🔵 {sym:<16}  exit: {exit_p:.6f}  PnL: {pnl_usd:>+8.4f}$")

        self.equity_curve.append(equity)
        print(f"\n  ⚡ Max eş zamanlı açık trade : {max_concurrent}")
        print(f"  ⚡ Toplam simüle edilen trade : {len(self.trades)}")

        if len(self.trades) == 0:
            print("\n" + "═" * 68)
            print("  🔍  Neden trade oluşmadı?")
            print("═" * 68)
            print(f"  İncelenen sembol: {len(self.all_data)}")
            print(f"  Toplam 4H bar: {total_bars}")
            print(f"  Pump kriteri: Günlük mum kazancı ≥ %{Config.PUMP_MIN_PCT}")
            print(f"  → Öneri: PUMP_MIN_PCT değerini düşürün (örn. 20.0)")
            print("═" * 68)

    # ─────────────────────────────────────────────────────────────────
    # F) Rapor — Backtester.print_report ile aynı format
    # ─────────────────────────────────────────────────────────────────
    def print_report(self):
        """Backtester.print_report'u yeniden kullan (aynı veri formatı)."""
        _dummy = Backtester.__new__(Backtester)
        _dummy.trades       = self.trades
        _dummy.equity_curve = self.equity_curve
        _dummy.capital      = self.capital
        _dummy.symbols      = list(self.all_data.keys())
        _days = int((self.end_dt - self.start_dt).total_seconds() / 86400)
        _dummy.days         = _days
        _dummy.all_data     = self.all_data
        Backtester.print_report(_dummy)

    def verify_profits_5m(self):
        """FullUniverse için 5m doğrulama — Backtester.verify_profits_5m'i yeniden kullanır."""
        _dummy = Backtester.__new__(Backtester)
        _dummy.trades       = self.trades
        _dummy.equity_curve = self.equity_curve
        _dummy.capital      = self.capital
        _dummy.all_data_5m  = getattr(self, "all_data_5m", {})
        Backtester.verify_profits_5m(_dummy)


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 4 — YALNIZCA TARAMA (SCAN) MODU
# ══════════════════════════════════════════════════════════════════════════

async def run_scan_only():
    """
    Canlı piyasa verisini çekerek pump olan coinleri göster.
    Trade açmaz, sadece watchlist oluşturur.
    """
    bot = PumpSnifferBot()
    try:
        await bot.scan_universe()

        if bot.watchlist:
            print("\n" + "═" * 68)
            print("  🚨  AKTİF PUMP WATCHLİST")
            print("═" * 68)
            for sym, item in sorted(bot.watchlist.items(),
                                     key=lambda x: x[1].pump_pct, reverse=True):
                print(f"  {sym:<18}  Pump: +{item.pump_pct:>7.2f}%  |  "
                      f"Dip: {item.pump_low:.6f}  |  Zirve: {item.pump_high:.6f}")

            # Her biri için tetikleme durumunu kontrol et
            print("\n  🎯  Tetikleme Kontrolü:")
            print("  " + "─" * 60)
            for sym, item in bot.watchlist.items():
                try:
                    df = await bot.fetch_ohlcv(sym, Config.TIMEFRAME,
                                               limit=Config.BB_LENGTH + 10)
                    signal = PumpSnifferBot.check_entry_signal(df, item.pump_high)
                    status = "✅ SİNYAL AKTİF" if signal["triggered"] else "⏳ Bekleniyor"
                    reasons = "  ".join(signal["reasons"]) if signal["reasons"] else "—"
                    print(f"  {sym:<18}  {status}  Skor: {signal['score']}/4  |  {reasons}")
                except Exception as e:
                    print(f"  {sym:<18}  ❌ Hata: {e}")
        else:
            print("\n  ℹ️ Şu anda pump kriterini karşılayan coin bulunamadı.")

    finally:
        await bot.exchange.close()


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 5 — MAIN (Giriş Noktası)
# ══════════════════════════════════════════════════════════════════════════

async def main_backtest(full_universe: bool = False,
                        start_dt: datetime = None, end_dt: datetime = None):
    """
    Backtest modunu çalıştır.
    full_universe=True → Binance'den canlı universe çek, tüm coinleri test et.
    full_universe=False → Sadece Config.BACKTEST_SYMBOLS listesini test et.
    start_dt/end_dt → Belirli tarih aralığı (None ise son BACKTEST_DAYS gün kullanılır).
    """
    if full_universe:
        bt = FullUniverseBacktester(start_dt=start_dt, end_dt=end_dt)
    else:
        bt = Backtester(start_dt=start_dt, end_dt=end_dt)
    await bt.load_data()
    bt.run_backtest()
    bt.print_report()
    # Kârlı tradeler 5m ile yeniden doğrula
    # FullUniverse: önce yalnızca kazanılan tradeler için 5m çek
    if full_universe and hasattr(bt, 'fetch_winning_5m'):
        await bt.fetch_winning_5m()
    bt.verify_profits_5m()


async def main_live():
    """Canlı bot modunu çalıştır."""
    bot = PumpSnifferBot()
    await bot.run()


def main():
    # ══════════════════════════════════════════════════════════════════════════
    # Container/Northflank için otomatik canlı mod (interaktif menü atlama)
    # ══════════════════════════════════════════════════════════════════════════
    import os
    auto_live = os.getenv("AUTO_LIVE", "false").lower() == "true"
    
    if auto_live:
        mod = "DEMO 🧪" if Config.DEMO_MODE else "CANLI ⚠️"
        print()
        print("=" * 56)
        print("   PUMP & DUMP REVERSION BOT — Binance Futures")
        print("=" * 56)
        print()
        print(f"  🚀 AUTO_LIVE MODE: {mod}")
        if not Config.DEMO_MODE:
            print("  ⚠️  GERÇEK PARA İLE İŞLEM AÇILACAK!")
        print()
        print("=" * 56)
        print()
        log.info("Container ortamı tespit edildi, otomatik canlı moda geçiliyor...")
        asyncio.run(main_live())
        return
    
    # ══════════════════════════════════════════════════════════════════════════
    # Normal interaktif menü (local development)
    # ══════════════════════════════════════════════════════════════════════════
    print()
    print("=" * 56)
    print("   PUMP & DUMP REVERSION BOT — Binance Futures")
    print("=" * 56)
    print()
    print("  Bir seçenek girin:")
    print()
    print("  1 — Backtest (Geçen ay, TÜM Binance coinleri)")
    print("      Sermaye: {}$  |  Dönem: son {} gün".format(
        int(Config.BACKTEST_INITIAL_CAPITAL), Config.BACKTEST_DAYS))
    print()
    print("  2 — Backtest (Hızlı, sadece 8 popüler coin)")
    print()
    print("  3 — Pump Tarama  (Şu anda pump yapan coinleri göster)")
    print()
    print("  4 — Canlı Bot  ⚠️  (Gerçek / Demo işlem açar)")
    print()
    print("=" * 56)

    secim = input("  Seçiminiz (1/2/3/4): ").strip()

    if secim == "1":
        print()
        # Sermaye özelleştirme
        cap_input = input(
            f"  Başlangıç sermayesi? [Enter = {Config.BACKTEST_INITIAL_CAPITAL}$]: "
        ).strip()
        if cap_input:
            try:
                Config.BACKTEST_INITIAL_CAPITAL = float(cap_input)
            except ValueError:
                print("  Geçersiz değer, varsayılan kullanılıyor.")

        # Tarih aralığı özelleştirme
        bt_start_dt = None
        bt_end_dt   = None
        start_input = input("  Başlangıç tarihi? (GG.AA.YYYY, örn. 09.02.2026) [Enter = son 31 gün]: ").strip()
        if start_input:
            try:
                bt_start_dt = datetime.strptime(start_input, "%d.%m.%Y")
                end_input = input("  Bitiş tarihi? (GG.AA.YYYY, örn. 15.02.2026) [Enter = bugün]: ").strip()
                bt_end_dt = datetime.strptime(end_input, "%d.%m.%Y") if end_input else datetime.now()
                # end_dt günün sonuna al (23:59 UTC)
                bt_end_dt = bt_end_dt.replace(hour=23, minute=59, second=59)
            except ValueError:
                print("  Geçersiz tarih formatı, son 31 gün kullanılıyor.")
                bt_start_dt = None
                bt_end_dt   = None

        if bt_start_dt:
            print()
            print(f"  Başlatılıyor: TÜM coinler  |  "
                  f"{Config.BACKTEST_INITIAL_CAPITAL}$  |  "
                  f"{bt_start_dt.strftime('%d.%m.%Y')} → {bt_end_dt.strftime('%d.%m.%Y')}")
            asyncio.run(main_backtest(full_universe=True, start_dt=bt_start_dt, end_dt=bt_end_dt))
        else:
            days_input = input(
                f"  Kaç günlük backtest? [Enter = {Config.BACKTEST_DAYS} gün]: "
            ).strip()
            if days_input:
                try:
                    Config.BACKTEST_DAYS = int(days_input)
                except ValueError:
                    print("  Geçersiz değer, varsayılan kullanılıyor.")
            print()
            print(f"  Başlatılıyor: TÜM coinler  |  "
                  f"{Config.BACKTEST_INITIAL_CAPITAL}$  |  son {Config.BACKTEST_DAYS} gün")
            asyncio.run(main_backtest(full_universe=True))

    elif secim == "2":
        print()
        cap_input = input(
            f"  Başlangıç sermayesi? [Enter = {Config.BACKTEST_INITIAL_CAPITAL}$]: "
        ).strip()
        if cap_input:
            try:
                Config.BACKTEST_INITIAL_CAPITAL = float(cap_input)
            except ValueError:
                pass

        # Tarih aralığı özelleştirme
        bt_start_dt = None
        bt_end_dt   = None
        start_input = input("  Başlangıç tarihi? (GG.AA.YYYY, örn. 01.01.2026) [Enter = son 31 gün]: ").strip()
        if start_input:
            try:
                bt_start_dt = datetime.strptime(start_input, "%d.%m.%Y")
                end_input = input("  Bitiş tarihi? (GG.AA.YYYY, örn. 12.01.2026) [Enter = bugün]: ").strip()
                bt_end_dt = datetime.strptime(end_input, "%d.%m.%Y") if end_input else datetime.now()
                bt_end_dt = bt_end_dt.replace(hour=23, minute=59, second=59)
            except ValueError:
                print("  Geçersiz tarih formatı, son 31 gün kullanılıyor.")
                bt_start_dt = None
                bt_end_dt   = None

        print()
        if bt_start_dt:
            print(f"  Başlatılıyor: 8 sembol  |  {Config.BACKTEST_INITIAL_CAPITAL}$  |  "
                  f"{bt_start_dt.strftime('%d.%m.%Y')} → {bt_end_dt.strftime('%d.%m.%Y')}")
            asyncio.run(main_backtest(full_universe=False, start_dt=bt_start_dt, end_dt=bt_end_dt))
        else:
            print(f"  Başlatılıyor: 8 sembol  |  {Config.BACKTEST_INITIAL_CAPITAL}$")
            asyncio.run(main_backtest(full_universe=False))

    elif secim == "3":
        print()
        print("  Pump taraması başlatılıyor…")
        asyncio.run(run_scan_only())

    elif secim == "4":
        print()
        mod = "DEMO 🧪" if Config.DEMO_MODE else "CANLI ⚠️"
        print("=" * 56)
        print(f"  MOD: {mod}")
        if not Config.DEMO_MODE:
            print("  ⚠️  GERÇEK PARA İLE İŞLEM AÇILACAK!")
        print("=" * 56)
        onay = input("  Devam etmek için 'EVET' yazın: ").strip()
        if onay.upper() == "EVET":
            asyncio.run(main_live())
        else:
            print("  İptal edildi.")

    else:
        print("  ❌ Geçersiz seçim. Lütfen 1, 2, 3 veya 4 girin.")


if __name__ == "__main__":
    main()
