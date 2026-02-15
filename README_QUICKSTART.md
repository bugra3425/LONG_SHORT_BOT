# 🤖 Bugra Bot - Hızlı Başlatma Rehberi

## ⚡ Tek Tıkla Başlatma

### Scalping Bot (API key'siz):
```bash
# Windows
start_scalping.bat

# Komut satırı
python bugra_bot.py 1
```

### Apex Sniper Bot (API key gerekli):
```bash
# Windows  
start_apex.bat

# Komut satırı
python bugra_bot.py 2
```

## 🔧 İlk Kurulum (Sadece Bir Kez)

### 1. API Key Ayarı (Apex Sniper için)

**config_example.py'yi kopyala:**
```bash
copy config_example.py config.py
```

**config.py'yi düzenle:**
```python
BINANCE_API_KEY = "senin_api_key_buraya"
BINANCE_API_SECRET = "senin_api_secret_buraya"
```

✅ **Artık her seferinde API key girmeye gerek yok!**

### 2. Binance API Gereksinimleri

Binance'de API oluştururken:
- ✅ **Enable Futures** (ZORUNLU!)
- ✅ Enable Reading
- ✅ Enable Spot & Margin Trading
- ❌ Withdraw kapalı (güvenlik için)

📖 Detaylı kurulum: [APEX_SETUP_GUIDE.md](APEX_SETUP_GUIDE.md)

## 🎮 Kullanım Örnekleri

### Menü ile Seçim
```bash
python bugra_bot.py
# Sonra 1 veya 2 seç
```

### Direkt Başlatma
```bash
# Scalping Bot
python bugra_bot.py 1

# Apex Sniper Bot  
python bugra_bot.py 2
```

### Windows'ta Çift Tıkla
- **start_scalping.bat** → Scalping bot'u başlat
- **start_apex.bat** → Apex sniper bot'u başlat

## 📊 Bot Karşılaştırması

| Özellik | Scalping Bot | Apex Sniper Bot |
|---------|--------------|-----------------|
| Timeframe | 1 dakika | 4 saat |
| Tarama Sıklığı | 10 saniye | 10 dakika |
| Strateji | Momentum | Teknik Analiz |
| API Key | ❌ Gerekmez | ✅ Gerekli |
| Pozisyon Sayısı | Sınırsız | Max 4 |
| Koruma | - | BTC Shield |
| Hedef | Hızlı hareket | Üst banddan SHORT |

## 🛡️ Güvenlik

- ✅ config.py otomatik olarak .gitignore'da
- ✅ API key'ler asla paylaşılmaz
- ✅ Withdraw izni kapalı tutun
- ✅ Test için canlı işlem yapılmaz (sadece sinyal)

## 🐛 Sorun Giderme

### "Invalid API Key" hatası:
```bash
# config.py'yi kontrol et
notepad config.py

# API key'lerde boşluk olmamalı
# "Enable Futures" aktif olmalı Binance'de
```

### Bot açılmıyor:
```bash
# Gerekli paketleri yükle
pip install ccxt pandas pandas-ta

# Python versiyonu kontrol et
python --version  # 3.8+ olmalı
```

## 💡 İpuçları

1. **İlk Defa Kullanıyorsanız:**
   - Önce Scalping Bot'u deneyin (API key'siz)
   - Sinyalleri gözlemleyin
   - Sonra Apex için API key ekleyin

2. **Her Açılışta API Key Girmeyin:**
   - config.py dosyasını bir kez oluşturun
   - Artık otomatik yüklenecek

3. **Hızlı Başlatma:**
   - .bat dosyalarını masaüstüne kısayol ekleyin
   - Veya komut satırı argümanlarını kullanın

## 📚 Ek Kaynaklar

- [APEX_SETUP_GUIDE.md](APEX_SETUP_GUIDE.md) - Detaylı API kurulumu
- [config_example.py](config_example.py) - Yapılandırma şablonu
- [CHANGELOG.md](CHANGELOG.md) - Değişiklikler

---

**Son Güncelleme:** 15 Şubat 2026
