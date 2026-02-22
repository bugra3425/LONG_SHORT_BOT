import ccxt
import pandas as pd
import os
import time
from datetime import datetime, timedelta

# ==========================================
# ⚙️ AYARLAR
# ==========================================
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_FOLDER = os.path.join(_PROJECT_ROOT, "data", "backtest_data")
DAYS_TO_FETCH = 240         # 8 ay (Geriye dönük)
START_RANK = 1              
END_RANK = 100
TIMEFRAME = '15m'
EXISTING_DATA_DAYS = 90     # Zaten var olan 3 aylık veri
MAX_WORKERS = 10            # Paralel işlem sayısı (API limitine dikkat)

# ==========================================
# 🔌 BORSA BAĞLANTISI (BYBIT)
# ==========================================
def get_sorted_coins():
    """Hacme göre sıralı coinleri al"""
    try:
        # Ana thread için tek instance
        exchange = ccxt.bybit({'enableRateLimit': True, 'options': {'defaultType': 'linear'}})
        markers = exchange.load_markets()
        tickers = exchange.fetch_tickers()
        
        futures = []
        for symbol, ticker in tickers.items():
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

def process_coin_fetch(coin_data):
    """Tek bir coin için veri çekme işlemi (Worker)"""
    symbol = coin_data['symbol']
    safe_symbol = symbol.replace('/', '_').replace(':', '_')
    filename = f"{DATA_FOLDER}/{safe_symbol}.csv"
    
    # Her thread kendi exchange instance'ını kullansın (Thread-safe)
    local_exchange = ccxt.bybit({
        'enableRateLimit': True,
        'rateLimit': 100, # Agresif limit
        'timeout': 30000,
        'options': {'defaultType': 'linear'}
    })
    
    try:
        existing_df = None
        earliest_timestamp = None
        
        # Mevcut dosyayı kontrol et
        if os.path.exists(filename):
            try:
                existing_df = pd.read_csv(filename)
                existing_df['timestamp'] = pd.to_datetime(existing_df['timestamp'])
                earliest_timestamp = existing_df['timestamp'].min()
                
                if earliest_timestamp < datetime.utcnow() - timedelta(days=200):
                    return {'symbol': symbol, 'file': filename, 'status': 'SKIPPED', 'msg': 'Yeterli veri var'}
            except Exception:
                pass
        
        # Tarih belirle
        if earliest_timestamp:
            fetch_end_ts = int(earliest_timestamp.timestamp() * 1000)
            days_needed = DAYS_TO_FETCH - (datetime.utcnow() - earliest_timestamp).days
            if days_needed <= 0: days_needed = 30
            fetch_start_ts = int((earliest_timestamp - timedelta(days=days_needed)).timestamp() * 1000)
            mode = f"EKLENIYOR ({days_needed} gün)"
        else:
            fetch_end_ts = int(datetime.utcnow().timestamp() * 1000)
            fetch_start_ts = int((datetime.utcnow() - timedelta(days=DAYS_TO_FETCH)).timestamp() * 1000)
            mode = f"SIFIRDAN ({DAYS_TO_FETCH} gün)"

        all_ohlcv = []
        current_since = fetch_start_ts
        
        # Veri çekme döngüsü
        while current_since < fetch_end_ts:
            try:
                data = local_exchange.fetch_ohlcv(symbol, TIMEFRAME, current_since, 1000)
            except Exception as e:
                time.sleep(1)
                continue
                
            if not data: break
            
            all_ohlcv.extend(data)
            last_ts = data[-1][0]
            if last_ts >= fetch_end_ts or last_ts == current_since: break
            current_since = last_ts + 1
            
        # Merge ve Kayıt
        if all_ohlcv:
            new_df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            new_df['timestamp'] = pd.to_datetime(new_df['timestamp'], unit='ms')
            
            if existing_df is not None:
                final_df = pd.concat([new_df, existing_df])
            else:
                final_df = new_df
                
            final_df = final_df.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
            final_df.to_csv(filename, index=False)
            
            return {'symbol': symbol, 'file': filename, 'status': 'SUCCESS', 'msg': f"{mode} - Toplam: {len(final_df)}"}
        else:
            if existing_df is not None:
                 return {'symbol': symbol, 'file': filename, 'status': 'SUCCESS', 'msg': "Yeni veri yok, korundu"}
            return {'symbol': symbol, 'file': filename, 'status': 'FAILED', 'msg': "Veri alınamadı"}
            
    except Exception as e:
        return {'symbol': symbol, 'file': filename, 'status': 'ERROR', 'msg': str(e)}
    finally:
        if hasattr(local_exchange, 'close'):
            local_exchange.close()

def fetch_and_save_data():
    """90 günlük veriyi çekip CSV'ye kaydet"""
    print("=" * 70)
    print("📥 VERİ ÇEKME VE KAYDETME (GENİŞLETİLMİŞ)")
    print("=" * 70)
    print(f"📅 Son {DAYS_TO_FETCH} günlük veri çekilecek")
    print(f"🎯 Coin aralığı: {START_RANK}-{END_RANK}")
    print(f"⏱️ Timeframe: {TIMEFRAME}")
    print("=" * 70)
    
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Klasör oluştur
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
    
    print("\n📋 Coin listesi alınıyor...")
    coins = get_sorted_coins()
    if not coins: return
    
    print(f"✅ {len(coins)} coin bulundu. Paralel çekim başlıyor ({MAX_WORKERS} Worker)...")
    print("=" * 70)

    saved_count = 0
    coin_list = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_coin = {executor.submit(process_coin_fetch, coin): coin for coin in coins}
        
        for i, future in enumerate(as_completed(future_to_coin), 1):
            res = future.result()
            symbol = res['symbol']
            status = res['status']
            msg = res['msg']
            
            print(f"[{i}/{len(coins)}] {symbol:<15} : {status} | {msg}")
            
            if status in ['SUCCESS', 'SKIPPED']:
                saved_count += 1
                coin_list.append({'symbol': symbol, 'file': res['file']})
    
    # Coin listesini de kaydet
    coin_df = pd.DataFrame(coin_list)
    coin_df.to_csv(f"{DATA_FOLDER}/_coin_list.csv", index=False)
    
    print("\n" + "=" * 70)
    print("✅ VERİ ÇEKME TAMAMLANDI")
    print("=" * 70)
    print(f"📊 Toplam: {saved_count}/{len(coins)} coin kaydedildi")
    print(f"📁 Konum: {DATA_FOLDER}/")
    print("=" * 70)

if __name__ == "__main__":
    fetch_and_save_data()
