# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                  BOT AYARLARI — Türkçe Açıklamalı                       ║
# ║                                                                          ║
# ║  Bu dosyayı değiştirip kaydettiğinde backtest/bot otomatik               ║
# ║  yeni değerleri kullanır. params.py yerine bu dosya önceliklidir.        ║
# ╚══════════════════════════════════════════════════════════════════════════╝


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 1 — ZAMAN DİLİMİ
# ══════════════════════════════════════════════════════════════════════════

TIMEFRAME = "4h"
# Mumun zaman dilimi.
# "1h"  → 1 saatlik mum
# "4h"  → 4 saatlik mum  (önerilen)
# "1d"  → Günlük mum


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 2 — PUMP TESPİT KOŞULLARI
#  Bot bir coinin "pump" yaptığını bu kurallara göre belirler.
# ══════════════════════════════════════════════════════════════════════════

PUMP_MIN_PCT = 30.0
# Bir coinin "pump" sayılabilmesi için gereken minimum yükseliş yüzdesi.
# Örnek: 30.0 → coin PUMP_WINDOW_CANDLES mum içinde en az %30 yükselmeli.
# Ölçüm: 7. mumun kapanışı ile 1. mumun gövde tabanı arasındaki fark.

PUMP_WINDOW_CANDLES = 7
# Pump tespitinde geriye kaç muma bakılır.
# Örnek: 7 → Son 7 mumda (4H'de = 28 saat) yeterli yükseliş var mı diye bakar.

PUMP_MIN_GREEN_COUNT = 4
# Pump sayılması için penceredeki minimum yeşil mum sayısı.
# Örnek: 4 → 7 mumun en az 4'ü yeşil olmalı.

TOP_N_GAINERS = 20
# Taramada kaç adet "en çok yükselen coin" izlensin.
# Örnek: 20 → Binance'deki en çok yükselen 20 coin takip edilir.
# Trigger anında en yüksek pump % olan coin önce kontrol edilir (büyükten küçüğe sıralı).
# MAX_ACTIVE_TRADES (5) zaten sınırladığından 20 coin içinde hepsine girilmez.

MIN_VOLUME_USDT = 10_000_000.0
# İzlenecek coinin minimum 24 saatlik hacmi (USDT cinsinden).
# Örnek: 10_000_000 → 10 milyon dolar altı hacimli coinler elenir.

PUMP_CONSECUTIVE_GREEN = 0
# Pump sonrası aynı coine tekrar giriş için gereken bekleme süresi (cooldown).
# 0 → Cooldown yok: koşullar sağlanırsa hemen tekrar girilebilir.
# Örnek: 3 → 12 saat bekle, 6 → 24 saat bekle.


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 3 — GİRİŞ TETİKLEYİCİ KOŞULLARI
#  Bot SHORT pozisyon açmak için bu koşulları arar.
# ══════════════════════════════════════════════════════════════════════════

ENTRY_RED_BODY_MIN_PCT = 4.0
# Giriş sinyali verecek kırmızı mumun minimum gövde yüzdesi.
# Örnek: 4.0 → Kırmızı mumun gövdesi en az %4 olmalı (küçük geri çekilmeler sayılmaz).

# ENTRY_RED_BODY_MAX_PCT — KALDIRILDI
# Büyük kırmızı mum (örn. %35) pump sonrası daha güçlü reversal sinyalidir.
# Pump zaten %30+ gerektirdiğinden %35 düşen kırmızı mum "tren kaçtı" değil,
# "sert dağıtım başladı" anlamına gelir → giriş daha da geçerli.

ANTI_ROCKET_SINGLE_CANDLE_PCT = 9999.0  # DEAKTİF — orijinal değer: 24.0
# Giriş mumundan önceki yeşil mumun maksimum gövde büyüklüğü.
# Örnek: 22.0 → Önceki yeşil mum %22'den büyükse "roket devam ediyor" diye giriş yapılmaz.


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 4 — STOP-LOSS, TRAILING STOP VE ZARARDA YEŞİL MUM ÇIKIŞI
#  Pozisyon koruma kuralları.
# ══════════════════════════════════════════════════════════════════════════

SL_ABOVE_ENTRY_PCT = 15.0
# İlk stop-loss seviyesi: giriş fiyatının kaç yüzde üstünde olsun.
# Örnek: 8.0 → 100$ girişte SL = 108$ (SHORT için yukarısı kayıp).
# 4H mumda geniş tutulması gerekir, küçük tutarsan erken durdurulursun.
# Max kayıp per trade = (1/MAX_ACTIVE_TRADES) × LEVERAGE × SL_ABOVE_ENTRY_PCT
# Örnek: %20 × 5x × %8 = kasanın %8'i per trade

BREAKEVEN_DROP_PCT = 6.0
# Fiyat giriş fiyatının kaç yüzde altına inince SL giriş fiyatına çekilsin (başabaş).
# Örnek: 5.0 → %5 kâra geçince SL → Giriş fiyatı (artık zarar etmezsin).

TSL_ACTIVATION_DROP_PCT = 8.0
# Trailing stop'un devreye girmesi için gereken minimum kâr yüzdesi.
# Örnek: 8.0 → %8 kâra geçince trailing stop aktif olur.

TSL_TRAIL_PCT = 4.0
# Trailing stop: fiyat en düşük seviyesinden kaç yüzde yukarı çıkınca çıkış yapılsın.
# Örnek: 4.0 → Fiyat dibin %4 üstüne çıkınca kâr al.
# Küçük değer → Erken çıkış (daha az kâr ama daha güvenli)
# Büyük değer → Geç çıkış (daha fazla kâr potansiyeli ama kâr erimesi riski)

GREEN_LOSS_SINGLE_BODY_PCT = 10.0
# Zararda iken kapanmış yeşil mumun gövdesi bu değere ulaşırsa anında kapat (GREEN-10).
# Örnek: 10.0 → Zararda, yeşil mum gövdesi ≥ %10 → pozisyon kapatılır (SL beklenmez).
# Mantık: %10'luk güçlü yeşil mum = pump devam ediyor, SL'e kadar bekleme, çık.
# Canlıda: sadece KAPANMIŞ mumlar kontrol edilir, açık muma tepki verilmez.

# Not: Gövdesi <GREEN_LOSS_SINGLE_BODY_PCT olan zararda yeşil mumlarda
# art arda 2 yeşil mum oluşunca da otomatik kapatılır (2xGREEN-LOSS kuralı).


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 5 — RİSK YÖNETİMİ
#  Para yönetimi ve pozisyon boyutlandırma.
# ══════════════════════════════════════════════════════════════════════════

LEVERAGE = 3
# Kaldıraç çarpanı.
# Örnek: 5 → 100$ marjinle 500$'ın pozisyon açılır.
# UYARI: Kaldıraç arttıkça hem kâr hem zarar büyür.
# Önerilen aralık: 2x – 5x

MAX_ACTIVE_TRADES = 5
# Aynı anda açık olabilecek maksimum işlem sayısı.
# Örnek: 5 → Kasanın %20'si her işleme ayrılır (5 × %20 = %100).
# Bir işlem kapanınca slot açılır ve yeni işlem girilebilir.

# RISK_PER_TRADE_PCT — KALDIRILDI (yanıltıcıydı)
# Gerçek max kayıp otomatik hesaplanır:
#   pos_margin = kasa / MAX_ACTIVE_TRADES  (%20)
#   max_kayip  = %20 × LEVERAGE × SL_ABOVE_ENTRY_PCT / 100
# Örnek: 3x kaldıraç, %15 SL → %20 × 3 × %15 = kasanın %9'u per trade


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 6 — TARAMA ARALIKLARI (CANLI BOT)
#  Botun kaç saniyede bir kontrol yapacağı.
# ══════════════════════════════════════════════════════════════════════════

# SCAN_INTERVAL_SEC — KALDIRILDI
# Bot zaten her mum kapanışından 5dk önce tara yapıyor (PREP_SCAN_OFFSET_MIN).
# Ayrıca periyodik tarama gereksizdir: kapanış olmadan poz açılmaz.

PREP_SCAN_OFFSET_MIN = 5
# 4H mum kapanışından kaç dakika önce watchlist tarama başlatılsın.
# Örnek: 5 → 23:55, 03:55, 07:55 UTC'de tara; kapanışta (00:00) sadece watchlist kontrol edilir.
# Önerilen: 3–5 dakika. Çok kısa tutarsan tarama yetişmeyebilir.

MANAGER_INTERVAL_SEC = 5
# Açık pozisyonların SL/TSL güncellemesi için kontrol aralığı (saniye).
# Örnek: 5 → Her 5 saniyede bir açık pozisyonlar kontrol edilir.


# ══════════════════════════════════════════════════════════════════════════
#  BÖLÜM 7 — BACKTEST AYARLARI
# ══════════════════════════════════════════════════════════════════════════

BACKTEST_DAYS = 31
# Backtest kaç günlük veri kullansın (menüde tarih girmezsen bu değer kullanılır).
# Örnek: 31 → Son 31 günlük veri üzerinde test yapılır.

BACKTEST_INITIAL_CAPITAL = 1000.0
# Backtest başlangıç kasası (USDT).
# Örnek: 1000.0 → Backtest 1000 USDT ile başlar.

BACKTEST_SYMBOLS = [
    "TRB/USDT",
    "GAS/USDT",
    "CYBER/USDT",
    "LOOM/USDT",
    "YGG/USDT",
    "VANRY/USDT",
    "ORDI/USDT",
    "BIGTIME/USDT",
]
# Backtest'te test edilecek coin listesi.
# Menüde "1. Backtest Başlat" seçilince bu coinler kullanılır.
# "2. Full Universe Backtest" seçilirse Binance'deki tüm coinler taranır.
