"""
Veri Çekme Scripti
Dosya: veri_cek.py
Tarih: 12 Şubat 2026
Açıklama: ccxt kütüphanesi ile borsadan geçmiş OHLCV (mum) verilerini çeker
          ve CSV dosyaları olarak backtest_data klasörüne kaydeder.
"""
import ccxt
import pandas as pd
import os
import time
from datetime import datetime, timedelta

# ==========================================
# ⚙️ AYARLAR
# ==========================================
DATA_FOLDER = "backtest_data"
DAYS_TO_FETCH = 60          # 2 ay
START_RANK = 1              # İlk 100
END_RANK = 100
TIMEFRAME = '15m'

# ==========================================
# 🔌 BORSA BAĞLANTISI (BYBIT)
# ==========================================
exchange = ccxt.bybit({
    'enableRateLimit': True, 
    'timeout': 60000,
    'options': {'defaultType': 'linear'}
})

def get_sorted_coins():
    """Hacme göre sıralı coinleri al"""
    try:
        markets = exchange.load_markets()
        tickers = exchange.fetch_tickers()
        
        futures = []
        for symbol, ticker in tickers.items():
            # Bybit linear format: BTC/USDT:USDT
            if '/USDT:USDT' in symbol and ticker.get('quoteVolume'):
                futures.append({
                    'symbol': symbol, 
                    'volume': float(ticker.get('quoteVolume', 0))
                })
        
        futures.sort(key=lambda x: x['volume'], reverse=True)
        return futures[START_RANK-1:END_RANK]
    except Exception as e:
        print(f"❌ Coin listesi alınamadı: {e}")
        return []

def fetch_ohlcv_with_retry(symbol, tf, since, limit, retries=3):
    """Retry mekanizmalı veri çekme - Pagination ile 2 aylık veri"""
    all_data = []
    current_since = since
    
    # 15m = 60 gün için ~5760 mum lazım, API 1000 limit
    # 6 iterasyon yapacağız
    iterations = (limit // 1000) + 1
    
    for i in range(iterations):
        for attempt in range(retries):
            try:
                data = exchange.fetch_ohlcv(symbol, tf, since=current_since, limit=1000)
                if data:
                    all_data.extend(data)
                    # Sonraki batch için timestamp güncelle
                    current_since = data[-1][0] + 1
                    time.sleep(0.2)
                break
            except Exception as e:
                if attempt < retries - 1:
                    print(f"   ⚠️ Retry {attempt+1}/{retries}...")
                    time.sleep(2)
                else:
                    return all_data if all_data else None
        
        if not data or len(data) < 100:
            break
    
    return all_data if all_data else None

def fetch_and_save_data():
    """15 günlük veriyi çekip CSV'ye kaydet"""
    print("=" * 70)
    print("📥 VERİ ÇEKME VE KAYDETME")
    print("=" * 70)
    print(f"📅 Son {DAYS_TO_FETCH} günlük veri çekilecek")
    print(f"🎯 Coin aralığı: {START_RANK}-{END_RANK}")
    print(f"⏱️ Timeframe: {TIMEFRAME}")
    print("=" * 70)
    
    # Klasör oluştur
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
        print(f"📁 Klasör oluşturuldu: {DATA_FOLDER}")
    
    # Coinleri al
    print("\n📋 Coin listesi alınıyor...")
    coins = get_sorted_coins()
    
    if not coins:
        print("❌ Coin listesi alınamadı!")
        return
    
    print(f"✅ {len(coins)} coin bulundu\n")
    
    # Belirli tarih aralığı: 2026-01-12 - 2026-01-21
    start_date = datetime(2026, 1, 12)
    end_date = datetime(2026, 1, 21, 23, 59)
    since = int(start_date.timestamp() * 1000)
    # 15dk periyot, 15 gün = 15*24*4 = 1440 mum
    limit = int((end_date - start_date).total_seconds() // (15*60))
    
    saved_count = 0
    coin_list = []
    
    for i, coin in enumerate(coins, 1):
        symbol = coin['symbol']
        safe_symbol = symbol.replace('/', '_').replace(':', '_')
        
        print(f"[{i}/{len(coins)}] {symbol} çekiliyor...", end=" ")
        
        data = fetch_ohlcv_with_retry(symbol, TIMEFRAME, since, limit)
        
        if data and len(data) > 100:
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['symbol'] = symbol
            
            # CSV'ye kaydet
            filename = f"{DATA_FOLDER}/{safe_symbol}.csv"
            df.to_csv(filename, index=False)
            
            print(f"✅ {len(df)} mum kaydedildi")
            saved_count += 1
            coin_list.append({'symbol': symbol, 'file': filename, 'candles': len(df)})
        else:
            print("❌ Veri alınamadı")
        
        time.sleep(0.3)  # Rate limit için bekle
    
    # Coin listesini de kaydet
    coin_df = pd.DataFrame(coin_list)
    coin_df.to_csv(f"{DATA_FOLDER}/_coin_list.csv", index=False)
    
    print("\n" + "=" * 70)
    print("✅ VERİ ÇEKME TAMAMLANDI")
    print("=" * 70)
    print(f"📊 Toplam: {saved_count}/{len(coins)} coin kaydedildi")
    print(f"📁 Konum: {DATA_FOLDER}/")
    print(f"📅 Tarih aralığı: {start_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")
    print("=" * 70)

if __name__ == "__main__":
    fetch_and_save_data()
