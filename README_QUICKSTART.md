# 🚀 PUMP & DUMP REVERSION BOT — Hızlı Başlatma

## 📖 Genel Bakış

**Strateji:** Agresif pump yapan low/mid-cap altcoinlerde dağıtım (distribution) onayı ile SHORT giriş  
**Timeframe:** 4 Saat (4H)  
**Exchange:** Binance Futures (USDT-M)  
**Versiyon:** 18.02.2026  
**Geliştirici:** Buğra Türkoğlu  

### 🎯 Strateji Özeti (v3 — Refined Scalper)

1. **Module 1:** Top 10 Daily Gainer → Watchlist (günlük %30+ artış)
2. **Module 2:** 4H Kapanan Mum → SHORT (pump sonrası kırmızı mum)
3. **Module 3:** SL entry'nin %15 üstü, TP = entry×0.92 (sabit %8), Trailing Stop
4. **Module 4:** Çıkış yalnızca SL / BE / TSL ile
5. **Module 5:** 24 saat cooldown sonra yeniden giriş

---

## ⚡ Hızlı Başlatma

### 1️⃣ Kurulum

```bash
# 1. Repository'yi klonla
git clone https://github.com/bugra3425/LONG_SHORT_BOT.git
cd LONG_SHORT_BOT

# 2. Sanal ortam oluştur (önerilen)
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 3. Gereksinimleri yükle
pip install -r requirements.txt
```

### 2️⃣ API Anahtarları (.env Ayarı)

```bash
# .env.sample dosyasını kopyala
copy .env.sample .env  # Windows
# cp .env.sample .env  # Linux/Mac

# .env dosyasını düzenle ve API anahtarlarını ekle
notepad .env  # Windows
# nano .env  # Linux/Mac
```

**`.env` dosyası içeriği:**

```env
# 🔑 BINANCE API KEYS
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here

# 🧪 DEMO MODE (true = demo trading, false = CANLI!)
DEMO_MODE=true

# 📲 TELEGRAM (Opsiyonel)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

> ⚠️ **ÖNEMLİ:** İlk testlerde mutlaka `DEMO_MODE=true` kullanın!

### 3️⃣ Binance Demo API Keys Alma

1. **Demo Trading:** https://testnet.binancefuture.com
   - Email ile kayıt ol
   - API Management'tan API key oluştur
   - **Enable Futures** seçeneğini aktif et

2. **Canlı Trading (İleri Seviye):** https://www.binance.com/en/my/settings/api-management
   - ⚠️ Gerçek para kullanır! Dikkatli olun!

---

## 🎮 Kullanım

### Ana Dosya ile Çalıştırma (Önerilen)

```bash
# Doğrudan ana dosyayı çalıştır
python 18.02.2026.py
```

**Menü seçenekleri:**

```
1 — Backtest (Geçen ay, TÜM Binance coinleri)
2 — Backtest (Hızlı, sadece 8 popüler coin)
3 — Pump Tarama (Şu anda pump yapan coinleri göster)
4 — Canlı Bot (Gerçek / Demo işlem açar)
```

### Alternatif: run.py ile Çalıştırma

```bash
# src/bot/main.py üzerinden (18.02.2026.py'yi çağırır)
python run.py
```

---

## 📊 Backtest Nasıl Çalıştırılır?

### Seçenek 1: Tam Universe (Tüm Coinler)

```bash
python 18.02.2026.py

# Menüden 1 seç
# Sermaye: (örn. 1000) Enter
# Tarih aralığı: GG.AA.YYYY formatında veya Enter (son 31 gün)
```

### Seçenek 2: Hızlı Test (8 Popüler Coin)

```bash
python 18.02.2026.py

# Menüden 2 seç
# Daha hızlı sonuç almanız için önceden belirlenmiş coinler test edilir
```

**Örnek Backtest Çıktısı:**

```
╔══════════════════════════════════════════════════════════════════╗
║               BACKTEST RAPORU — Pump & Dump Reversion            ║
╠══════════════════════════════════════════════════════════════════╣
║  Sermaye: $1000 → $1450  |  ROI: +45.0%  |  31 gün              ║
║  İşlem: 12  |  Kazanan: 8 (66.7%)  |  Kaybeden: 4 (33.3%)       ║
║  Avg Win: +12.5%  |  Avg Loss: -8.2%  |  Max Drawdown: -5.3%    ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## 🤖 Canlı Bot Nasıl Çalıştırılır?

### ⚠️ DEMO MODE ile Testler (Önerilen)

```bash
# 1. .env dosyasında DEMO_MODE=true olduğundan emin ol
# 2. Ana dosyayı çalıştır
python 18.02.2026.py

# 3. Menüden 4 seç
# 4. Onay için "EVET" yaz
```

**Bot çalışırken:**

- Her 15 dakikada bir universe taraması yapar
- Top 10 günlük gainer coini watchlist'e alır
- 4H mum kapanışlarında SHORT sinyali kontrol eder
- Pozisyon açar, SL/TSL yönetir, otomatik çıkış yapar

### ⚠️ CANLI MODE (Gerçek Para - Dikkat!)

```bash
# 1. .env dosyasında DEMO_MODE=false yap
# 2. Binance'den CANLI API keys kullan
# 3. Küçük sermaye ile test et!
```

> 🛡️ **GÜVENLİK:** Canlı botun ilk çalıştırmasında mutlaka küçük sermaye kullanın!

---

## 🔍 Pump Tarama Modu

Gerçek zamanlı pump tespit etmek için:

```bash
python 18.02.2026.py

# Menüden 3 seç
# Bot tüm universe'ü tarar ve pump yapan coinleri gösterir
```

**Örnek Çıktı:**

```
🚨 TOP GAINER: LOOM/USDT:USDT  |  +42.3%  |  Zirve: 0.08450
🚨 TOP GAINER: CYBER/USDT:USDT  |  +38.7%  |  Zirve: 4.32100
🚨 TOP GAINER: VANRY/USDT:USDT  |  +35.2%  |  Zirve: 0.12340
```

---

## 📁 Proje Yapısı

```
LONG_SHORT_BOT/
│
├── 18.02.2026.py          # ⭐ ANA DOSYA - Strateji burada
├── run.py                 # Alternatif giriş noktası
├── .env                   # API anahtarları (GİZLİ - Git'e eklenmesin)
├── .env.sample            # .env şablonu
├── requirements.txt       # Python kütüphaneleri
├── README_QUICKSTART.md   # Bu dosya
│
└── src/
    └── bot/
        ├── config.py      # Config sınıfı (18.02.2026.py'den alınır)
        ├── exchange.py    # Async exchange client
        ├── strategy.py    # 18.02.2026.py'yi import eder
        └── main.py        # run.py tarafından çağrılır
```

---

## 🛡️ Güvenlik ve En İyi Uygulamalar

### ✅ Yapılması Gerekenler

- ✅ İlk testlerde **DEMO_MODE=true** kullanın
- ✅ `.env` dosyasını asla Git'e eklemeyin (`.gitignore`'da)
- ✅ Binance API'de **Withdraw izni kapalı** tutun
- ✅ Binance API'de **IP whitelist** kullanın (sunucu IP'si)
- ✅ Küçük sermaye ile başlayın

### ❌ Yapılmaması Gerekenler

- ❌ API Secret'ı asla paylaşmayın
- ❌ İlk testlerde büyük sermaye kullanmayın
- ❌ CANLI MODE'da bot'u gözetimsiz bırakmayın

---

## 🐛 Sorun Giderme

### "BINANCE_API_KEY bulunamadı" Hatası

```bash
# .env dosyasının proje kökünde olduğundan emin ol
ls -la .env  # Linux/Mac
dir .env     # Windows

# .env.sample'dan kopyalayın
copy .env.sample .env
```

### "Invalid API Key" Hatası

```bash
# 1. Binance API'de "Enable Futures" aktif mi kontrol et
# 2. Demo için testnet.binancefuture.com kullanıyor musunuz?
# 3. IP whitelist'e sunucu IP'si eklendi mi?
```

### "Network Error" Hatası

```bash
# DNS sorunu olabilir (Türkiye'de sık görülür)
# 18.02.2026.py DNS fix içerir (Google/Cloudflare DNS)
# VPN kullanmayı deneyin
```

### Bot Hiç İşlem Açmıyor

```bash
# 1. Watchlist boş mu? (pump tespit edilemiyor olabilir)
# 2. 4H mum kapanışını bekleyin (bot hemen giriş yapmaz)
# 3. Backtest ile stratejiyi önce test edin
```

---

## 📞 Destek

**GitHub:** https://github.com/bugra3425/LONG_SHORT_BOT  
**Versiyon:** 18.02.2026  
**Geliştirici:** Buğra Türkoğlu  

---

## 📄 Lisans & Sorumluluk Reddi

Bu bot eğitim amaçlıdır. Gerçek para ile kullanımında tüm sorumluluk kullanıcıya aittir.  
Finansal tavsiye niteliği taşımaz. Kendi riskinizi kendiniz yönetin.

⚠️ **Kripto para ticareti yüksek risk içerir. Kaybedebileceğinizden fazlasını yatırmayın!**
