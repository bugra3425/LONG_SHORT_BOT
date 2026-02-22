# 🚀 PUMP & DUMP REVERSION BOT

**Binance Futures USDT-M | 4H Timeframe | SHORT Only Strategy**

## 📋 Strateji Özeti

- **Timeframe**: 4 Saat (4H)
- **Tip**: Pump & Dump Reversion (Mean Reversion)
- **Yön**: SHORT only
- **Hedef**: Low/mid-cap altcoin pump sonrası dağıtım tespiti
- **Kaldıraç**: 3x (sabit)
- **SL**: Entry × 1.15 (%15 üst)
- **TP**: Trailing Stop (%7+ düşüşte aktif)

## 🎯 Teknik Detaylar

### Module 1: RADAR
- Top 10 günlük gainer izleme (%30+ artış)
- Major-cap hariç (BTC, ETH, BNB, SOL...)
- 6 adet 4H mum penceresi (24 saat)

### Module 2: TRIGGER
- Pump sonrası ilk kırmızı 4H mum
- Solid reversal tespiti (min %4 gövde)
- Zirve onayı kontrolü

### Module 3: RISK MANAGEMENT
- 3x kaldıraç (equity < 200$ → 4x)
- Max 5 eş zamanlı işlem
- SL: Entry × 1.15
- BE: %7 düşüşte breakeven
- TSL: %7+ düşüşte trailing aktif

## 🛠️ Kurulum

### 1. Gereksinimler

```bash
Python 3.12+
Git
```

### 2. Repository Clone

```bash
git clone https://github.com/YOUR_USERNAME/pump-dump-bot.git
cd pump-dump-bot
```

### 3. Bağımlılıklar

```bash
pip install -r requirements.txt
```

### 4. Environment Ayarları

```bash
# .env.sample'ı kopyala
copy .env.sample .env  # Windows
cp .env.sample .env    # Linux/Mac

# .env dosyasını düzenle
# API keys ekle (demo veya canlı)
```

## 🎮 Kullanım

### Doğrudan Ana Dosyayı Çalıştır

```bash
python 18.02.2026.py
```

Menü seçenekleri:
1. Backtest (TÜM Binance coinleri)
2. Backtest (8 popüler coin - hızlı)
3. Pump Tarama (sadece watchlist)
4. Canlı Bot (Demo/Canlı)

### Alternatif: run.py

```bash
python run.py
```

## 🐳 Docker Kullanımı

### Local Test

```bash
# Build
docker build -t pump-bot .

# Run (interactive)
docker run -it --env-file .env pump-bot
```

### Docker Compose

```bash
docker-compose up
```

## ☁️ Northflank Deployment

Detaylı talimatlar için: **[NORTHFLANK_DEPLOYMENT.md](NORTHFLANK_DEPLOYMENT.md)**

### Hızlı Adımlar

1. **GitHub'a Push**
   ```bash
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

2. **Northflank'da Proje Oluştur**
   - Repository bağla
   - Dockerfile build seç
   - Environment variables ekle

3. **Environment Variables**
   ```
   BINANCE_API_KEY=your_key
   BINANCE_API_SECRET=your_secret
   DEMO_MODE=true
   AUTO_LIVE_MODE=true
   ```

4. **Deploy**
   - Build & Deploy başlat
   - Logs'u izle

## 🔒 Güvenlik

### API Key Ayarları (Binance)

✅ Enable Futures
✅ Enable Reading
❌ Withdraw KAPALI (önemli!)
✅ IP Whitelist (sunucu IP'si)

### Önemli Notlar

- `.env` ve `config.py` dosyaları **ASLA** GitHub'a push edilmez
- İlk testlerde **DEMO_MODE=true** kullanın
- Canlıya geçmeden önce en az 1 hafta demo test yapın
- Binance API'de Withdraw iznini kapatın

## 📊 Backtest Kullanımı

### Hızlı Backtest (8 coin)

```bash
python 18.02.2026.py
# Seçenek: 2
```

### Tam Universe Backtest

```bash
python 18.02.2026.py
# Seçenek: 1
# Sermaye ve tarih aralığı belirle
```

### Sonuçlar

- Terminal raporu
- Trade detayları
- Equity curve
- Win rate & Sharpe ratio

## 📁 Proje Yapısı

```
pump-dump-bot/
├── 18.02.2026.py              ⭐ ANA DOSYA (tüm strateji)
├── run.py                     Alternatif giriş
├── Dockerfile                 Production image
├── docker-compose.yml         Local development
├── requirements.txt           Python dependencies
├── .env.sample                API keys şablonu
├── NORTHFLANK_DEPLOYMENT.md   Deployment rehberi
│
└── src/bot/
    ├── config.py              Config wrapper
    ├── exchange.py            Async Binance client
    ├── strategy.py            Strategy wrapper
    ├── main.py                Entry point
    └── binance_replay.py      Replay mode
```

## 🧪 Test Modu

### Demo Trading

```env
DEMO_MODE=true
BINANCE_API_KEY=demo_key  # testnet.binancefuture.com
BINANCE_API_SECRET=demo_secret
```

Demo API: https://testnet.binancefuture.com

### Pump Tarama (İşlem Yok)

```bash
python 18.02.2026.py
# Seçenek: 3
```

Sadece watchlist gösterir, işlem açmaz.

## 📈 Performans

### Backtest Sonuçları (Örnek)

- Period: 31 gün
- Initial Capital: 1000 USDT
- Total Trades: 15-25
- Win Rate: %60-70
- Avg ROI/Trade: %8-12
- Sharpe Ratio: 1.5+

⚠️ Geçmiş performans gelecek garantisi değildir!

## 🔧 Konfigürasyon

Ana parametreler `18.02.2026.py` → `Config` sınıfında:

```python
LEVERAGE = 3
MAX_ACTIVE_TRADES = 5
PUMP_MIN_PCT = 30.0
SL_ABOVE_ENTRY_PCT = 15.0
TIMEFRAME = "4h"
TOP_N_GAINERS = 10
```

## 🐛 Sorun Giderme

### "Invalid API Key" hatası

```bash
# .env dosyasını kontrol et
# API key'lerde boşluk olmamalı
# Binance'de "Enable Futures" aktif mi?
```

### Bot çalışmıyor

```bash
# Logs kontrol et
# Python version: 3.12+
# Dependencies yüklü mü?
python --version
pip install -r requirements.txt
```

### Pump tespit edilmiyor

```bash
# Normal - market sakin olabilir
# PUMP_MIN_PCT çok yüksek olabilir (%30)
# Universe çekiliyor mu? (logs kontrol)
```

## 📞 Destek & Katkı

- **Issues**: GitHub Issues kullanın
- **PRs**: Katkılar hoş geldinir
- **Docs**: Detaylı bilgi için NORTHFLANK_DEPLOYMENT.md

## ⚖️ Lisans & Disclaimer

⚠️ **UYARI**: Bu bot eğitim/araştırma amaçlıdır.
- Finansal tavsiye değildir
- Kullanım tamamen kendi sorumluluğunuzdadır
- Geçmiş performans gelecek garantisi değildir
- Kripto para yatırımları risklidir

## 🔗 Faydalı Linkler

- [Binance Futures API](https://binance-docs.github.io/apidocs/futures/en/)
- [Northflank Docs](https://northflank.com/docs)
- [CCXT Documentation](https://docs.ccxt.com/)

---

**Geliştirici**: Buğra Türkoğlu  
**Tarih**: 18 Şubat 2026  
**Versiyon**: 3.0 (Refined Scalper)

🚀 Happy Trading! (Demo'da test edin!)
