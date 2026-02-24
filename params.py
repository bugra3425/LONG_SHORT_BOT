# ╔══════════════════════════════════════════════════════════════════════╗
# ║          PUMP & DUMP REVERSION BOT — PARAMETRE DOSYASI              ║
# ║          Bu dosyayı değiştir → git push → Northflank otomatik       ║
# ║          rebuild yapar ve yeni ayarlarla canlıya başlar.            ║
# ╚══════════════════════════════════════════════════════════════════════╝
#
# ❗ Northflank workflow:
#    1. Bu dosyada değerleri değiştir
#    2. git add params.py && git commit -m "params: ..." && git push
#    3. Northflank otomatik rebuild → yeni parametrelerle bot başlar
#
# ❗ Test ipucu (daha sık sinyal için):
#    TIMEFRAME = "1h"         # 4h yerine 1h (4× daha fazla bar)
#    PUMP_MIN_PCT = 20.0      # Pump eşiğini düşür (daha fazla sinyal)
#    PUMP_WINDOW_CANDLES = 6  # 1h'de 6 mum = 6 saat pencere
# ═══════════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 1 — ZAMAN DİLİMİ
# ──────────────────────────────────────────────────────────────────────

TIMEFRAME = "15m"
# Desteklenen değerler: "15m" | "30m" | "1h" | "2h" | "4h"
# ⚠ Backtest'te hızlı test: "1h" ile 4× daha fazla bar → 4× daha fazla sinyal
# ⚠ Canlı botta: piyasa kapanış mumunu bekler (4h = 4 saatte 1 bar)

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 2 — PUMP TESPİT KOŞULLARİ (Module 1 — Radar)
# ──────────────────────────────────────────────────────────────────────

PUMP_MIN_PCT = 20.0
# Pump penceresi boyunca minimum kazanç yüzdesi (window[0].low → son kapanış)
# Örnek: 30 → son 6 mumda dip'ten kapanışa %30+ çıkış olmalı
# Daha az sinyal istiyorsan artır (35, 40), fazla sinyal istiyorsan düşür (20, 25)

PUMP_WINDOW_CANDLES = 4
# Kaç mumun geçmişine bakılır? (4h × 6 = 24 saat)
# Kısa TF kullanıyorsan da 6 bırakabilirsin (1h × 6 = 6 saat pencere)

PUMP_MIN_GREEN_COUNT = 2
# 6 mumun kaçı yeşil olmalı? (min 4 → steady climb)
# Agresif test için 3'e indirebilirsin

PUMP_CANDLE_BODY_MIN_PCT = 3.0
# Yeşil mum gövdesi minimum yüzdesi (cılız fitilli mumları eliyor)
# Önerilen aralık: 3.0 – 8.0

TOP_N_GAINERS = 10
# Scannerdan kaç coin watchlist'e girer? (en yüksek pump % olanlar)

MIN_VOLUME_USDT = 10_000_000.0
# Pump penceresi toplam hacim limiti (USDT)
# Likitsiz coinleri elemek için — test için 1_000_000 yapabilirsin

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 3 — GİRİŞ TETİKLEYİCİ KOŞULLARİ (Module 2 — Trigger)
# ──────────────────────────────────────────────────────────────────────

ENTRY_RED_BODY_MIN_PCT = 2.0
# Giriş mumunun kırmızı gövdesi minimum yüzdesi
# SHORT girilecek mum güçlü bir kırmızı mum olmalı (zayıf doji girilmez)

PRE_CANDLE_GREEN_BODY_MAX_PCT = 30.0
# Giriş mumundan HEMEN ÖNCE gelen yeşil mumun gövdesi max yüzdesi
# Eğer önceki mum tek başına %30+ çıktıysa → ANTI-ROCKET, giriş yok

ANTI_ROCKET_SINGLE_CANDLE_PCT = 30.0
# Tetikleyiciden önceki tek mumun "anti-rocket" eşiği

GREEN_LOSS_SINGLE_BODY_PCT = 10.0
# Açık SHORT'ta zararda iken gelen yeşil mumun gövdesi >= bu değerse → hemen çık
# Daha erken çık istiyorsan: 7.0 | Daha geç: 15.0

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 4 — STOP-LOSS VE TRAILING STOP (Module 3 — Trade Management)
# ──────────────────────────────────────────────────────────────────────

SL_ABOVE_ENTRY_PCT = 15.0
# İLK Stop-Loss: Giriş fiyatının kaç % üstü?
# entry × (1 + SL_ABOVE_ENTRY_PCT/100)
# Daha dar SL: 10.0 | Daha geniş SL: 20.0

BREAKEVEN_DROP_PCT = 7.0
# Stage 1 — Breakeven: Fiyat entry'den %X aşağı inince SL → entry'e çekilir

TSL_ACTIVATION_DROP_PCT = 7.0
# Stage 2 — TSL Aktivasyonu: Fiyat %X aşağı inince Trailing Stop devreye girer

TSL_TRAIL_PCT = 4.0
# TSL mesafesi: SL = lowest_low × (1 + TSL_TRAIL_PCT/100)
# Dar trailing: 2.0 | Geniş trailing: 6.0

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 5 — RİSK YÖNETİMİ
# ──────────────────────────────────────────────────────────────────────

LEVERAGE = 3
# Kaldıraç (Binance Futures)
# ⚠ Dikkat: 5+ kaldıraç ciddi likidite riski taşır

MAX_ACTIVE_TRADES = 5
# Aynı anda maksimum açık pozisyon sayısı

RISK_PER_TRADE_PCT = 2.0
# Her trade için öz-varlığın (equity) yüzde kaçı riske atılır?
# %2 → 1000$ sermayede 20$ risk/trade

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 6 — TARAMA ARALIKLARI (Canlı Bot)
# ──────────────────────────────────────────────────────────────────────

SCAN_INTERVAL_SEC = 300
# Universe tarama aralığı (saniye). Kaç saniyede bir tüm Binance futures taranır?

WATCHLIST_CHECK_INTERVAL_SEC = 60
# Watchlist sinyal kontrol aralığı (saniye).

MANAGER_INTERVAL_SEC = 5
# Açık trade yönetim döngüsü (saniye). SL, TSL, BE kontrolleri.

# ──────────────────────────────────────────────────────────────────────
#  BÖLÜM 7 — BACKTEST ÖZEL AYARLARI
# ──────────────────────────────────────────────────────────────────────

BACKTEST_DAYS = 31
# Backtest kaç günlük geçmiş veri üzerinde çalışır?

BACKTEST_INITIAL_CAPITAL = 1000.0
# Backtest başlangıç sermayesi (USDT)

BACKTEST_SYMBOLS = [
    # Hızlı backtest (seçenek 2) için kullanılan semboller
    "TRB/USDT", "GAS/USDT", "CYBER/USDT", "LOOM/USDT",
    "YGG/USDT", "VANRY/USDT", "ORDI/USDT", "BIGTIME/USDT",
]
