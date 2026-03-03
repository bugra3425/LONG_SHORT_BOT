# ╔══════════════════════════════════════════════════════════════════════╗
# ║              ORİJİNAL DEĞERLER — 4H PROFİL                          ║
# ║  orjinal değerler.py dosyasından yüklendi.                          ║
# ╚══════════════════════════════════════════════════════════════════════╝

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 1 — ZAMAN DİLİMİ
# ──────────────────────────────────────────────────────────────────────

TIMEFRAME = "4h"

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 2 — PUMP TESPİT KOŞULLARI
# ──────────────────────────────────────────────────────────────────────

PUMP_MIN_PCT = 30.0
PUMP_WINDOW_CANDLES = 6
PUMP_MIN_GREEN_COUNT = 4
PUMP_CANDLE_BODY_MIN_PCT = 5.0
TOP_N_GAINERS = 20
MIN_VOLUME_USDT = 10_000_000.0

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 3 — GİRİŞ TETİKLEYİCİ KOŞULLARI
# ──────────────────────────────────────────────────────────────────────

ENTRY_RED_BODY_MIN_PCT = 4.0
PRE_CANDLE_GREEN_BODY_MAX_PCT = 30.0
ANTI_ROCKET_SINGLE_CANDLE_PCT = 22.0
GREEN_LOSS_SINGLE_BODY_PCT = 10.0

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 4 — STOP-LOSS VE TRAILING STOP (4H PROFİL)
# ──────────────────────────────────────────────────────────────────────

SL_ABOVE_ENTRY_PCT      = 15.0  # 4H mumlarda geniş ilk SL
BREAKEVEN_DROP_PCT      = 5.0   # %5 kâra geçince SL → Entry
TSL_ACTIVATION_DROP_PCT = 8.0   # %8 kârda trailing stop devreye girsin
TSL_TRAIL_PCT           = 4.0   # En düşük fiyattan %4 yukarı sekince kârı al

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 5 — RİSK YÖNETİMİ
# ──────────────────────────────────────────────────────────────────────

LEVERAGE = 3
MAX_ACTIVE_TRADES = 5
RISK_PER_TRADE_PCT = 2.0

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 6 — TARAMA ARALIKLARI
# ──────────────────────────────────────────────────────────────────────

# SCAN_INTERVAL_SEC kaldırıldı — prep_scan_loop yönetiyor
WATCHLIST_CHECK_INTERVAL_SEC = 60
MANAGER_INTERVAL_SEC = 5

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 7 — BACKTEST
# ──────────────────────────────────────────────────────────────────────

BACKTEST_DAYS = 31
BACKTEST_INITIAL_CAPITAL = 1000.0
BACKTEST_SYMBOLS = [
    "TRB/USDT", "GAS/USDT", "CYBER/USDT", "LOOM/USDT",
    "YGG/USDT", "VANRY/USDT", "ORDI/USDT", "BIGTIME/USDT",
]
