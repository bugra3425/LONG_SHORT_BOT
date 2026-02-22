# 🚂 Railway.app Deployment Guide

**Neden Railway?** Northflank'ten farklı olarak coğrafi kısıtlama yapmıyor, Binance API'ye erişim sağlıyor.

---

## 🚀 Hızlı Başlangıç (5 Dakika)

### 1. Railway Hesabı Oluştur
1. https://railway.app/ adresine git
2. **Login with GitHub** (ücretsiz $5 credit)

### 2. Yeni Proje Oluştur
1. **New Project** → **Deploy from GitHub repo**
2. `bugra3425/LONG_SHORT_BOT` seç
3. **Deploy Now**

### 3. Environment Variables Ekle
Railway dashboard → **Variables** tab:

```bash
BINANCE_API_KEY=<your_api_key>
BINANCE_API_SECRET=<your_api_secret>
DEMO_MODE=true
AUTO_LIVE=true
```

### 4. Deploy Settings
Railway otomatik Dockerfile'ı tespit eder:
- ✅ **Build Command:** Docker build (otomatik)
- ✅ **Start Command:** `CMD` from Dockerfile (otomatik)
- ✅ **Port:** Gerekmez (bot sadece outbound bağlantı yapar)

### 5. Deploy!
**Deploy** butonuna tıkla → Railway otomatik build ve deploy eder.

---

## 📊 Logları İzle

Railway → **Deployments** → Son deployment → **View Logs**

Başarılı başlatma:
```
🚀 AUTO_LIVE MODE: DEMO 🧪
Container ortamı tespit edildi, otomatik canlı moda geçiliyor...
🌐 Binance Futures bağlantısı kuruluyor...
🧪 Demo Trading modu aktif
✅ 547 adet USDT-M futures çifti bulundu
⏰ 4H mum taraması başlatılıyor...
```

---

## 💰 Fiyatlandırma

- **Starter Plan:** $5 credit (ilk ay BEDAVA)
- **Developer Plan:** $5/ay (credit yenileme)
- **Kullanım:** ~$0.50-1/ay (küçük bot için yeterli)

---

## ⚙️ Avantajları

✅ **Coğrafi kısıtlama yok** - Binance API erişimi sorunsuz  
✅ **Otomatik GitHub sync** - Push yaptığında otomatik deploy  
✅ **Kolay environment variables** - UI'dan düzenle  
✅ **Ücretsiz başlangıç** - $5 credit  
✅ **Türkiye'den erişim** - DNS sorunu yok  

---

## 🔧 Sorun Giderme

### Build hatası alıyorsam?
- **Settings** → **Build Command** kontrol et
- Dockerfile doğru tanımlanmış mı?

### Loglar görünmüyorsa?
- **Deployments** → Son deployment → **View Logs**
- Container status: **Active** olmalı

### API hatası alıyorsam?
- **Variables** → API keys doğru mu?
- `DEMO_MODE=true` ekli mi?

---

## 📋 Alternatif: Render.com

Render de coğrafi kısıtlama yapmıyor:
1. https://render.com/ → Login with GitHub
2. **New** → **Web Service** → GitHub repo seç
3. **Docker** seç
4. Environment variables ekle
5. **Create Web Service**

Fark: Render "Web Service" olarak çalışır (free tier 15 dk sonra sleep, $7/ay always-on)

---

## ✅ Önerilen: Railway

Railway hem uygun fiyatlı hem de Binance erişimi için en iyi seçenek.

**Şimdi Railway'e geç ve Northflank'i durdur!**
