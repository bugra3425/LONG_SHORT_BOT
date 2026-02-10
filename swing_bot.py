import ccxt
import pandas as pd
import pandas_ta as ta
import requests
import time
import sys
import warnings
from datetime import datetime

# Pandas uyarılarını kapat
warnings.filterwarnings('ignore', category=FutureWarning)
pd.set_option('future.no_silent_downcasting', True)

# ==========================================
# ⚙️ SWING BOT - BTC TAKİPLİ ÇİFT YÖNLÜ
# ==========================================
# Özellikler:
# - BTC trend analizi ile yön belirleme
# - Hem LONG hem SHORT sinyal
# - 5x-10x kaldıraç (güce göre)
# - 1-4 saat pozisyon süresi
# ==========================================

API_KEY = 'YOUR_API_KEY_HERE'
SECRET_KEY = 'YOUR_SECRET_KEY_HERE'
TELEGRAM_TOKEN = '8063148867:AAH2UX__oKRPtXGyZWtBEmMJOZOMY1GN3Lc'
CHAT_ID = '6786568689'

# Multi-Timeframe Ayarları (Swing için 15m ve 1h odaklı)
TIMEFRAMES = ['4h', '1h', '15m']
TF_NAMES = {'4h': '4 Saat', '1h': 'Saatlik', '15m': '15 Dakika'}
TF_RELIABILITY = {'4h': 15, '1h': 10, '15m': 5}

# Swing Trading Ayarları
LEVERAGE_MIN = 5
LEVERAGE_MAX = 10
POSITION_TIME_MIN = 1  # saat
POSITION_TIME_MAX = 4  # saat

# Strateji Ayarları
SCORE_THRESHOLD = 70           # Optimize edilmiş
STRONG_SIGNAL_THRESHOLD = 75   # Güçlü sinyal (yüksek kaldıraç)
MAX_SIGNALS_PER_HOUR = 10
MIN_VOLUME_USD = 10_000_000    # 10M USD
SCAN_COIN_COUNT = 50
MIN_WIN_RATE = 65              # Optimize edilmiş

# 🏆 1-8 ŞUBAT EN BAŞARILI COİNLER (Backtest Sonuçları)
TOP_PERFORMERS = [
    'ENSO/USDT:USDT',        # +233.6% WR:81%
    'ASTER/USDT:USDT',       # +185.5% WR:69%
    'WHITEWHALE/USDT:USDT',  # +183.6% WR:70%
    'PIPPIN/USDT:USDT',      # +173.6% WR:68%
    'GPS/USDT:USDT',         # +167.9% WR:74%
    'ETH/USDT:USDT',         # +157.1%
    'BANANAS31/USDT:USDT',   # +158.2%
    'ALCH/USDT:USDT',        # +135.7%
    'DASH/USDT:USDT',        # +121.8%
    'STABLE/USDT:USDT',      # +119.4%
    'KAITO/USDT:USDT',       # +111.3%
    'ENA/USDT:USDT',         # +94.2%
    'IP/USDT:USDT',          # +94.2%
    'BERA/USDT:USDT',        # +92.3%
    'NEAR/USDT:USDT',        # +92.1%
    'KITE/USDT:USDT',        # +91.8%
    'SHIB1000/USDT:USDT',    # +84.3%
    'UNI/USDT:USDT',         # +82.2%
    'SOL/USDT:USDT',         # +81.1%
    'AVAX/USDT:USDT',        # +75.0%
]
USE_TOP_PERFORMERS = True  # True = sadece başarılı coinler, False = tüm coinler

# BTC Ağırlığı
BTC_TREND_WEIGHT = 15          # BTC aynı yönde ise +15 puan
BTC_COUNTER_PENALTY = -8       # BTC ters yönde ise -8 puan (hafifletildi)

# ==========================================
# 🔌 BORSA BAĞLANTISI
# ==========================================
try:
    exchange_config = {
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    }
    
    if API_KEY != 'YOUR_API_KEY_HERE':
        exchange_config['apiKey'] = API_KEY
        exchange_config['secret'] = SECRET_KEY
    else:
        print("ℹ️ API Anahtarı girilmedi. Bot 'Public Mod'da çalışacak.")

    exchange = ccxt.binance(exchange_config)
except Exception as e:
    print(f"Bağlantı Hatası: {e}")
    sys.exit()

# ==========================================
# 🛠️ YARDIMCI FONKSİYONLAR
# ==========================================

def send_telegram_message(message):
    """Telegram mesaj gönder."""
    if TELEGRAM_TOKEN == 'YOUR_TELEGRAM_BOT_TOKEN':
        print(f"TELEGRAM: {message}")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Hatası: {e}")

def fetch_ohlcv_safe(symbol, timeframe, limit=150):
    """Güvenli OHLCV veri çekme."""
    for attempt in range(3):
        try:
            data = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if data and len(data) >= 50:
                return data
        except:
            if attempt < 2:
                time.sleep(1)
    return None

def get_funding_rate(symbol):
    """Binance Futures Funding Rate."""
    try:
        clean_symbol = symbol.replace('/', '').split(':')[0]
        url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={clean_symbol}&limit=1"
        response = requests.get(url, timeout=5).json()
        if response and isinstance(response, list) and len(response) > 0:
            return float(response[0]['fundingRate'])
        return 0.0
    except:
        return 0.0

def get_open_interest_change(symbol):
    """Open Interest değişimi (son 4 saat)."""
    try:
        clean_symbol = symbol.replace('/', '').split(':')[0]
        url = f"https://fapi.binance.com/futures/data/openInterestHist?symbol={clean_symbol}&period=1h&limit=4"
        response = requests.get(url, timeout=5).json()
        if response and isinstance(response, list) and len(response) >= 2:
            current = float(response[-1]['sumOpenInterest'])
            prev = float(response[0]['sumOpenInterest'])
            if prev > 0:
                return ((current - prev) / prev) * 100
        return 0.0
    except:
        return 0.0

def get_taker_ratio(symbol):
    """Taker Buy/Sell Ratio."""
    try:
        clean_symbol = symbol.replace('/', '').split(':')[0]
        url = f"https://fapi.binance.com/futures/data/takerlongshortRatio?symbol={clean_symbol}&period=1h&limit=1"
        response = requests.get(url, timeout=5).json()
        if response and isinstance(response, list) and len(response) > 0:
            return float(response[0]['buySellRatio'])
        return 1.0
    except:
        return 1.0

def calculate_leverage(score, win_rate):
    """Sinyal gücüne göre kaldıraç hesapla (5x-10x)."""
    if score >= 90 and win_rate >= 75:
        return 10
    elif score >= 80 and win_rate >= 70:
        return 8
    elif score >= 70 and win_rate >= 65:
        return 7
    elif score >= 60:
        return 6
    return LEVERAGE_MIN

def calculate_position_time(timeframe, score):
    """Timeframe ve skora göre tahmini pozisyon süresi (saat)."""
    base_times = {'4h': 4, '1h': 2, '15m': 1}
    base = base_times.get(timeframe, 2)
    
    # Güçlü sinyalde daha uzun tutma
    if score >= 85:
        return min(base + 1, POSITION_TIME_MAX)
    return base

def calculate_risk_reward_long(entry, stop):
    """LONG için TP seviyeleri."""
    risk = abs(entry - stop)
    tp1 = entry + (risk * 1.5)   # 1:1.5 R:R
    tp2 = entry + (risk * 2.5)   # 1:2.5 R:R
    tp3 = entry + (risk * 4)     # 1:4 R:R
    return tp1, tp2, tp3

def calculate_risk_reward_short(entry, stop):
    """SHORT için TP seviyeleri."""
    risk = abs(entry - stop)
    tp1 = entry - (risk * 1.5)
    tp2 = entry - (risk * 2.5)
    tp3 = entry - (risk * 4)
    return tp1, tp2, tp3

# ==========================================
# 📊 BTC TREND ANALİZİ
# ==========================================

def analyze_btc_trend():
    """
    BTC'nin mevcut trendini belirler.
    Returns: 'BULLISH', 'BEARISH', 'NEUTRAL' ve güç skoru
    """
    try:
        symbol = 'BTC/USDT:USDT'
        
        # 1H ve 4H verileri çek
        ohlcv_1h = fetch_ohlcv_safe(symbol, '1h', 100)
        ohlcv_4h = fetch_ohlcv_safe(symbol, '4h', 50)
        
        if not ohlcv_1h or not ohlcv_4h:
            return 'NEUTRAL', 0
        
        # 1H DataFrame
        df_1h = pd.DataFrame(ohlcv_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_1h['ema9'] = ta.ema(df_1h['close'], length=9)
        df_1h['ema21'] = ta.ema(df_1h['close'], length=21)
        df_1h['ema50'] = ta.ema(df_1h['close'], length=50)
        df_1h['rsi'] = ta.rsi(df_1h['close'], length=14)
        
        macd_1h = ta.macd(df_1h['close'], fast=12, slow=26, signal=9)
        if macd_1h is not None:
            df_1h['macd'] = macd_1h.iloc[:, 0]
            df_1h['macd_signal'] = macd_1h.iloc[:, 1]
        
        adx_1h = ta.adx(df_1h['high'], df_1h['low'], df_1h['close'], length=14)
        if adx_1h is not None:
            df_1h['adx'] = adx_1h.iloc[:, 0]
            df_1h['di_plus'] = adx_1h.iloc[:, 1]
            df_1h['di_minus'] = adx_1h.iloc[:, 2]
        
        df_1h = df_1h.ffill().fillna(0)
        last_1h = df_1h.iloc[-1]
        
        # 4H DataFrame  
        df_4h = pd.DataFrame(ohlcv_4h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df_4h['ema9'] = ta.ema(df_4h['close'], length=9)
        df_4h['ema21'] = ta.ema(df_4h['close'], length=21)
        df_4h['rsi'] = ta.rsi(df_4h['close'], length=14)
        df_4h = df_4h.ffill().fillna(0)
        last_4h = df_4h.iloc[-1]
        
        # Trend Puanlama
        bull_score = 0
        bear_score = 0
        
        price = float(last_1h['close'])
        ema9 = float(last_1h['ema9'])
        ema21 = float(last_1h['ema21'])
        ema50 = float(last_1h['ema50'])
        rsi = float(last_1h['rsi'])
        adx = float(last_1h['adx']) if 'adx' in last_1h else 0
        di_plus = float(last_1h['di_plus']) if 'di_plus' in last_1h else 0
        di_minus = float(last_1h['di_minus']) if 'di_minus' in last_1h else 0
        macd = float(last_1h['macd']) if 'macd' in last_1h else 0
        macd_signal = float(last_1h['macd_signal']) if 'macd_signal' in last_1h else 0
        
        # 1. EMA Dizilimi
        if price > ema9 > ema21 > ema50:
            bull_score += 25
        elif price < ema9 < ema21 < ema50:
            bear_score += 25
        elif price > ema21:
            bull_score += 10
        elif price < ema21:
            bear_score += 10
        
        # 2. RSI
        if rsi > 60:
            bull_score += 15
        elif rsi < 40:
            bear_score += 15
        
        # 3. ADX + DI
        if adx > 25:
            if di_plus > di_minus:
                bull_score += 20
            else:
                bear_score += 20
        
        # 4. MACD
        if macd > macd_signal:
            bull_score += 15
        else:
            bear_score += 15
        
        # 5. 4H Trend Doğrulama
        price_4h = float(last_4h['close'])
        ema21_4h = float(last_4h['ema21'])
        rsi_4h = float(last_4h['rsi'])
        
        if price_4h > ema21_4h and rsi_4h > 50:
            bull_score += 20
        elif price_4h < ema21_4h and rsi_4h < 50:
            bear_score += 20
        
        # Sonuç
        if bull_score >= bear_score + 20:
            return 'BULLISH', bull_score
        elif bear_score >= bull_score + 20:
            return 'BEARISH', bear_score
        else:
            return 'NEUTRAL', max(bull_score, bear_score)
            
    except Exception as e:
        print(f"BTC Trend Hatası: {e}")
        return 'NEUTRAL', 0

# ==========================================
# 🧠 ÇİFT YÖNLÜ ANALİZ MOTORU
# ==========================================

def analyze_timeframe_dual(symbol, timeframe, btc_trend):
    """
    Tek timeframe için hem LONG hem SHORT analizi.
    BTC trend ağırlıklandırması uygulanır.
    """
    try:
        ohlcv = fetch_ohlcv_safe(symbol, timeframe)
        if not ohlcv:
            return None

        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        # İndikatör Hesaplamaları
        df['ema9'] = ta.ema(df['close'], length=9)
        df['ema21'] = ta.ema(df['close'], length=21)
        df['ema50'] = ta.ema(df['close'], length=50)
        df['sma100'] = ta.sma(df['close'], length=100)
        df['rsi'] = ta.rsi(df['close'], length=14)
        
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None:
            df['macd'] = macd.iloc[:, 0]
            df['macd_signal'] = macd.iloc[:, 1]
            df['macd_hist'] = macd.iloc[:, 2]
        else:
            df['macd'] = df['macd_signal'] = df['macd_hist'] = 0
        
        bb = ta.bbands(df['close'], length=20, std=2)
        if bb is not None:
            df['bb_lower'] = bb.iloc[:, 0]
            df['bb_middle'] = bb.iloc[:, 1]
            df['bb_upper'] = bb.iloc[:, 2]
            df['bb_pct'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        else:
            df['bb_pct'] = 0.5
        
        adx_data = ta.adx(df['high'], df['low'], df['close'], length=14)
        if adx_data is not None:
            df['adx'] = adx_data.iloc[:, 0]
            df['di_plus'] = adx_data.iloc[:, 1]
            df['di_minus'] = adx_data.iloc[:, 2]
        else:
            df['adx'] = df['di_plus'] = df['di_minus'] = 0
        
        stoch_rsi = ta.stochrsi(df['close'], length=14)
        if stoch_rsi is not None:
            df['stoch_k'] = stoch_rsi.iloc[:, 0]
        else:
            df['stoch_k'] = 50
        
        df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=14)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['vol_sma'] = ta.sma(df['volume'], length=20)
        
        df = df.ffill().fillna(0)
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(last['close'])
        
        # Değerleri al
        ema9 = float(last['ema9']) if pd.notna(last['ema9']) else price
        ema21 = float(last['ema21']) if pd.notna(last['ema21']) else price
        ema50 = float(last['ema50']) if pd.notna(last['ema50']) else price
        rsi = float(last['rsi']) if pd.notna(last['rsi']) else 50
        adx = float(last['adx']) if pd.notna(last['adx']) else 0
        di_plus = float(last['di_plus']) if pd.notna(last['di_plus']) else 0
        di_minus = float(last['di_minus']) if pd.notna(last['di_minus']) else 0
        macd_val = float(last['macd']) if pd.notna(last['macd']) else 0
        macd_sig = float(last['macd_signal']) if pd.notna(last['macd_signal']) else 0
        macd_hist = float(last['macd_hist']) if pd.notna(last['macd_hist']) else 0
        bb_pct = float(last['bb_pct']) if pd.notna(last['bb_pct']) else 0.5
        stoch_k = float(last['stoch_k']) if pd.notna(last['stoch_k']) else 50
        mfi = float(last['mfi']) if pd.notna(last['mfi']) else 50
        atr = float(last['atr']) if pd.notna(last['atr']) else price * 0.02
        
        prev_ema9 = float(prev['ema9']) if pd.notna(prev['ema9']) else price
        prev_ema21 = float(prev['ema21']) if pd.notna(prev['ema21']) else price
        prev_macd = float(prev['macd']) if pd.notna(prev['macd']) else 0
        prev_macd_sig = float(prev['macd_signal']) if pd.notna(prev['macd_signal']) else 0
        
        # ═══════════════════════════════════════════════════════════════
        # LONG PUANLAMA (Maks 150 puan)
        # ═══════════════════════════════════════════════════════════════
        long_score = 0
        long_reasons = []
        
        # 1. ADX + DI+ (Trend Gücü) - 25p
        if adx > 25 and di_plus > di_minus:
            long_score += 25
            long_reasons.append(f"📈 ADX Güçlü ({adx:.0f}) + DI+: +25p")
        elif di_plus > di_minus * 1.1:
            long_score += 12
            long_reasons.append(f"📈 DI+ > DI-: +12p")
        
        # 2. EMA Dizilimi - 25p
        if price > ema9 > ema21 > ema50:
            long_score += 25
            long_reasons.append("🟢 Bullish EMA Dizilimi: +25p")
        elif price > ema21 and ema9 > ema21:
            long_score += 15
            long_reasons.append("📈 EMA Bullish: +15p")
        # Golden Cross
        if prev_ema9 <= prev_ema21 and ema9 > ema21:
            long_score += 20
            long_reasons.append("⭐ GOLDEN CROSS: +20p")
        
        # 3. RSI - 20p
        if rsi < 30:
            long_score += 20
            long_reasons.append(f"🔥 RSI Aşırı Satım ({rsi:.0f}): +20p")
        elif rsi < 40:
            long_score += 15
            long_reasons.append(f"📉 RSI Düşük ({rsi:.0f}): +15p")
        elif rsi > 50 and rsi < 70:
            long_score += 8
            long_reasons.append(f"📊 RSI Bullish Zone ({rsi:.0f}): +8p")
        
        # 4. MACD - 25p
        if prev_macd <= prev_macd_sig and macd_val > macd_sig:
            long_score += 25
            long_reasons.append("⭐ MACD Bullish Cross: +25p")
        elif macd_val > macd_sig and macd_hist > 0:
            long_score += 15
            long_reasons.append("📈 MACD Bullish: +15p")
        
        # 5. BB - 20p
        if bb_pct < 0.1:
            long_score += 20
            long_reasons.append("🔥 BB Alt Bant Bounce: +20p")
        elif bb_pct < 0.25:
            long_score += 12
            long_reasons.append("📉 BB Alt Bölge: +12p")
        
        # 6. StochRSI - 15p
        if stoch_k < 20:
            long_score += 15
            long_reasons.append(f"🔥 StochRSI Aşırı Satım ({stoch_k:.0f}): +15p")
        elif stoch_k < 35:
            long_score += 8
            long_reasons.append(f"📉 StochRSI Düşük ({stoch_k:.0f}): +8p")
        
        # 7. MFI - 10p
        if mfi < 25:
            long_score += 10
            long_reasons.append(f"💰 MFI Aşırı Satım ({mfi:.0f}): +10p")
        
        # 8. Volume Spike - 10p
        vol = float(last['volume']) if pd.notna(last['volume']) else 0
        vol_sma = float(last['vol_sma']) if pd.notna(last['vol_sma']) else vol
        is_green = last['close'] > last['open']
        if vol > vol_sma * 1.5 and is_green:
            long_score += 10
            long_reasons.append("📊 Yüksek Hacim + Yeşil Mum: +10p")
        
        # ═══════════════════════════════════════════════════════════════
        # SHORT PUANLAMA (Maks 150 puan)
        # ═══════════════════════════════════════════════════════════════
        short_score = 0
        short_reasons = []
        
        # 1. ADX + DI- - 25p
        if adx > 25 and di_minus > di_plus:
            short_score += 25
            short_reasons.append(f"📉 ADX Güçlü ({adx:.0f}) + DI-: +25p")
        elif di_minus > di_plus * 1.1:
            short_score += 12
            short_reasons.append(f"📉 DI- > DI+: +12p")
        
        # 2. EMA Dizilimi - 25p
        if price < ema9 < ema21 < ema50:
            short_score += 25
            short_reasons.append("🔴 Bearish EMA Dizilimi: +25p")
        elif price < ema21 and ema9 < ema21:
            short_score += 15
            short_reasons.append("📉 EMA Bearish: +15p")
        # Death Cross
        if prev_ema9 >= prev_ema21 and ema9 < ema21:
            short_score += 20
            short_reasons.append("💀 DEATH CROSS: +20p")
        
        # 3. RSI - 20p
        if rsi > 80:
            short_score += 20
            short_reasons.append(f"🔥 RSI Aşırı Alım ({rsi:.0f}): +20p")
        elif rsi > 70:
            short_score += 15
            short_reasons.append(f"📈 RSI Yüksek ({rsi:.0f}): +15p")
        elif rsi > 50 and rsi < 60:
            short_score += 5
            short_reasons.append(f"📊 RSI Nötr ({rsi:.0f}): +5p")
        
        # 4. MACD - 25p
        if prev_macd >= prev_macd_sig and macd_val < macd_sig:
            short_score += 25
            short_reasons.append("💀 MACD Bearish Cross: +25p")
        elif macd_val < macd_sig and macd_hist < 0:
            short_score += 15
            short_reasons.append("📉 MACD Bearish: +15p")
        
        # 5. BB - 20p
        if bb_pct > 0.95:
            short_score += 20
            short_reasons.append("🔥 BB Üst Bant Reddi: +20p")
        elif bb_pct > 0.8:
            short_score += 12
            short_reasons.append("📈 BB Üst Bölge: +12p")
        
        # 6. StochRSI - 15p
        if stoch_k > 85:
            short_score += 15
            short_reasons.append(f"🔥 StochRSI Aşırı Alım ({stoch_k:.0f}): +15p")
        elif stoch_k > 70:
            short_score += 8
            short_reasons.append(f"📈 StochRSI Yüksek ({stoch_k:.0f}): +8p")
        
        # 7. MFI - 10p
        if mfi > 80:
            short_score += 10
            short_reasons.append(f"💰 MFI Aşırı Alım ({mfi:.0f}): +10p")
        
        # 8. Volume Spike - 10p
        is_red = last['close'] < last['open']
        if vol > vol_sma * 1.5 and is_red:
            short_score += 10
            short_reasons.append("📊 Yüksek Hacim + Kırmızı Mum: +10p")
        
        # ═══════════════════════════════════════════════════════════════
        # BTC TREND AĞIRLANDIRMASI
        # ═══════════════════════════════════════════════════════════════
        btc_direction, btc_strength = btc_trend
        
        if btc_direction == 'BULLISH':
            long_score += BTC_TREND_WEIGHT
            long_reasons.append(f"₿ BTC Bullish Desteği: +{BTC_TREND_WEIGHT}p")
            short_score += BTC_COUNTER_PENALTY
            short_reasons.append(f"₿ BTC Karşıt Yön: {BTC_COUNTER_PENALTY}p")
        elif btc_direction == 'BEARISH':
            short_score += BTC_TREND_WEIGHT
            short_reasons.append(f"₿ BTC Bearish Desteği: +{BTC_TREND_WEIGHT}p")
            long_score += BTC_COUNTER_PENALTY
            long_reasons.append(f"₿ BTC Karşıt Yön: {BTC_COUNTER_PENALTY}p")
        
        # Yön Belirleme
        direction = None
        score = 0
        reasons = []
        
        # Fark en az 10 puan olmalı (düşürüldü)
        if long_score >= short_score + 10 and long_score >= SCORE_THRESHOLD:
            direction = 'LONG'
            score = long_score
            reasons = long_reasons
        elif short_score >= long_score + 10 and short_score >= SCORE_THRESHOLD:
            direction = 'SHORT'
            score = short_score
            reasons = short_reasons
        
        if not direction:
            return None
        
        return {
            'tf': timeframe,
            'direction': direction,
            'score': score,
            'long_score': long_score,
            'short_score': short_score,
            'price': price,
            'atr': atr,
            'adx': adx,
            'rsi': rsi,
            'bb_pct': bb_pct,
            'reasons': reasons
        }

    except Exception as e:
        return None

# ==========================================
# 🎯 WIN RATE VE KALDIRAÇ HESAPLAMA
# ==========================================

def calculate_swing_win_rate(tf_results, btc_trend):
    """Multi-TF sonuçlarına göre Win Rate hesaplar."""
    win_rates = {}
    signal_tfs = []
    direction = None
    
    for tf, result in tf_results.items():
        if result and result['score'] >= SCORE_THRESHOLD:
            signal_tfs.append(tf)
            
            if direction is None:
                direction = result['direction']
            
            # Baz oran: %55
            wr = 55
            
            # Skor bonusu
            if result['score'] >= 90:
                wr += 15
            elif result['score'] >= 75:
                wr += 10
            elif result['score'] >= 60:
                wr += 5
            
            # TF güvenilirlik
            wr += TF_RELIABILITY.get(tf, 0)
            
            win_rates[tf] = wr
    
    # Confluence bonusu
    if len(signal_tfs) >= 3:
        for tf in win_rates:
            win_rates[tf] += 12
    elif len(signal_tfs) >= 2:
        for tf in win_rates:
            win_rates[tf] += 7
    
    # BTC uyumu bonusu
    btc_direction, btc_strength = btc_trend
    if direction:
        if (direction == 'LONG' and btc_direction == 'BULLISH') or \
           (direction == 'SHORT' and btc_direction == 'BEARISH'):
            for tf in win_rates:
                win_rates[tf] += 8
    
    return win_rates, signal_tfs, direction

def select_best_signal(tf_results, win_rates, signal_tfs):
    """En iyi sinyal TF'ini seçer."""
    if not signal_tfs:
        return None, 0
    
    # Confluence varsa 1H tercih
    if len(signal_tfs) >= 2 and '1h' in signal_tfs:
        return '1h', win_rates.get('1h', 0)
    
    # En yüksek skor
    best_tf = max(signal_tfs, key=lambda tf: tf_results[tf]['score'])
    return best_tf, win_rates.get(best_tf, 0)

# ==========================================
# 🔥 ANA ANALİZ FONKSİYONU
# ==========================================

def analyze_coin_swing(symbol, rank, btc_trend):
    """Coin için swing analizi yapar."""
    try:
        tf_results = {}
        for tf in TIMEFRAMES:
            result = analyze_timeframe_dual(symbol, tf, btc_trend)
            tf_results[tf] = result
            time.sleep(0.2)
        
        # Yön tutarlılık kontrolü - en az 1 TF yeterli (gevşetildi)
        directions = [r['direction'] for r in tf_results.values() if r]
        if not directions:
            return None
        
        # En dominant yönü al
        from collections import Counter
        dir_counts = Counter(directions)
        dominant_dir, count = dir_counts.most_common(1)[0]
        
        # En az 1 TF yeterli (önceden 2 idi)
        if count < 1:
            return None
        
        # Ters yöndeki TF'leri filtrele
        for tf in list(tf_results.keys()):
            if tf_results[tf] and tf_results[tf]['direction'] != dominant_dir:
                tf_results[tf] = None
        
        # Win rate hesapla
        win_rates, signal_tfs, direction = calculate_swing_win_rate(tf_results, btc_trend)
        
        if not signal_tfs:
            return None
        
        # En iyi TF
        best_tf, win_rate = select_best_signal(tf_results, win_rates, signal_tfs)
        
        if win_rate < MIN_WIN_RATE:
            return None
        
        selected = tf_results[best_tf]
        if not selected:
            return None
        
        price = selected['price']
        atr = selected['atr']
        score = selected['score']
        
        # Kaldıraç ve pozisyon süresi
        leverage = calculate_leverage(score, win_rate)
        position_time = calculate_position_time(best_tf, score)
        
        # Stop Loss ve TP hesapla
        if direction == 'LONG':
            stop_loss = price - (atr * 2.0)  # ATR x 2 stop
            tp1, tp2, tp3 = calculate_risk_reward_long(price, stop_loss)
        else:  # SHORT
            stop_loss = price + (atr * 2.0)
            tp1, tp2, tp3 = calculate_risk_reward_short(price, stop_loss)
        
        # Binance verileri
        funding = get_funding_rate(symbol)
        oi_change = get_open_interest_change(symbol)
        taker_ratio = get_taker_ratio(symbol)
        
        return {
            'symbol': symbol,
            'rank': rank,
            'direction': direction,
            'best_tf': best_tf,
            'score': score,
            'win_rate': win_rate,
            'leverage': leverage,
            'position_time': position_time,
            'price': price,
            'stop_loss': stop_loss,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'atr': atr,
            'funding': funding,
            'oi_change': oi_change,
            'taker_ratio': taker_ratio,
            'confluence': len(signal_tfs),
            'reasons': selected['reasons'],
            'btc_trend': btc_trend
        }
        
    except Exception as e:
        return None

# ==========================================
# 📤 SİNYAL FORMATLAMA
# ==========================================

def format_swing_signal(signal):
    """Telegram mesajı formatlar."""
    coin = signal['symbol'].split('/')[0]
    direction = signal['direction']
    emoji = "🟢 LONG" if direction == 'LONG' else "🔴 SHORT"
    btc_dir = signal['btc_trend'][0]
    btc_emoji = "📈" if btc_dir == 'BULLISH' else "📉" if btc_dir == 'BEARISH' else "➖"
    
    msg = f"""
{'='*35}
{emoji} <b>SWİNG SİNYALİ</b>
{'='*35}

<b>💎 {coin}/USDT</b> (Rank #{signal['rank']})
<b>📊 Yön:</b> {direction}
<b>🎯 Skor:</b> {signal['score']}/150
<b>📈 Win Rate:</b> %{signal['win_rate']:.0f}
<b>⚡ Kaldıraç:</b> {signal['leverage']}x
<b>⏱️ Süre:</b> ~{signal['position_time']} saat

{btc_emoji} <b>BTC Trend:</b> {btc_dir}

<b>📍 Giriş:</b> ${signal['price']:.4f}
<b>🛑 Stop Loss:</b> ${signal['stop_loss']:.4f}

<b>🎯 Hedefler:</b>
  TP1 (30%): ${signal['tp1']:.4f}
  TP2 (30%): ${signal['tp2']:.4f}  
  TP3 (40%): ${signal['tp3']:.4f}

<b>📊 Confluence:</b> {signal['confluence']}/3 TF
<b>⏰ TF:</b> {TF_NAMES[signal['best_tf']]}

<b>📉 Piyasa Verileri:</b>
• Funding: {signal['funding']*100:.4f}%
• OI Değişim: {signal['oi_change']:+.1f}%
• Taker Ratio: {signal['taker_ratio']:.2f}

<b>🔍 Nedenler:</b>
"""
    for reason in signal['reasons'][:6]:
        msg += f"• {reason}\n"
    
    msg += f"\n⚠️ <i>Risk: Pozisyonun %1-2'si</i>"
    
    return msg

# ==========================================
# 🔄 ANA DÖNGÜ
# ==========================================

def get_top_coins(limit=SCAN_COIN_COUNT):
    """Hacme göre top coinleri al veya başarılı coin listesini kullan."""
    try:
        # Başarılı coin listesi aktifse onu kullan
        if USE_TOP_PERFORMERS:
            print(f"🏆 Geçen hafta başarılı {len(TOP_PERFORMERS)} coin taranıyor...")
            return [{'symbol': s, 'volume': 0} for s in TOP_PERFORMERS]
        
        tickers = exchange.fetch_tickers()
        
        futures = []
        for symbol, data in tickers.items():
            if ':USDT' in symbol and data.get('quoteVolume'):
                vol = float(data['quoteVolume'])
                if vol >= MIN_VOLUME_USD:
                    futures.append({
                        'symbol': symbol,
                        'volume': vol
                    })
        
        # Hacme göre sırala
        futures.sort(key=lambda x: x['volume'], reverse=True)
        return futures[:limit]
        
    except Exception as e:
        print(f"Coin listesi hatası: {e}")
        return []

def run_swing_scanner():
    """Ana tarama döngüsü."""
    print("="*50)
    print("🔄 SWING BOT - ÇİFT YÖNLÜ TARAMA BAŞLIYOR")
    print("="*50)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # BTC Trend Analizi
    print("₿ BTC Trend Analizi yapılıyor...")
    btc_trend = analyze_btc_trend()
    btc_dir, btc_strength = btc_trend
    btc_emoji = "📈 BULLISH" if btc_dir == 'BULLISH' else "📉 BEARISH" if btc_dir == 'BEARISH' else "➖ NEUTRAL"
    print(f"₿ BTC Trend: {btc_emoji} (Güç: {btc_strength})")
    print()
    
    # Top coinleri al
    print(f"📊 Top {SCAN_COIN_COUNT} coin taranıyor...")
    coins = get_top_coins()
    
    if not coins:
        print("❌ Coin listesi alınamadı!")
        return
    
    signals = []
    
    for i, coin_data in enumerate(coins, 1):
        symbol = coin_data['symbol']
        coin_name = symbol.split('/')[0]
        
        print(f"  [{i}/{len(coins)}] {coin_name}...", end=" ")
        
        try:
            result = analyze_coin_swing(symbol, i, btc_trend)
            
            if result:
                signals.append(result)
                dir_emoji = "🟢" if result['direction'] == 'LONG' else "🔴"
                print(f"{dir_emoji} {result['direction']} Skor:{result['score']} WR:{result['win_rate']:.0f}% {result['leverage']}x")
            else:
                print("➖ Sinyal yok")
                
        except Exception as e:
            print(f"❌ Hata: {e}")
        
        time.sleep(0.3)
    
    # Sonuçları sırala (skor + win rate)
    signals.sort(key=lambda x: (x['score'] + x['win_rate']), reverse=True)
    
    # Özet
    print()
    print("="*50)
    print(f"📊 TARAMA SONUÇLARI")
    print("="*50)
    
    long_count = sum(1 for s in signals if s['direction'] == 'LONG')
    short_count = sum(1 for s in signals if s['direction'] == 'SHORT')
    
    print(f"🟢 LONG Sinyalleri: {long_count}")
    print(f"🔴 SHORT Sinyalleri: {short_count}")
    print(f"📊 Toplam: {len(signals)}")
    print()
    
    # En iyi 5 sinyal
    if signals:
        print("🏆 EN İYİ 5 SİNYAL:")
        print("-"*40)
        
        for i, sig in enumerate(signals[:5], 1):
            coin = sig['symbol'].split('/')[0]
            dir_emoji = "🟢" if sig['direction'] == 'LONG' else "🔴"
            print(f"{i}. {dir_emoji} {coin} | {sig['direction']} | Skor:{sig['score']} | WR:{sig['win_rate']:.0f}% | {sig['leverage']}x | ~{sig['position_time']}h")
        
        # İlk 3 sinyali Telegram'a gönder
        print()
        print("📤 Telegram'a gönderiliyor...")
        
        # Özet mesajı
        summary = f"""
🔄 SWİNG BOT TARAMA SONUÇLARI
━━━━━━━━━━━━━━━━━━━━━━━━━━
₿ BTC: {btc_emoji}
🟢 LONG: {long_count} | 🔴 SHORT: {short_count}
📊 Toplam Sinyal: {len(signals)}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        send_telegram_message(summary)
        
        for sig in signals[:3]:
            msg = format_swing_signal(sig)
            send_telegram_message(msg)
            time.sleep(1)
        
        print("✅ Gönderildi!")
    else:
        print("❌ Uygun sinyal bulunamadı.")
        send_telegram_message("🔄 Swing Tarama: Uygun sinyal bulunamadı.")
    
    return signals

# ==========================================
# 🚀 BAŞLAT
# ==========================================

if __name__ == "__main__":
    print()
    print("="*50)
    print("  🔄 SWING BOT v1.0 - ÇİFT YÖNLÜ TRADİNG")
    print("="*50)
    print()
    print("📋 Özellikler:")
    print("  • BTC trend takibi ile yön belirleme")
    print("  • Hem LONG hem SHORT sinyal")
    print("  • 5x-10x dinamik kaldıraç")
    print("  • 1-4 saat pozisyon süresi")
    print("  • Multi-timeframe confluence")
    print()
    
    while True:
        try:
            run_swing_scanner()
            
            print()
            print(f"⏳ Sonraki tarama: 30 dakika sonra")
            print("   (Ctrl+C ile çıkış)")
            
            # 30 dakika bekle
            for i in range(30, 0, -1):
                print(f"\r⏰ {i} dakika kaldı...", end="")
                time.sleep(60)
            print()
            
        except KeyboardInterrupt:
            print("\n\n👋 Bot durduruldu.")
            break
        except Exception as e:
            print(f"\n❌ Hata: {e}")
            print("⏳ 5 dakika sonra tekrar denenecek...")
            time.sleep(300)
