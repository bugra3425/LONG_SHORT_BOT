# 📋 CHANGELOG - Crypto Trading Bot

## [v1.1.0] - 2026-02-10

### 🚀 Yeni: Swing Bot (Çift Yönlü)

#### swing_bot.py - BTC Takipli Çift Yönlü Trading
- **BTC Trend Analizi**: Önce BTC yönü belirleniyor (BULLISH/BEARISH/NEUTRAL)
- **Çift Yönlü Sinyal**: Hem LONG hem SHORT sinyalleri
- **Dinamik Kaldıraç**: 5x-10x (sinyal gücüne göre)
- **Pozisyon Süresi**: 1-4 saat (daha stabil)
- **Multi-Timeframe**: 15m, 1h, 4h confluence

#### Strateji Parametreleri
```
Min Score: 60
Min Win Rate: 65%
BTC Aynı Yön Bonus: +20p
BTC Ters Yön Ceza: -15p

Kaldıraç:
  • Score≥90 + WR≥75%: 10x
  • Score≥80 + WR≥70%: 8x
  • Score≥70 + WR≥65%: 7x
  • Score≥60: 6x

Stop Loss: ATR × 2.0
TP1: 1:1.5 (30%)
TP2: 1:2.5 (30%)
TP3: 1:4.0 (40%)
```

#### LONG Sinyal Kriterleri
- Golden Cross (EMA9 > EMA21)
- RSI < 30 (aşırı satım)
- MACD Bullish Cross
- BB Alt Bant Bounce
- StochRSI < 20

#### SHORT Sinyal Kriterleri  
- Death Cross (EMA9 < EMA21)
- RSI > 80 (aşırı alım)
- MACD Bearish Cross
- BB Üst Bant Reddi
- StochRSI > 85

---

## [v1.0.0] - 2026-02-09

### 🚀 Yeni Özellikler

#### Trading Bot Sistemleri
- **short_bot.py** - SHORT sinyal trading botu oluşturuldu
  - 9 teknik indikatör entegrasyonu (ADX, DI+/DI-, EMA9/21, SMA50, RSI, MACD, BB, StochRSI, MFI, ATR)
  - Multi-timeframe analiz (15m, 1h, 4h)
  - Telegram bildirim sistemi
  
- **ultra_short_bot.py** - Geliştirilmiş ultra short bot
  - Daha agresif sinyal algılama
  - Hızlı giriş/çıkış stratejisi

- **oto_bot.py** - Otomatik trading bot altyapısı

- **scan_50_100.py** - Coin tarama scripti
  - Hacme göre 50-100 sıralı coinleri tarar
  - En iyi 3 SHORT sinyalini Telegram'a gönderir
  - 61/100 coin'de sinyal bulundu (LA %90, KITE %88, 42 %87)

#### Backtest Sistemleri
- **backtest_dun.py** - İlk backtest scripti
  - Başlangıç: -19% kayıp (sorunlu strateji)
  
- **backtest_csv.py** - Hızlı CSV tabanlı backtest (v3)
  - ⚡ ~0.5 saniyede backtest (vs dakikalar)
  - SINGLE_COIN filtresi ile tek coin test
  - SHOW_TRADE_DETAILS detaylı işlem logu
  - Tarih aralığı: 2026-01-25 - 2026-02-08

#### Veri Yönetimi
- **veri_cek.py** - OHLCV veri çekme scripti
  - 15 günlük 15m mum verisi
  - 51 coin için veri indirildi (rank 50-100)
  - CSV formatında kayıt
  - Bybit/OKX/Binance desteği (bağlantı sorunları nedeniyle)

- **backtest_data/** klasörü
  - 51 coin CSV dosyası
  - `_coin_list.csv` metadata dosyası

### 📈 Strateji Geliştirmeleri

#### v1 → v2 İyileştirmeler
| Sorun | Çözüm |
|-------|-------|
| Re-entry spam | 8 mum cooldown eklendi |
| Sıkı stop loss | ATR × 2.5 genişletildi |
| Kötü R:R oranı | Partial TP sistemi |

#### v3 Final Strateji Parametreleri
```
Score Threshold: ≥80
Win Rate Threshold: ≥75%
Cooldown: 8 mum
Max Trades/Coin: 20

Stop Loss: ATR × 2.5
TP1: 1:1.5 (30% pozisyon)
TP2: 1:2.5 (30% pozisyon)  
TP3: 1:4.0 (40% pozisyon)

Volatilite Filtresi: 0.5% < ATR% < 5%
Trailing Stop: TP1/TP2 sonrası aktif
```

### 📊 Backtest Sonuçları

#### Haftalık Test (1-8 Şubat 2026)
| Metrik | Değer |
|--------|-------|
| Toplam İşlem | 304 |
| Win Rate | 58.6% |
| Başlangıç | $1,000 |
| Final | $1,821 |
| **Kar** | **+$821 (+82%)** |

#### Tekil Coin Performansları
| Coin | İşlem | Win Rate | Kar | TP3 | Stop Loss |
|------|-------|----------|-----|-----|-----------|
| **DOT** | 21 | **81%** | **+$201** | 4 | 2 |
| AAVE | 16 | 75% | +$163 | 3 | 3 |
| HBAR | 15 | 60% | +$29 | 2 | 5 |

### 🔧 Teknik Detaylar

#### Kullanılan Kütüphaneler
- `ccxt` - Kripto borsa API
- `pandas` - Veri işleme
- `pandas_ta` - Teknik analiz
- `requests` - HTTP istekleri

#### Telegram Entegrasyonu
- Bot Token: `8063148867:AAH2UX__...`
- Chat ID: `6786568689`
- Sinyal ve backtest sonuçları gönderimi

#### İndikatör Listesi (9 adet)
1. ADX + DI+/DI- (trend gücü)
2. EMA 9 (hızlı trend)
3. EMA 21 (orta trend)
4. SMA 50 (yavaş trend)
5. RSI (momentum)
6. MACD (trend değişimi)
7. Bollinger Bands (volatilite)
8. Stochastic RSI (aşırı alım/satım)
9. MFI (para akışı)

### 🐛 Çözülen Sorunlar
- Binance API bağlantı sorunları (SSL reset)
- Re-entry spam problemi (cooldown ile çözüldü)
- Düşük win rate (-19% → +82% karlılık)
- Yavaş backtest (dakikalar → 0.5 saniye)

### 📁 Proje Yapısı
```
murat/
├── backtest_bot.py      # Eski backtest
├── backtest_csv.py      # Hızlı CSV backtest ⭐
├── backtest_dun.py      # Günlük backtest
├── eth_analiz.py        # ETH analiz
├── oto_bot.py           # Otomatik bot
├── sample_.py           # Örnek kod
├── scan_50_100.py       # Coin tarayıcı
├── short_bot.py         # SHORT bot
├── temp_bnb.py          # BNB test
├── ultra_short_bot.py   # Ultra short bot
├── veri_cek.py          # Veri çekici
├── CHANGELOG.md         # Bu dosya
└── backtest_data/       # 51 coin CSV verisi
    ├── _coin_list.csv
    ├── DOT_USDT_USDT.csv
    ├── AAVE_USDT_USDT.csv
    └── ... (48 diğer coin)
```

### 🔗 Repository
- GitHub: https://github.com/Golabstech/bugra-bot
- Push tarihi: 2026-02-09
- 64 dosya, 76,209 satır kod

---

## Sonraki Adımlar (Planlar)
- [ ] İlk 100 coin için 1 aylık veri çekimi (API sorunları çözülmeli)
- [ ] LONG sinyal stratejisi ekleme
- [ ] Canlı trading modu
- [ ] Web dashboard

---
*Son güncelleme: 2026-02-09*
