"""
UZUN VADELİ BOT BACKTEST
Tarih: 15 Şubat 2026
Backtest Dönemi: 9-14 Şubat 2026 (5 gün)

Bu script uzun_vadeli_bot.py stratejisini geçmiş verilerle test eder.
Tüm giriş/çıkış noktaları, TP seviyeleri, kar/zarar detayları loglanır.
"""
import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import pandas_ta as ta
import logging
from datetime import datetime, timedelta
import json
import os

# --- LOG AYARLARI ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('backtest_results.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Windows terminal için encoding düzelt
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# --- KONFİGÜRASYON ---
def load_config():
    """API anahtarlarını yükle - önce .env, sonra config.py, sonra manuel"""
    # 1. .env dosyasından dene
    try:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        sandbox = os.getenv('EXCHANGE_SANDBOX', 'false').lower() == 'true'
        
        if api_key and api_secret:
            return api_key, api_secret, sandbox
    except ImportError:
        pass  # dotenv yüklü değil
    except Exception:
        pass
    
    # 2. .env dosyasını manuel oku (dotenv olmadan)
    try:
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                env_vars = {}
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
                
                api_key = env_vars.get('BINANCE_API_KEY')
                api_secret = env_vars.get('BINANCE_API_SECRET')
                sandbox = env_vars.get('EXCHANGE_SANDBOX', 'false').lower() == 'true'
                
                if api_key and api_secret:
                    return api_key, api_secret, sandbox
    except Exception:
        pass
    
    # 3. config.py'den dene
    try:
        import config
        return config.BINANCE_API_KEY, config.BINANCE_API_SECRET, False
    except:
        pass
    
    return None, None, False

class BacktestEngine:
    """Backtest motoru - Geçmiş verilerle stratejinin performansını test eder"""
    
    def __init__(self, api_key, api_secret, sandbox=False):
        exchange_options = {
            'enableRateLimit': True,
            'timeout': 30000,
        }
        
        # Backtest için public API yeterli (sadece OHLCV çekiyoruz)
        # API key olmadan da geçmiş veriler çekilebilir
        if api_key and api_secret:
            exchange_options['apiKey'] = api_key
            exchange_options['secret'] = api_secret
        
        # Futures için option ekle
        exchange_options['options'] = {'defaultType': 'future'}
        
        self.exchange = ccxt.binance(exchange_options)
        self.sandbox = sandbox
        
        # Backtest parametreleri
        self.start_date = datetime(2026, 2, 9)  # 9 Şubat 2026 (Geçen hafta Pazar)
        self.end_date = datetime(2026, 2, 14, 23, 59)  # 14 Şubat 2026 (Geçen hafta Cuma)
        self.timeframe = '4h'
        
        # Strateji parametreleri (uzun_vadeli_bot ile aynı)
        self.max_active_trades = 4  # Aynı anda en fazla 4 pozisyon
        self.min_total_trades = 3  # Minimum 3 işlem açılmalı
        self.max_total_trades = 8  # Maksimum 8 işlem açılabilir
        self.leverage = 5
        self.initial_capital = 10000  # Başlangıç sermayesi ($)
        self.position_size_divider = 4  # Parayı 4'e böl (her işlem için capital/4)
        
        # Test sonuçları
        self.trades = []
        self.active_positions = {}
        self.closed_trades = []
        self.btc_data = None
        
    def calculate_fibonacci_levels(self, df, lookback=75):
        """Fibonacci seviyelerini hesapla"""
        recent_data = df.iloc[-lookback:] if len(df) >= lookback else df
        swing_high = recent_data['h'].max()
        swing_low = recent_data['l'].min()
        diff = swing_high - swing_low
        
        return {
            'peak': swing_high,
            'fib_0': swing_high,
            'fib_236': swing_high - (diff * 0.236),
            'fib_382': swing_high - (diff * 0.382),
            'fib_500': swing_high - (diff * 0.500),
            'fib_618': swing_high - (diff * 0.618),
            'fib_786': swing_high - (diff * 0.786),
            'fib_1': swing_low,
            'ext_1272': swing_high + (diff * 0.272),
            'ext_1618': swing_high + (diff * 0.618),
        }
    
    def check_divergence(self, df):
        """Bearish Divergence kontrolü"""
        if len(df) < 10:
            return False
        if df['c'].iloc[-1] > df['c'].iloc[-5:-1].max() and df['rsi'].iloc[-1] < df['rsi'].iloc[-10:-1].max():
            return True
        return False
    
    def check_signal(self, df, fib_levels, symbol):
        """5 Basamaklı Onay Sistemi"""
        if len(df) < 200:
            return None
            
        curr = df.iloc[-1]
        
        # BASAMAK 1: MACD Trend Yorgunluğu
        macd_hist_curr = curr['macd_hist']
        macd_hist_prev = df.iloc[-2]['macd_hist']
        macd_hist_declining = macd_hist_curr < macd_hist_prev
        macd_hist_negative = macd_hist_curr < 0
        
        if not (macd_hist_declining or macd_hist_negative):
            return None
        
        # BASAMAK 2: Lokasyon
        if curr['c'] < curr['ema200'] or curr['c'] < curr['bb_upper']:
            return None
        
        # BASAMAK 3: Fibonacci
        tolerance = 0.005
        near_fib_0 = abs(curr['h'] - fib_levels['fib_0']) / fib_levels['fib_0'] < tolerance
        near_ext_1272 = abs(curr['h'] - fib_levels['ext_1272']) / fib_levels['ext_1272'] < tolerance
        near_ext_1618 = abs(curr['h'] - fib_levels['ext_1618']) / fib_levels['ext_1618'] < tolerance
        
        if not (near_fib_0 or near_ext_1272 or near_ext_1618):
            return None
        
        if curr['c'] >= fib_levels['fib_236']:
            return None
        
        # BASAMAK 4: Momentum
        if curr['rsi'] < 60 or curr['mfi'] < 75:
            return None
        
        if not self.check_divergence(df):
            return None
        
        # BASAMAK 5: Volume Trigger
        is_red = curr['c'] < curr['o']
        body_pct = abs(curr['c'] - curr['o']) / curr['o']
        avg_volume = df['v'].iloc[-6:-1].mean()
        vol_spike = curr['v'] > (avg_volume * 1.5)
        
        if not is_red or body_pct < 0.03 or not vol_spike:
            return None
        
        logging.info(f"✅ {symbol} SİNYAL BULUNDU!")
        logging.info(f"   MACD hist: {macd_hist_curr:.4f}")
        logging.info(f"   RSI: {curr['rsi']:.1f}, MFI: {curr['mfi']:.1f}")
        logging.info(f"   Fiyat: ${curr['c']:.6f}, BB Üst: ${curr['bb_upper']:.6f}")
        logging.info(f"   Gövde: %{body_pct*100:.1f}, Hacim: {vol_spike}")
        
        return "SHORT_IMMEDIATE"
    
    async def get_historical_data(self, symbol, start_timestamp, end_timestamp):
        """Belirli tarih aralığında geçmiş verileri çek"""
        try:
            all_candles = []
            current_timestamp = start_timestamp
            
            while current_timestamp < end_timestamp:
                ohlcv = await self.exchange.fetch_ohlcv(
                    symbol, 
                    timeframe=self.timeframe,
                    since=current_timestamp,
                    limit=1000
                )
                
                if not ohlcv:
                    break
                
                all_candles.extend(ohlcv)
                current_timestamp = ohlcv[-1][0] + 1
                
                if len(ohlcv) < 1000:
                    break
                
                await asyncio.sleep(0.1)
            
            # DataFrame'e çevir
            df = pd.DataFrame(all_candles, columns=['t', 'o', 'h', 'l', 'c', 'v'])
            df = df.drop_duplicates(subset=['t'])
            df = df.sort_values('t')
            
            # İndikatörleri ekle
            bb = ta.bbands(df['c'], length=20, std=2)
            df['bb_upper'] = bb['BBU_20_2.0']
            df['bb_mid'] = bb['BBM_20_2.0']
            df['rsi'] = ta.rsi(df['c'], length=14)
            df['mfi'] = ta.mfi(df['h'], df['l'], df['c'], df['v'], length=14)
            df['atr'] = ta.atr(df['h'], df['l'], df['c'], length=14)
            df['ema200'] = ta.ema(df['c'], length=200)
            
            macd = ta.macd(df['c'], fast=12, slow=26, signal=9)
            df['macd'] = macd['MACD_12_26_9']
            df['macd_signal'] = macd['MACDs_12_26_9']
            df['macd_hist'] = macd['MACDh_12_26_9']
            
            return df
            
        except Exception as e:
            logging.error(f"❌ {symbol} veri çekme hatası: {e}")
            return None
    
    async def simulate_position(self, symbol, entry_df, full_df, fib_levels):
        """Bir pozisyonu simüle et - giriş sonrası fiyat hareketlerini takip et"""
        entry_idx = len(entry_df) - 1
        curr = entry_df.iloc[-1]
        entry_price = curr['c']
        entry_time = pd.to_datetime(curr['t'], unit='ms')
        atr = curr['atr']
        
        # TP ve SL seviyeleri
        tp1_price = fib_levels['fib_500']
        tp2_price = fib_levels['fib_618']
        original_tp2 = tp2_price
        
        sl_atr_based = entry_price + (atr * 2)
        sl_fib_based = fib_levels['peak'] * 1.005
        sl_price = min(sl_atr_based, sl_fib_based)
        
        # Pozisyon boyutu hesapla (sermayenin 1/4'ü)
        position_capital = self.initial_capital / self.position_size_divider
        position_size_usdt = position_capital
        
        trade_info = {
            'symbol': symbol,
            'entry_time': entry_time,
            'entry_price': entry_price,
            'tp1': tp1_price,
            'tp2': tp2_price,
            'sl': sl_price,
            'fib_levels': fib_levels,
            'tp1_hit': False,
            'tp2_hit': False,
            'sl_hit': False,
            'dynamic_tp_used': False,
            'exit_time': None,
            'exit_price': None,
            'exit_reason': None,
            'profit_pct': 0,
            'profit_usd': 0,
            'quantity': 1.0,
            'position_size_usdt': position_size_usdt
        }
        
        logging.info(f"")
        logging.info(f"{'='*80}")
        logging.info(f"📊 POZİSYON AÇILDI #{len(self.closed_trades)+1}: {symbol}")
        logging.info(f"{'='*80}")
        logging.info(f"   Giriş Zamanı: {entry_time}")
        logging.info(f"   Giriş Fiyatı: ${entry_price:.6f}")
        logging.info(f"   Pozisyon Boyutu: ${position_size_usdt:.2f} (Sermayenin 1/{self.position_size_divider})")
        logging.info(f"   TP1 (Fib 0.5): ${tp1_price:.6f}")
        logging.info(f"   TP2 (Fib 0.618): ${tp2_price:.6f}")
        logging.info(f"   SL: ${sl_price:.6f}")
        logging.info(f"   Risk/Reward: 1:{((entry_price - tp2_price)/(sl_price - entry_price)):.2f}")
        
        # Giriş sonrası mumları takip et
        for i in range(entry_idx + 1, len(full_df)):
            candle = full_df.iloc[i]
            candle_time = pd.to_datetime(candle['t'], unit='ms')
            high = candle['h']
            low = candle['l']
            close = candle['c']
            
            # TP1 Kontrolü
            if not trade_info['tp1_hit'] and low <= tp1_price:
                trade_info['tp1_hit'] = True
                trade_info['quantity'] = 0.5
                trade_info['sl'] = entry_price  # SL breakeven
                profit_tp1 = ((entry_price - tp1_price) / entry_price) * 100 * 0.5
                profit_tp1_usd = position_size_usdt * (profit_tp1 / 100)
                
                logging.info(f"")
                logging.info(f"🎯 {symbol} TP1'E ULAŞTI!")
                logging.info(f"   Zaman: {candle_time}")
                logging.info(f"   Fiyat: ${low:.6f}")
                logging.info(f"   %50 pozisyon kapandı - Kar: %{profit_tp1:.2f} (${profit_tp1_usd:.2f})")
                logging.info(f"   SL breakeven'e çekildi: ${entry_price:.6f}")
                continue
            
            # TP2 Kontrolü
            if trade_info['tp1_hit'] and not trade_info['tp2_hit'] and low <= tp2_price:
                trade_info['tp2_hit'] = True
                trade_info['exit_time'] = candle_time
                trade_info['exit_price'] = tp2_price
                trade_info['exit_reason'] = 'TP2_HIT'
                
                profit_total = ((entry_price - tp1_price) / entry_price) * 100 * 0.5
                profit_total += ((entry_price - tp2_price) / entry_price) * 100 * 0.5
                trade_info['profit_pct'] = profit_total
                trade_info['profit_usd'] = position_size_usdt * (profit_total / 100)
                
                logging.info(f"")
                logging.info(f"🎯🎯 {symbol} TP2'YE ULAŞTI!")
                logging.info(f"   Zaman: {candle_time}")
                logging.info(f"   Fiyat: ${tp2_price:.6f}")
                logging.info(f"   TOPLAM KAR: %{profit_total:.2f} (${trade_info['profit_usd']:.2f})")
                if trade_info['dynamic_tp_used']:
                    logging.info(f"   🚀 BTC dinamik TP sayesinde ekstra kar!")
                logging.info(f"   ✅ Pozisyon tamamen kapatıldı")
                break
            
            # SL Kontrolü
            if high >= trade_info['sl']:
                trade_info['sl_hit'] = True
                trade_info['exit_time'] = candle_time
                trade_info['exit_price'] = trade_info['sl']
                trade_info['exit_reason'] = 'SL_HIT'
                
                if trade_info['tp1_hit']:
                    # Breakeven SL
                    trade_info['profit_pct'] = ((entry_price - tp1_price) / entry_price) * 100 * 0.5
                    trade_info['profit_usd'] = position_size_usdt * (trade_info['profit_pct'] / 100)
                    logging.info(f"")
                    logging.info(f"🔄 {symbol} BREAKEVEN SL TETİKLENDİ")
                    logging.info(f"   Zaman: {candle_time}")
                    logging.info(f"   Fiyat: ${trade_info['sl']:.6f}")
                    logging.info(f"   Zarar yok, %50 kar korundu: %{trade_info['profit_pct']:.2f} (${trade_info['profit_usd']:.2f})")
                else:
                    # İlk SL
                    trade_info['profit_pct'] = ((entry_price - trade_info['sl']) / entry_price) * 100
                    trade_info['profit_usd'] = position_size_usdt * (trade_info['profit_pct'] / 100)
                    logging.info(f"")
                    logging.info(f"🛑 {symbol} SL TETİKLENDİ")
                    logging.info(f"   Zaman: {candle_time}")
                    logging.info(f"   Fiyat: ${trade_info['sl']:.6f}")
                    logging.info(f"   ZARAR: %{trade_info['profit_pct']:.2f} (${trade_info['profit_usd']:.2f})")
                break
        
        # Hala açık pozisyon varsa (backtest sonu)
        if not trade_info['sl_hit'] and not trade_info['tp2_hit']:
            last_candle = full_df.iloc[-1]
            last_price = last_candle['c']
            last_time = pd.to_datetime(last_candle['t'], unit='ms')
            
            trade_info['exit_time'] = last_time
            trade_info['exit_price'] = last_price
            trade_info['exit_reason'] = 'BACKTEST_END'
            
            if trade_info['tp1_hit']:
                profit_total = ((entry_price - tp1_price) / entry_price) * 100 * 0.5
                profit_total += ((entry_price - last_price) / entry_price) * 100 * 0.5
            else:
                profit_total = ((entry_price - last_price) / entry_price) * 100
            
            trade_info['profit_pct'] = profit_total
            trade_info['profit_usd'] = position_size_usdt * (profit_total / 100)
            
            logging.info(f"")
            logging.info(f"⏸️ {symbol} POZİSYON AÇIK (Backtest Sonu)")
            logging.info(f"   Son Fiyat: ${last_price:.6f}")
            logging.info(f"   Gerçekleşmemiş Kar/Zarar: %{profit_total:.2f}")
        
        self.closed_trades.append(trade_info)
        return trade_info
    
    async def run_backtest(self):
        """Backtest'i çalıştır"""
        
        # Top coinleri belirle (gerçek bottan farklı olarak manuel liste)
        # Normalde fetch_eligible_symbols kullanılır, ama backtest için sabit liste
        test_symbols = [
            'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'ADA/USDT', 'AVAX/USDT',
            'DOT/USDT', 'LINK/USDT', 'NEAR/USDT', 'ATOM/USDT', 'ICP/USDT',
            'ARB/USDT', 'OP/USDT', 'APT/USDT', 'SUI/USDT', 'SEI/USDT',
            'FIL/USDT', 'HBAR/USDT', 'DOGE/USDT', 'SHIB/USDT', 'PEPE/USDT'
        ]
        
        logging.info("")
        logging.info("="*80)
        logging.info("🔬 UZUN VADELİ BOT BACKTEST BAŞLATILIYOR")
        logging.info("="*80)
        logging.info(f"📅 Başlangıç: {self.start_date.strftime('%d.%m.%Y')}")
        logging.info(f"📅 Bitiş: {self.end_date.strftime('%d.%m.%Y')}")
        logging.info(f"⏱️ Timeframe: {self.timeframe}")
        logging.info(f"📊 Strateji: 5 Basamaklı Onay Sistemi + Fibonacci")
        logging.info(f"🔍 Test Edilen Coinler: {len(test_symbols)}")
        logging.info("="*80)
        logging.info("")
        
        start_ts = int(self.start_date.timestamp() * 1000)
        end_ts = int(self.end_date.timestamp() * 1000)
        
        # BTC verilerini çek (referans için)
        logging.info("📊 BTC/USDT verileri çekiliyor...")
        self.btc_data = await self.get_historical_data('BTC/USDT', start_ts - 86400000*30, end_ts)
        
        logging.info(f"🔍 {len(test_symbols)} coin taranacak...")
        logging.info("")
        
        # Her coin için verileri çek ve sinyalleri kontrol et
        for symbol in test_symbols:
            try:
                logging.info(f"📈 {symbol} analiz ediliyor...")
                
                # Geçmiş verileri çek (200 mum öncesinden başla - EMA200 için)
                df = await self.get_historical_data(symbol, start_ts - 86400000*50, end_ts)
                
                if df is None or len(df) < 200:
                    logging.warning(f"   ⚠️ {symbol} yeterli veri yok, atlanıyor")
                    continue
                
                # Backtest dönemi içindeki her 4 saatlik mumu kontrol et
                backtest_df = df[df['t'] >= start_ts]
                
                for idx in range(200, len(df)):  # EMA200 için en az 200 mum gerekli
                    current_df = df.iloc[:idx+1]
                    current_candle = current_df.iloc[-1]
                    candle_time = pd.to_datetime(current_candle['t'], unit='ms')
                    
                    # Backtest dışı mumları atla
                    if current_candle['t'] < start_ts or current_candle['t'] > end_ts:
                        continue
                    
                    # KURAL 1: Maksimum işlem sayısı kontrolü (max 8 trade)
                    if len(self.closed_trades) >= self.max_total_trades:
                        continue
                    
                    # KURAL 2: Aynı anda max pozisyon kontrolü (max 4 açık pozisyon)
                    if len(self.active_positions) >= self.max_active_trades:
                        continue
                    
                    # KURAL 3: Bu coin için zaten pozisyon var mı?
                    if symbol in self.active_positions:
                        continue
                    
                    # Fibonacci seviyelerini hesapla
                    fib_levels = self.calculate_fibonacci_levels(current_df)
                    
                    # Sinyal kontrolü
                    signal = self.check_signal(current_df, fib_levels, symbol)
                    
                    if signal:
                        # Pozisyon aç ve simüle et
                        self.active_positions[symbol] = True
                        trade = await self.simulate_position(symbol, current_df, df, fib_levels)
                        del self.active_positions[symbol]
                
                await asyncio.sleep(0.2)  # Rate limit
                
            except Exception as e:
                logging.error(f"❌ {symbol} backtest hatası: {e}")
                continue
        
        # Sonuçları raporla
        self.generate_report()
    
    def generate_report(self):
        """Backtest sonuçlarını raporla"""
        logging.info("")
        logging.info("="*80)
        logging.info("📊 BACKTEST SONUÇLARI")
        logging.info("="*80)
        logging.info("")
        
        if not self.closed_trades:
            logging.info("❌ Hiç trade açılmadı!")
            logging.info(f"⚠️  Not: Strateji minimum {self.min_total_trades} işlem açılmasını gerektirir")
            return
        
        total_trades = len(self.closed_trades)
        
        # Pozisyon Yönetimi Kontrolü
        logging.info("🎯 POZİSYON YÖNETİMİ KURALLARI:")
        logging.info(f"   💰 Başlangıç Sermayesi: ${self.initial_capital:.2f}")
        logging.info(f"   📊 Her İşlem Boyutu: ${self.initial_capital/self.position_size_divider:.2f} (1/{self.position_size_divider} sermaye)")
        logging.info(f"   🔢 Aynı Anda Max Pozisyon: {self.max_active_trades}")
        logging.info(f"   ⬆️  Min Toplam İşlem: {self.min_total_trades}")
        logging.info(f"   ⬇️  Max Toplam İşlem: {self.max_total_trades}")
        logging.info(f"   ✅ Açılan İşlem Sayısı: {total_trades}")
        
        if total_trades < self.min_total_trades:
            logging.info(f"   ⚠️  DİKKAT: Minimum işlem sayısına ({self.min_total_trades}) ulaşılamadı!")
        
        logging.info("")
        
        winning_trades = [t for t in self.closed_trades if t['profit_pct'] > 0]
        losing_trades = [t for t in self.closed_trades if t['profit_pct'] < 0]
        breakeven_trades = [t for t in self.closed_trades if t['profit_pct'] == 0]
        
        total_profit_pct = sum(t['profit_pct'] for t in self.closed_trades)
        total_profit_usd = sum(t.get('profit_usd', 0) for t in self.closed_trades)
        avg_profit = total_profit_pct / total_trades if total_trades > 0 else 0
        
        win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        
        final_capital = self.initial_capital + total_profit_usd
        roi = (total_profit_usd / self.initial_capital * 100) if self.initial_capital > 0 else 0
        
        logging.info(f"📈 GENEL İSTATİSTİKLER:")
        logging.info(f"   Toplam İşlem: {total_trades}")
        logging.info(f"   Kazanan: {len(winning_trades)} (%{win_rate:.1f})")
        logging.info(f"   Kaybeden: {len(losing_trades)}")
        logging.info(f"   Breakeven: {len(breakeven_trades)}")
        logging.info(f"")
        logging.info(f"💰 KAR/ZARAR:")
        logging.info(f"   Toplam Net: %{total_profit_pct:.2f} (${total_profit_usd:.2f})")
        logging.info(f"   Ortalama: %{avg_profit:.2f}")
        logging.info(f"   Başlangıç: ${self.initial_capital:.2f}")
        logging.info(f"   Son Durum: ${final_capital:.2f}")
        logging.info(f"   ROI: %{roi:.2f}")
        logging.info(f"")
        
        if winning_trades:
            best_trade = max(winning_trades, key=lambda x: x['profit_pct'])
            avg_win = sum(t['profit_pct'] for t in winning_trades) / len(winning_trades)
            logging.info(f"✅ KAZANAN İŞLEMLER:")
            logging.info(f"   En İyi: {best_trade['symbol']} - %{best_trade['profit_pct']:.2f}")
            logging.info(f"   Ortalama Kazanç: %{avg_win:.2f}")
            logging.info(f"")
        
        if losing_trades:
            worst_trade = min(losing_trades, key=lambda x: x['profit_pct'])
            avg_loss = sum(t['profit_pct'] for t in losing_trades) / len(losing_trades)
            logging.info(f"❌ KAYBEDEN İŞLEMLER:")
            logging.info(f"   En Kötü: {worst_trade['symbol']} - %{worst_trade['profit_pct']:.2f}")
            logging.info(f"   Ortalama Kayıp: %{avg_loss:.2f}")
            logging.info(f"")
        
        logging.info(f"📋 DETAYLI İŞLEM LİSTESİ:")
        logging.info("")
        
        for i, trade in enumerate(self.closed_trades, 1):
            status = "✅ KAR" if trade['profit_pct'] > 0 else "❌ ZARAR" if trade['profit_pct'] < 0 else "🔄 BREAKEVEN"
            profit_usd = trade.get('profit_usd', 0)
            logging.info(f"{i}. {trade['symbol']} - {status}")
            logging.info(f"   Giriş: {trade['entry_time'].strftime('%d.%m %H:%M')} @ ${trade['entry_price']:.6f}")
            logging.info(f"   Çıkış: {trade['exit_time'].strftime('%d.%m %H:%M')} @ ${trade['exit_price']:.6f}")
            logging.info(f"   Sebep: {trade['exit_reason']}")
            logging.info(f"   TP1: {'✅' if trade['tp1_hit'] else '❌'} | TP2: {'✅' if trade['tp2_hit'] else '❌'} | SL: {'✅' if trade['sl_hit'] else '❌'}")
            logging.info(f"   Net Kar/Zarar: %{trade['profit_pct']:.2f} (${profit_usd:.2f})")
            logging.info("")
        
        # JSON olarak kaydet
        with open('backtest_results.json', 'w') as f:
            json.dump({
                'backtest_config': {
                    'start_date': self.start_date.isoformat(),
                    'end_date': self.end_date.isoformat(),
                    'timeframe': self.timeframe,
                    'initial_capital': self.initial_capital,
                    'position_size_divider': self.position_size_divider,
                    'max_active_trades': self.max_active_trades,
                    'min_total_trades': self.min_total_trades,
                    'max_total_trades': self.max_total_trades
                },
                'summary': {
                    'total_trades': total_trades,
                    'winning_trades': len(winning_trades),
                    'losing_trades': len(losing_trades),
                    'win_rate': win_rate,
                    'total_profit_pct': total_profit_pct,
                    'total_profit_usd': total_profit_usd,
                    'avg_profit_pct': avg_profit,
                    'final_capital': final_capital,
                    'roi': roi
                },
                'trades': [{
                    'symbol': t['symbol'],
                    'entry_time': t['entry_time'].isoformat(),
                    'entry_price': float(t['entry_price']),
                    'exit_time': t['exit_time'].isoformat() if t['exit_time'] else None,
                    'exit_price': float(t['exit_price']) if t['exit_price'] else None,
                    'exit_reason': t['exit_reason'],
                    'profit_pct': float(t['profit_pct']),
                    'profit_usd': float(t.get('profit_usd', 0)),
                    'position_size_usdt': float(t.get('position_size_usdt', 0)),
                    'tp1_hit': t['tp1_hit'],
                    'tp2_hit': t['tp2_hit'],
                    'sl_hit': t['sl_hit']
                } for t in self.closed_trades]
            }, f, indent=2)
        
        logging.info("💾 Sonuçlar 'backtest_results.json' dosyasına kaydedildi")
        logging.info("📄 Detaylı loglar 'backtest_results.log' dosyasında")
    
    async def close(self):
        await self.exchange.close()


# --- ÇALIŞTIRMA ---
async def main():
    # Backtest için API key gerekmez (sadece public OHLCV okuyoruz)
    api_key = None
    api_secret = None
    sandbox = False
    
    print("")
    print("="*80)
    print("🔬 UZUN VADELİ BOT BACKTEST")
    print("="*80)
    print("✅ PUBLIC API: API key olmadan geçmiş veriler çekilecek")
    print("✅ Sadece OKUMA: Geçmiş OHLCV verileri çekilecek, işlem yapılmayacak")
    
    print("")
    print("📅 Test Dönemi: 9-14 Şubat 2026 (GEÇEN HAFTA)")
    print("📊 Strateji: 5 Basamaklı Onay + Fibonacci + BTC Dinamik TP")
    print("⏱️  Süre: ~5-10 dakika (20 coin x geçmiş veriler)")
    print("🔍 Test Edilecek: ETH, SOL, BNB, ADA, AVAX ve 15 coin daha")
    print("="*80)
    print("")
    
    confirm = input("⏸️  Backtest başlatılsın mı? (y/n) [y]: ").strip().lower()
    if confirm and confirm != 'y':
        print("❌ İşlem iptal edildi")
        return
    
    engine = BacktestEngine(api_key, api_secret, sandbox)
    
    try:
        await engine.run_backtest()
    except KeyboardInterrupt:
        print("\n🛑 Backtest kullanıcı tarafından durduruldu")
    except Exception as e:
        print(f"\n❌ Backtest hatası: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.close()

if __name__ == "__main__":
    asyncio.run(main())
