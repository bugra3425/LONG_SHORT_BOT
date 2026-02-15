"""
KISA VADELİ BOT - Fibonacci Scalping Stratejisi
Dosya: kisa_vadeli_bot.py
Tarih: 15 Şubat 2026
Strateji: Bollinger Bands + Fibonacci Retracement
Timeframe: 1 dakikalık mumlar
Hedef: Küçük/orta boy volatil coinler (BTC/ETH/DOGE hariç)

Özellikler:
    • Fibonacci onayı ile giriş/çıkış
    • TP1 (Fib 0.5): %50 pozisyon kapat
    • TP2 (Fib 0.618 - Altın Oran): Kalan %50 kapat
    • Her 10 saniyede tarama
    • API key gerektirmez (sadece sinyal verir)
    
Kullanım:
    python kisa_vadeli_bot.py
"""
import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import pandas_ta as ta
import logging
import time
import sys
from datetime import datetime

# --- LOG AYARLARI ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- KONFİGÜRASYON YÜKLEME ---
def load_config():
    """config.py dosyasından API anahtarlarını yükle (varsa)"""
    try:
        import config
        return config.BINANCE_API_KEY, config.BINANCE_API_SECRET
    except ImportError:
        return None, None
    except AttributeError:
        return None, None

class BugraBot:
    def __init__(self):
        # API key'siz çalışır (sadece public data okur)
        self.exchange = ccxt.binance({
            'options': {'defaultType': 'future'},
            'enableRateLimit': True,
            'timeout': 30000,  # 30 saniye timeout
            'rateLimit': 50,  # Rate limit
        })
        self.leverage = 5
        self.stop_loss_pct = 0.03  # %3
        self.min_volume = 20_000_000
        self.timeframe = '1m'  # 1 dakikalık mumlar - Hızlı sinyal için
        
        # Cooldown sistemi: Aynı coin için 5dk bekleme
        self.last_signal_time = {}  # {symbol: timestamp}
        self.cooldown_seconds = 300  # 5 dakika
        
        # Connection retry
        self.max_retries = 3
        self.retry_delay = 5  # saniye

    async def fetch_high_volatility_coins(self):
        """En çok yükselen/düşen 50 küçük/orta boy coini getirir (büyük coinler hariç)."""
        for attempt in range(self.max_retries):
            try:
                tickers = await self.exchange.fetch_tickers()
                
                # Büyük market cap'li coinleri filtrele (manuel liste)
                excluded_symbols = {
                    'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT',
                    'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT',
                    'LTC/USDT', 'LINK/USDT', 'UNI/USDT', 'ATOM/USDT', 'XLM/USDT',
                    'BCH/USDT', 'ETC/USDT', 'FIL/USDT', 'APT/USDT', 'NEAR/USDT',
                    'ICP/USDT', 'HBAR/USDT', 'VET/USDT', 'ARB/USDT', 'OP/USDT',
                    'MKR/USDT', 'AAVE/USDT', 'GRT/USDT', 'SAND/USDT', 'MANA/USDT'
                }
                
                # Filtreler:
                # 1. USDT çiftleri
                # 2. Büyük coinler HARİÇ
                # 3. Hacim > 20M (likidite)
                # 4. Fiyat > $0.0001 (çok düşük hacimli shitcoinleri çıkar)
                futures_tickers = [
                    t for t in tickers.values() 
                    if '/USDT' in t['symbol'] 
                    and t['symbol'] not in excluded_symbols  # Büyük coinleri çıkar
                    and t.get('quoteVolume', 0) > self.min_volume
                    and t.get('last', 0) > 0.0001
                ]
                
                # Yükselişe/düşüşe göre sırala - En çok hareket edenleri al
                # Pozitif = yükseliş (LONG için), Negatif = düşüş (SHORT için)
                sorted_tickers = sorted(
                    futures_tickers, 
                    key=lambda x: abs(x.get('percentage', 0)), 
                    reverse=True
                )
                return [t['symbol'] for t in sorted_tickers[:50]]
                
            except (ccxt.NetworkError, ccxt.ExchangeNotAvailable) as e:
                if attempt < self.max_retries - 1:
                    logging.warning(f"⚠️ Bağlantı hatası (Deneme {attempt + 1}/{self.max_retries}): {str(e)[:100]}")
                    logging.info(f"⏳ {self.retry_delay} saniye sonra tekrar denenecek...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    logging.error(f"❌ Binance'e bağlanılamadı. Lütfen internet bağlantınızı kontrol edin.")
                    return []
            except Exception as e:
                logging.error(f"❌ Beklenmeyen hata: {str(e)[:100]}")
                return []
        
        return []

    async def get_indicators(self, symbol):
        """Verileri çeker - Bollinger Bands ve göstergeler."""
        for attempt in range(self.max_retries):
            try:
                ohlcv = await self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=50)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                # Bollinger Bands
                bb = ta.bbands(df['close'], length=20, std=2)
                df['bb_upper'] = bb['BBU_20_2.0']
                df['bb_mid'] = bb['BBM_20_2.0']
                df['bb_lower'] = bb['BBL_20_2.0']
                df['sma'] = df['bb_mid']  # Orta band = SMA
                
                # RSI
                df['rsi'] = ta.rsi(df['close'], length=14)
                
                # Hacim ortalaması
                df['vol_ma'] = df['volume'].rolling(10).mean()
                
                return df
                
            except (ccxt.NetworkError, ccxt.ExchangeNotAvailable) as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)  # Kısa bekleme
                else:
                    return None
            except Exception:
                return None
        
        return None
    
    def calculate_fibonacci_levels(self, df, lookback=25):
        """Fibonacci Retracement seviyelerini hesapla (son 25 mum)."""
        # Son 25 mumu al
        recent_data = df.iloc[-lookback:]
        
        # Swing High (En yüksek tepe) ve Swing Low (En düşük dip)
        swing_high = recent_data['high'].max()
        swing_low = recent_data['low'].min()
        
        # Fark
        diff = swing_high - swing_low
        
        # Fibonacci seviyeleri (SHORT için - Yukarıdan aşağıya)
        fib_levels = {
            'peak': swing_high,  # 0% - Zirve
            'fib_0': swing_high,  # 0%
            'fib_236': swing_high - (diff * 0.236),  # 23.6%
            'fib_382': swing_high - (diff * 0.382),  # 38.2%
            'fib_500': swing_high - (diff * 0.500),  # 50%
            'fib_618': swing_high - (diff * 0.618),  # 61.8% (Altın Oran)
            'fib_786': swing_high - (diff * 0.786),  # 78.6%
            'fib_1': swing_low,  # 100% - Dip
            'ext_1272': swing_high + (diff * 0.272),  # 127.2% Uzatma
            'ext_1618': swing_high + (diff * 0.618),  # 161.8% Uzatma
        }
        
        return fib_levels

    def check_signal(self, df, fib_levels):
        """BOLLİNGER BANDS + FİBONACCI STRATEJİSİ: Fibonacci onaylı sinyaller."""
        if len(df) < 20:
            return None
            
        curr = df.iloc[-1]  # Şimdiki mum (giriş mumu)
        prev = df.iloc[-2]  # Önceki mum (sinyal mumu)
        prevs = df.iloc[-6:-2]  # Daha önceki 4 mum
        
        # ÖNCEKİ MUM (Sinyal Mumu) kontrolü
        prev_body_change = abs(prev['close'] - prev['open']) / prev['open']
        prev_vol_ratio = prev['volume'] / prev['vol_ma'] if prev['vol_ma'] > 0 else 0
        
        # --- SHORT SİNYALİ (FİBONACCI ONAYLANMIŞ) ---
        # Fibonacci Şartları:
        # 1. Önceki mum fiyatı Fibonacci 0% (peak) veya uzatma seviyelerinde (1.272/1.618)
        # 2. Sinyal mumu Fibonacci 0.236 seviyesinin ALTINDA kapanmalı (düzeltme başladı)
        
        # Fiyat zirveye yakın mı? (Peak'in %1 yakınında veya uzatma seviyelerinde)
        near_peak = abs(prev['high'] - fib_levels['peak']) / fib_levels['peak'] < 0.01
        near_ext_1272 = abs(prev['high'] - fib_levels['ext_1272']) / fib_levels['ext_1272'] < 0.01
        near_ext_1618 = abs(prev['high'] - fib_levels['ext_1618']) / fib_levels['ext_1618'] < 0.01
        
        at_fibonacci_peak = near_peak or near_ext_1272 or near_ext_1618
        
        # Sinyal mumu Fib 0.236'nın altında mı kapandı?
        closed_below_fib236 = prev['close'] < fib_levels['fib_236']
        
        if prev['close'] > prev['sma'] and prev['rsi'] > 60 and at_fibonacci_peak and closed_below_fib236:
            # Üst banda dokunma kontrolü
            streak_short = (prev['high'] >= prev['bb_upper']) or (prevs['high'] >= prevs['bb_upper']).any()
            is_red = prev['close'] < prev['open']
            
            if streak_short and is_red and prev_body_change >= 0.03 and prev_vol_ratio >= 1.3:
                # Şimdiki mumda giriş koşulları
                if curr['close'] <= prev['high'] * 1.01 and curr['close'] > curr['sma']:
                    return 'SHORT'

        # --- LONG SİNYALİ (FİBONACCI ONAYLANMIŞ) ---
        # Fibonacci Şartları:
        # 1. Önceki mum fiyatı Fibonacci 100% (dip) seviyesinde
        # 2. Sinyal mumu Fibonacci 0.786 seviyesinin ÜSTÜNDE kapanmalı (toparlanma başladı)
        
        # Fiyat dibe yakın mı?
        near_dip = abs(prev['low'] - fib_levels['fib_1']) / fib_levels['fib_1'] < 0.01
        
        # Sinyal mumu Fib 0.786'nın üstünde mü kapandı?
        closed_above_fib786 = prev['close'] > fib_levels['fib_786']
        
        if prev['close'] < prev['sma'] and prev['rsi'] < 40 and near_dip and closed_above_fib786:
            # Alt banda dokunma kontrolü
            streak_long = (prev['low'] <= prev['bb_lower']) or (prevs['low'] <= prevs['bb_lower']).any()
            is_green = prev['close'] > prev['open']
            
            if streak_long and is_green and prev_body_change >= 0.03 and prev_vol_ratio >= 1.3:
                # Şimdiki mumda giriş koşulları
                if curr['close'] >= prev['low'] * 0.99 and curr['close'] < curr['sma']:
                    return 'LONG'

        return None

    async def execute_trade(self, symbol, side, last_price, sl_price, tp_price, rsi, vol_ratio, signal_price, fib_levels):
        """Sinyal bilgisini terminale yazdırır (Binance'de işlem AÇMAZ)."""
        logging.info(f"")
        logging.info(f"{'='*70}")
        logging.info(f"⚡🎯 {side} SİNYALİ - FİBONACCI ONAYLANMIŞ!")  
        logging.info(f"{'='*70}")
        logging.info(f"💰 Coin: {symbol}")
        logging.info(f"📊 Yön: {side}")
        logging.info(f"📈 RSI (Sinyal Mumu): {rsi:.1f}")
        logging.info(f"📊 Hacim Oranı: {vol_ratio:.2f}x")
        logging.info(f"")
        logging.info(f"📐 FIBONACCI SEVİYELERİ:")
        logging.info(f"   Peak (0%): ${fib_levels['peak']:.6f}")
        logging.info(f"   Fib 0.236: ${fib_levels['fib_236']:.6f}")
        logging.info(f"   Fib 0.382: ${fib_levels['fib_382']:.6f}")
        logging.info(f"   Fib 0.500: ${fib_levels['fib_500']:.6f} ← TP1 (%50 kapat)")
        logging.info(f"   Fib 0.618: ${fib_levels['fib_618']:.6f} ← TP2 (Altın Oran, %50 kapat)")
        logging.info(f"   Fib 1.0  : ${fib_levels['fib_1']:.6f} (Dip)")
        logging.info(f"")
        logging.info(f"🕐 Sinyal Mumu Kapanış: ${signal_price:.6f}")
        logging.info(f"💵 Giriş (Şimdiki Mum): ${last_price:.6f}")
        logging.info(f"")
        
        if side == 'SHORT':
            tp1_price = fib_levels['fib_500']
            tp2_price = fib_levels['fib_618']
            # SL: %3 veya Peak'in %0.5 üstü
            sl_alternative = fib_levels['peak'] * 1.005
            sl_price = min(last_price * (1 + self.stop_loss_pct), sl_alternative)
            
            logging.info(f"🎯 TP1 (Fib 0.5): ${tp1_price:.6f} → Pozisyonun %50'sini kapat")
            logging.info(f"🎯 TP2 (Fib 0.618 - Altın): ${tp2_price:.6f} → Kalan %50'yi kapat")
            logging.info(f"🛑 Stop Loss: ${sl_price:.6f} (Peak + %0.5 veya %3)")
        else:  # LONG
            tp1_price = fib_levels['fib_500']
            tp2_price = fib_levels['fib_382']
            sl_alternative = fib_levels['fib_1'] * 0.995
            sl_price = max(last_price * (1 - self.stop_loss_pct), sl_alternative)
            
            logging.info(f"🎯 TP1 (Fib 0.5): ${tp1_price:.6f} → Pozisyonun %50'sini kapat")
            logging.info(f"🎯 TP2 (Fib 0.382): ${tp2_price:.6f} → Kalan %50'yi kapat")
            logging.info(f"🛑 Stop Loss: ${sl_price:.6f} (Dip - %0.5 veya %3)")
        
        logging.info(f"⚡ Kaldıraç: {self.leverage}x")
        logging.info(f"{'='*70}")
        logging.info(f"")

    async def scan_symbol(self, symbol):
        """Tek bir coini tarar."""
        try:
            # Cooldown kontrolü: Son 5 dakikada sinyal verdiysen atla
            now = time.time()
            if symbol in self.last_signal_time:
                elapsed = now - self.last_signal_time[symbol]
                if elapsed < self.cooldown_seconds:
                    return  # Henüz 5 dk geçmemiş, atla
            
            df = await self.get_indicators(symbol)
            
            # Veri alınamadıysa atla
            if df is None or len(df) < 25:
                return
            
            # Fibonacci seviyelerini hesapla
            fib_levels = self.calculate_fibonacci_levels(df)
            
            # Sinyal kontrol et (Fibonacci onaylı)
            signal = self.check_signal(df, fib_levels)
            
            if signal:
                curr = df.iloc[-1]  # Şimdiki mum (giriş)
                prev = df.iloc[-2]  # Önceki mum (sinyal)
                
                last_price = curr['close']
                signal_price = prev['close']  # Sinyal mumunun kapanış fiyatı
                rsi = prev['rsi']  # Sinyal mumunun RSI'ı
                vol_ratio = prev['volume'] / prev['vol_ma'] if prev['vol_ma'] > 0 else 0
                
                # Stop Loss ve Take Profit hesapla (Fibonacci bazlı)
                if signal == 'LONG':
                    sl_price = last_price * (1 - self.stop_loss_pct)
                    tp_price = fib_levels['fib_500']  # İlk hedef
                else:  # SHORT
                    sl_price = last_price * (1 + self.stop_loss_pct)
                    tp_price = fib_levels['fib_500']  # İlk hedef
                
                await self.execute_trade(symbol, signal, last_price, sl_price, tp_price, rsi, vol_ratio, signal_price, fib_levels)
                
                # Sinyal verdi, cooldown başlat
                self.last_signal_time[symbol] = now
                
        except Exception:
            pass # Bazı yeni coinlerde veri eksikliği olabilir, atla.

    async def run(self):
        logging.info("⚡🎯 BOLLINGER BANDS + FİBONACCI STRATEJİSİ - Her 10 saniyede tarama!")
        logging.info("📌 1 dakikalık mumlar | BB Upper/Lower + Fibonacci Retracement")
        logging.info("📌 Fibonacci: Son 25 mumdan Swing High/Low hesaplanır")
        logging.info("📌 SHORT: Zirve → Fib 0.236 altı kırmızı mum → Giriş")
        logging.info("📌 LONG: Dip → Fib 0.786 üstü yeşil mum → Giriş")
        logging.info("📌 TP1: Fib 0.5 (%50 kapat) | TP2: Fib 0.618 (Altın Oran, %50 kapat)")
        logging.info("📌 Filtre: Top 50 yükselen coin (BTC/ETH/DOGE gibi büyükler HARİÇ)")
        logging.info("📌 Hedef: Küçük/orta boy volatil coinler\n")
        
        scan_count = 0
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        while True:
            try:
                scan_count += 1
                symbols = await self.fetch_high_volatility_coins()
                
                if not symbols:
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logging.error(f"❌ Üst üste {max_consecutive_errors} kez bağlantı hatası.")
                        logging.error("⏸️ 60 saniye bekleniyor...")
                        await asyncio.sleep(60)
                        consecutive_errors = 0
                    else:
                        await asyncio.sleep(10)
                    continue
                
                # Başarılı bağlantı - counter'ı sıfırla
                consecutive_errors = 0
                
                if symbols:
                    logging.info(f"🔍 Tarama #{scan_count} - {len(symbols)} küçük/orta coin kontrol ediliyor...")
                
                tasks = [self.scan_symbol(s) for s in symbols]
                await asyncio.gather(*tasks, return_exceptions=True)  # Hataları yakala ama devam et
                
                await asyncio.sleep(10)  # 10 SANİYE'de bir tarama (hızlı!)
                
            except KeyboardInterrupt:
                logging.info("\n🛑 Kullanıcı tarafından durduruldu.")
                break
            except Exception as e:
                logging.error(f"❌ Ana döngü hatası: {str(e)[:100]}")
                await asyncio.sleep(10)

    async def close(self):
        """Exchange bağlantısını kapat."""
        await self.exchange.close()


# --- ÇALIŞTIRMA ---
if __name__ == "__main__":
    print("")
    print("="*70)
    print("⚡🚀 KISA VADELİ BOT - FİBONACCI SCALPING 🚀⚡")
    print("="*70)
    print("📌 Binance'de işlem AÇMAZ, SADECE SİNYALLER!")
    print("📌 Strateji: Bollinger Bands + Fibonacci Retracement")
    print("📌 SHORT: Zirveye dokundu + Fib 0.236 altı kapanış")
    print("📌 LONG: Dibe dokundu + Fib 0.786 üstü kapanış")
    print("📌 TP1 (Fib 0.5): Pozisyonun %50'sini kapat")
    print("📌 TP2 (Fib 0.618 - Altın Oran): Kalan %50'yi kapat")
    print("📌 Tarama: HER 10 SANİYE - Top 50 yükselen coin")
    print("📌 Filtre: BTC/ETH/DOGE gibi büyük coinler HARİÇ")
    print("📌 Hedef: Küçük/orta boy volatil coinler")
    print("📌 Cooldown: Aynı coin için 5 dakika bekleme")
    print("📌 Avantaj: Fibonacci ile bilimsel giriş/çıkış noktaları!")
    print("📌 API Key gerektirmez!")
    print("="*70)
    print("")
    
    bot = BugraBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n🛑 Bot durduruldu.")
    finally:
        asyncio.run(bot.close())
