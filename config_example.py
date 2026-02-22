"""
==============================================================================
PUMP & DUMP REVERSION BOT — CONFIG EXAMPLE
Tarih : 18 Şubat 2026
Geliştirici: Buğra Türkoğlu
==============================================================================

⚠️ ÖNEMLİ: Bu dosya sadece örnek amaçlıdır!
Gerçek kullanım için .env dosyasını kullanın.

.env.sample dosyasını .env olarak kopyalayın ve API anahtarlarınızı girin:
    copy .env.sample .env  (Windows)
    cp .env.sample .env    (Linux/Mac)
==============================================================================
"""

# ==========================================
# 🔑 BINANCE API KEYS
# ==========================================
# Demo Trading için: https://testnet.binancefuture.com
# Canlı Trading için: https://www.binance.com/en/my/settings/api-management
BINANCE_API_KEY = "your_api_key_here"
BINANCE_API_SECRET = "your_api_secret_here"

# ==========================================
# 📊 STRATEJI PARAMETRELERİ
# ==========================================
# Tüm strateji parametreleri 18.02.2026.py → Config sınıfında tanımlıdır
# Parametreleri değiştirmek için 18.02.2026.py dosyasını düzenleyin veya
# src/bot/config.py'yi kullanın

# Örnek parametreler (referans için):
# - LEVERAGE = 3
# - MAX_ACTIVE_TRADES = 5
# - PUMP_MIN_PCT = 30.0  (günlük min %30 artış)
# - SL_ABOVE_ENTRY_PCT = 15.0  (SL: entry × 1.15)
# - TIMEFRAME = "4h"

# ==========================================
# 🛡️ GÜVENLİK UYARISI
# ==========================================
# ❌ config.py veya .env dosyalarını asla GitHub'a yüklemeyin!
# ❌ API anahtarlarınızı kimseyle paylaşmayın!
# ✅ Binance API'de "Withdraw" iznini kapalı tutun!
# ✅ İlk testlerde DEMO_MODE=true kullanın!
# ✅ IP whitelist kullanın (sunucu IP'si)

