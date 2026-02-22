# 🚀 NORTHFLANK DEPLOYMENT GUIDE

## Pump & Dump Reversion Bot - Northflank Canlı Deployment

### 📋 Ön Hazırlık

#### 1. GitHub Repository
```bash
# Proje klasöründe git init (eğer yoksa)
git init
git add .
git commit -m "Initial commit - Pump & Dump Reversion Bot"

# GitHub'a push
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

#### 2. Binance API Keys Hazırla

**Demo Trading (Önerilen - Test için):**
- https://testnet.binancefuture.com adresine git
- API Key oluştur (Read + Trade izinleri)
- Keys'i kaydet

**Canlı Trading (Dikkatli!):**
- https://www.binance.com/en/my/settings/api-management
- API Key oluştur
- ✅ Enable Futures
- ✅ Enable Reading
- ❌ Withdraw KAPALI (güvenlik)
- IP Whitelist ekle (Northflank IP'leri)

---

## 🌐 Northflank Setup

### Adım 1: Proje Oluştur

1. Northflank'a giriş yap
2. **New Project** → Proje adı: `pump-dump-bot`
3. Region seç (Europe - Frankfurt önerilen)

### Adım 2: Service Oluştur

1. **Add Service** → **Combined Service**
2. **Repository** bölümünde:
   - GitHub repository'nizi seçin
   - Branch: `main`
   - Build context: `/` (root)

3. **Build Settings**:
   - Build Engine: **Dockerfile**
   - Dockerfile path: `Dockerfile`
   - Auto-build: ✅ Aktif (her commit'te build)

### Adım 3: Environment Variables

**Secrets** bölümünde ekle:

```env
# Binance API (DEMO - Test için)
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here

# Demo Mode (true = demo.binance.com, false = canlı)
DEMO_MODE=true

# Telegram (Opsiyonel)
TELEGRAM_BOT_TOKEN=your_bot_token  # Bildirimler için
TELEGRAM_CHAT_ID=your_chat_id

# Timezone
TZ=UTC
```

⚠️ **ÖNEMLİ:** İlk testlerde **DEMO_MODE=true** kullanın!

### Adım 4: Resources

**Resource Limits:**
- CPU: 0.5 - 1.0 vCPU (yeterli)
- Memory: 512 MB - 1 GB
- Disk: 1 GB (loglar için)

**Scaling:**
- Min Instances: 1
- Max Instances: 1 (bot tek instance çalışmalı)

### Adım 5: Runtime Settings

**Command Override** (isteğe bağlı):
```bash
python -u 18.02.2026.py
```

**Port Mapping:**
- Port mapping gerekmez (bot standalone çalışır)
- Healthcheck: Dockerfile'da tanımlı

### Adım 6: Deploy

1. **Deploy** butonuna tıkla
2. Build loglarını izle (3-5 dakika)
3. Deploy tamamlandığında **Logs** sekmesinden çıktıları kontrol et

---

## 📊 Bot Çalıştırma Modu

18.02.2026.py'de 4 mod var:

1. **Backtest (TÜM coinler)** - Manuel çalıştırma gerektirir
2. **Backtest (8 coin)** - Manuel çalıştırma
3. **Pump Tarama** - Manuel çalıştırma
4. **Canlı Bot** - Otomatik çalışır ✅

### Northflank'da Otomatik Canlı Mod

Northflank'da bot her başlatıldığında **menü gösterir**. Otomatik canlı modu için:

#### Seçenek A: Kod Değişikliği (Önerilen)

`18.02.2026.py` dosyasının en altında `main()` fonksiyonunu değiştir:

```python
def main():
    # Northflank için otomatik canlı mod
    import os
    if os.getenv("AUTO_LIVE_MODE") == "true":
        print("🚀 Otomatik canlı mod başlatılıyor...")
        asyncio.run(main_live())
        return
    
    # Normal menü (local development)
    print()
    print("=" * 56)
    # ... mevcut menü kodu ...
```

Sonra Northflank'da environment variable ekle:
```env
AUTO_LIVE_MODE=true
```

#### Seçenek B: Command Override

Northflank'da **Runtime → Command** bölümüne:
```bash
python -c "import asyncio; from main_strategy import main_live; asyncio.run(main_live())"
```

---

## 🔍 Monitoring & Logs

### Log İzleme

Northflank'da:
1. **Logs** sekmesi → Real-time logs
2. Bot çıktılarını canlı izle:
   - Pump detection
   - Trade signals
   - Position management

### Kritik Loglar

```
✅ İyi Sinyaller:
- "🔑 API anahtarları yüklendi"
- "📡 Universe: X USDT-M futures çifti bulundu"
- "🚨 TOP GAINER: SYMBOL | +XX%"
- "📉 SHORT açıldı: SYMBOL"

❌ Hata Sinyalleri:
- "Invalid API Key"
- "Network error"
- "Rate limit exceeded"
```

### Alerts (Opsiyonel)

Northflank'da **Alerts** sekmesinden:
- CPU > 80% → Slack/Discord bildirim
- Memory > 80% → Bildirim
- Service restart → Bildirim

---

## 🛡️ Güvenlik Kontrol Listesi

### Deployment Öncesi

- [ ] `.env` dosyası GitHub'a **PUSH EDİLMEDİ**
- [ ] `config.py` dosyası GitHub'a **PUSH EDİLMEDİ**
- [ ] `.gitignore` düzgün çalışıyor
- [ ] Binance API'de **Withdraw izni KAPALI**
- [ ] İlk test **DEMO_MODE=true**
- [ ] IP Whitelist aktif (opsiyonel)

### Deployment Sonrası

- [ ] Logs düzgün akıyor
- [ ] Bot API'ye bağlanabiliyor
- [ ] Demo işlemler görünüyor (testnet.binancefuture.com)
- [ ] Hata/exception yok
- [ ] Resource kullanımı normal (CPU < 50%, RAM < 80%)

---

## 🎯 Canlıya Geçiş

### DEMO → CANLI Geçiş

1. **Son testler tamam mı?**
   - En az 1 hafta demo'da test edildi
   - Backtest karlı
   - Hatalar giderildi

2. **Binance Canlı API Oluştur**
   - https://www.binance.com/en/my/settings/api-management
   - Enable Futures ✅
   - Withdraw KAPALI ❌
   - IP Whitelist ekle

3. **Northflank'da Secrets Güncelle**
   - `BINANCE_API_KEY` → Canlı key
   - `BINANCE_API_SECRET` → Canlı secret
   - `DEMO_MODE` → **false**

4. **Redeploy**
   - Service'i yeniden başlat
   - İlk 24 saat yakından izle

5. **Monitoring**
   - Her gün logları kontrol et
   - P&L takibi
   - Binance'de manuel kontrol

---

## 🐛 Troubleshooting

### "Invalid API Key" hatası
```bash
# Environment variables'ı kontrol et
# Northflank → Service → Secrets → API keys doğru mu?
# Binance'de API aktif mi?
```

### "Network timeout" hataları
```bash
# Normal - retry mekanizması var
# Sık oluyorsa Northflank region değiştir
```

### Bot sürekli restart oluyor
```bash
# Logs'u incele - hangi exception?
# Memory limit yeterli mi? (min 512MB)
# Python dependency eksik mi?
```

### Pump'lar tespit edilmiyor
```bash
# Universe çekiliyor mu? (log kontrol)
# PUMP_MIN_PCT çok yüksek olabilir (Config'de %30)
# Market sakin olabilir (normal)
```

---

## 📞 Destek

- GitHub Issues: Teknik sorunlar için
- Binance Support: API key sorunları için
- Northflank Docs: https://northflank.com/docs

---

## ✅ Quick Checklist

Deployment öncesi son kontrol:

```bash
# 1. Git temiz mi?
git status

# 2. Secrets GitHub'da mı? (OLMAMALI!)
git log --all --full-history -- .env
git log --all --full-history -- config.py

# 3. Dockerfile build test (local)
docker build -t pump-bot-test .

# 4. .gitignore çalışıyor mu?
cat .gitignore

# 5. README güncel mi?
cat README_QUICKSTART.md
```

Hepsi tamam → **GitHub Push** → **Northflank Deploy** 🚀
