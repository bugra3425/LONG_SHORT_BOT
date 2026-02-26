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
GREEN_LOSS_SINGLE_BODY_PCT = 3.0

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 4 — STOP-LOSS VE TRAILING STOP (5m Test Profili)
# ──────────────────────────────────────────────────────────────────────

SL_ABOVE_ENTRY_PCT      = 2.5   # Giriş üstü ilk SL
BREAKEVEN_DROP_PCT      = 1.5   # %1.5 kâra geçince SL → Entry
TSL_ACTIVATION_DROP_PCT = 5.0  # Giriş fiyatının %10 altına fiyat gelince TSL aktif
TSL_TRAIL_PCT           = 2.0   # En düşük fiyattan %5 yukarı sekince pozisyonu kapat

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
