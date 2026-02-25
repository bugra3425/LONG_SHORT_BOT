# ╔══════════════════════════════════════════════════════════════════════╗
# ║          PUMP & DUMP REVERSION BOT — HIZLI TEST PARAMETRELERİ        ║
# ║  DİKKAT: Bu ayarlar SADECE risk motorunu (BE, TSL, SL) test etmek    ║
# ║  içindir. Gerçek trade için kullanmayınız!                           ║
# ╚══════════════════════════════════════════════════════════════════════╝

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 1 — ZAMAN DİLİMİ (Hiper-Aktif Mod)
# ──────────────────────────────────────────────────────────────────────

TIMEFRAME = "5m"

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 2 — PUMP TESPİT KOŞULLARI (Mikro Pump)
# ──────────────────────────────────────────────────────────────────────

PUMP_MIN_PCT = 3
PUMP_WINDOW_CANDLES = 6
PUMP_MIN_GREEN_COUNT = 3
PUMP_CANDLE_BODY_MIN_PCT = 0.1
TOP_N_GAINERS = 15
MIN_VOLUME_USDT = 5_000_000.0

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 3 — GİRİŞ TETİKLEYİCİ KOŞULLARI (Anında Giriş)
# ──────────────────────────────────────────────────────────────────────

ENTRY_RED_BODY_MIN_PCT = 0.1
PRE_CANDLE_GREEN_BODY_MAX_PCT = 5.0
ANTI_ROCKET_SINGLE_CANDLE_PCT = 5.0
GREEN_LOSS_SINGLE_BODY_PCT = 0.8

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 4 — STOP-LOSS VE TRAILING STOP (Genişletilmiş İzleme Makası)
# ──────────────────────────────────────────────────────────────────────

# Timeframe başına TSL profil tablosu.
# TIMEFRAME değişkenini değiştirmek yeterli — tüm değerler otomatik güncellenir.
_TSL_PROFILES = {
    "5m": {
        "SL_ABOVE_ENTRY_PCT":      2.5,   # Giriş üstü ilk SL
        "BREAKEVEN_DROP_PCT":      1.5,   # Breakeven tetik düşüş %
        "TSL_ACTIVATION_DROP_PCT": 3.0,   # %3 kâra ulaşıldığında TSL'yi uyandır
        "TSL_TRAIL_PCT":           2.0,   # (callbackRate) En düşük fiyattan %2 yukarı sekince kârı al
    },
    "4h": {
        "SL_ABOVE_ENTRY_PCT":      15.0,  # 4H mumlarda pump'ın son iğnesine dayanabilmek için geniş ilk SL
        "BREAKEVEN_DROP_PCT":      5.0,   # %5 kâra geçince sermayeyi koru (SL -> Entry)
        "TSL_ACTIVATION_DROP_PCT": 8.0,   # %8 kârda iz süren stopu uyandır
        "TSL_TRAIL_PCT":           4.0,   # (callbackRate) En düşük fiyattan %4 yukarı sekince kârı al
    },
}

_active_profile = _TSL_PROFILES.get(TIMEFRAME, _TSL_PROFILES["5m"])

SL_ABOVE_ENTRY_PCT      = _active_profile["SL_ABOVE_ENTRY_PCT"]
# İLK Stop-Loss: Girişin üstünde başlangıç SL.

BREAKEVEN_DROP_PCT      = _active_profile["BREAKEVEN_DROP_PCT"]
# Stage 1 — Breakeven: Fiyat bu kadar %kâra geçtiğinde SL hemen giriş fiyatına çekilsin.

TSL_ACTIVATION_DROP_PCT = _active_profile["TSL_ACTIVATION_DROP_PCT"]
# Stage 2 — TSL Aktivasyonu: Fiyat bu kadar %kâra ulaştığında trailing motor devreye girsin.

TSL_TRAIL_PCT           = _active_profile["TSL_TRAIL_PCT"]
# TSL Mesafesi: Fiyat en düşük seviyesindeyken bu % gerisinden takip etsin.

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 5 — RİSK YÖNETİMİ
# ──────────────────────────────────────────────────────────────────────

LEVERAGE = 3
MAX_ACTIVE_TRADES = 5
RISK_PER_TRADE_PCT = 0.5

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 6 — TARAMA ARALIKLARI (Saniye Bazlı Hız)
# ──────────────────────────────────────────────────────────────────────

SCAN_INTERVAL_SEC = 60
WATCHLIST_CHECK_INTERVAL_SEC = 15
MANAGER_INTERVAL_SEC = 5
