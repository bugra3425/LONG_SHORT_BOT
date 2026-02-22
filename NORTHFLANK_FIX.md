# 🔧 Northflank Container Otomatik Başlatma - Düzeltme

**Sorun:** Container başlatıldığında interaktif menü gösteriyordu ve input beklemeden timeout oluyordu.

**Çözüm:** `AUTO_LIVE=true` environment variable ile otomatik canlı moda geçiş.

---

## ✅ Yapılan Değişiklikler

### 1. 18.02.2026.py - Otomatik Mod Desteği
```python
def main():
    # Container için AUTO_LIVE kontrolü
    import os
    auto_live = os.getenv("AUTO_LIVE", "false").lower() == "true"
    
    if auto_live:
        # Interaktif menüyü atla, direkt canlı bot başlat
        asyncio.run(main_live())
        return
    
    # Normal interaktif menü (local development)
    ...
```

### 2. Dockerfile - ENV AUTO_LIVE=true
```dockerfile
# Container ortamı için otomatik canlı mod
ENV AUTO_LIVE=true
```

### 3. .env.sample - Dokümantasyon
```bash
AUTO_LIVE=false  # true = Otomatik canlı mod | false = Interaktif menü
```

---

## 🚀 Northflank'te Kullanım

### Environment Variables (Gerekli)
Northflank → Service → Environment Variables:

```bash
BINANCE_API_KEY=your_actual_api_key
BINANCE_API_SECRET=your_actual_api_secret
DEMO_MODE=true                    # İlk teste demo ile başla
AUTO_LIVE=true                    # Otomatik canlı mod (interaktif menü atla)
```

### Opsiyonel Variables
```bash
TELEGRAM_BOT_TOKEN=your_bot_token      # Bildirimler için
TELEGRAM_CHAT_ID=your_chat_id
REDIS_URL=redis://localhost:6379/0     # Replay cache için (gerekli değil)
```

---

## 📋 Deployment Adımları

### 1. Kodu Push Et
```bash
git add 18.02.2026.py Dockerfile .env.sample
git commit -m "fix: Northflank container otomatik başlatma desteği eklendi"
git push origin main
```

### 2. Northflank'te Yeniden Deploy
- Northflank → Services → `bot-worker`
- **Redeploy** butonuna tıkla (veya otomatik deploy aktifse bekle)

### 3. Logları Kontrol Et
Başarılı başlatma logları:
```
========================================================
   PUMP & DUMP REVERSION BOT — Binance Futures
========================================================

  🚀 AUTO_LIVE MODE: DEMO 🧪

========================================================

Container ortamı tespit edildi, otomatik canlı moda geçiliyor...
🌐 Binance Futures bağlantısı kuruluyor...
✅ 547 adet USDT-M futures çifti bulundu
⏰ 4H mum taraması başlatılıyor...
```

### 4. Demo'dan Canlıya Geçiş (Dikkatli!)
Test başarılı olduktan sonra:
```bash
DEMO_MODE=false  # ⚠️ GERÇEK PARA KULLANIR!
AUTO_LIVE=true
```

---

## 🔍 Sorun Giderme

### Container sürekli restart oluyor
- **Sebep:** API keys yanlış veya eksik
- **Çözüm:** Northflank environment variables kontrol et

### "Process terminated" hatası
- **Sebep:** AUTO_LIVE=false (interaktif menü açık)
- **Çözüm:** Northflank'te `AUTO_LIVE=true` olarak set et

### Loglar görünmüyor
- **Sebep:** PYTHONUNBUFFERED eksik
- **Çözüm:** Dockerfile'da zaten var, redeploy yap

---

## ✅ Test Checklist

- [ ] `AUTO_LIVE=true` set edildi (Northflank)
- [ ] `DEMO_MODE=true` aktif (ilk test)
- [ ] API keys doğru girildi
- [ ] Container başarıyla çalışıyor (Logs → Running)
- [ ] "AUTO_LIVE MODE" mesajı görünüyor
- [ ] 4H mum taraması başladı
- [ ] Sinyaller üretiyor (pump tespit edilirse)

---

**Artık container otomatik olarak canlı moda geçecek! 🎉**
