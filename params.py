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

PUMP_MIN_PCT = 1.5
PUMP_WINDOW_CANDLES = 6
PUMP_MIN_GREEN_COUNT = 3
PUMP_CANDLE_BODY_MIN_PCT = 0.1
TOP_N_GAINERS = 15
MIN_VOLUME_USDT = 500_000.0

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

SL_ABOVE_ENTRY_PCT = 2.5
# İLK Stop-Loss: Girişin %2.5 üstü. 

BREAKEVEN_DROP_PCT = 1.5
# Stage 1 — Breakeven: Fiyat %1.5 kâra (düşüşe) geçtiği an SL hemen giriş fiyatına çekilsin.

TSL_ACTIVATION_DROP_PCT = 3.0
# Stage 2 — TSL Aktivasyonu: Fiyat %3.0 kâra ulaştığında ana takip motoru devreye girsin.

TSL_TRAIL_PCT = 2.0
# TSL Mesafesi: Fiyat en düşük seviyesindeyken %2 gerisinden (yukarısından) takip etsin.

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 5 — RİSK YÖNETİMİ
# ──────────────────────────────────────────────────────────────────────

LEVERAGE = 1
MAX_ACTIVE_TRADES = 5
RISK_PER_TRADE_PCT = 0.5

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 6 — TARAMA ARALIKLARI (Saniye Bazlı Hız)
# ──────────────────────────────────────────────────────────────────────

SCAN_INTERVAL_SEC = 60
WATCHLIST_CHECK_INTERVAL_SEC = 15
MANAGER_INTERVAL_SEC = 5
