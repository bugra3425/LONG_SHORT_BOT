import pandas as pd
import pandas_ta as ta
import warnings
import os
from datetime import datetime

warnings.filterwarnings('ignore')
pd.set_option('future.no_silent_downcasting', True)

# ==========================================
# ⚙️ SWING BACKTEST AYARLARI
# ==========================================
DATA_FOLDER = "backtest_data"
INITIAL_BALANCE = 1000
POSITION_SIZE_PCT = 10

# 📅 TARİH ARALIĞI - 1 ay önce 1 hafta (10-16 Ocak 2026)
BACKTEST_START = datetime(2026, 1, 12, 0, 0, 0)
BACKTEST_END = datetime(2026, 1, 21, 23, 59, 59)

# 🎯 TEK COİN TEST (None = tüm coinler)
SINGLE_COIN = None  # "BTC/USDT:USDT"

# 📋 İŞLEM DETAYLARI GÖSTER
SHOW_TRADE_DETAILS = True
SAVE_SIGNALS_CSV = True  # Sinyalleri CSV'ye kaydet

# ⚡ STRATEJİ FİLTRELERİ (OPTİMİZE)
SCORE_THRESHOLD_LONG = 65  # Long açmak için eşik biraz daha düşük
SCORE_THRESHOLD_SHORT = 75 # Short açmak için eşik daha yüksek
MIN_WIN_RATE = 65          # 55 -> 65
COOLDOWN_CANDLES = 8       # 4 -> 8 (daha az işlem)
MAX_TRADES_PER_COIN = 15   # 30 -> 15
MIN_SCORE_DIFF = 20        # LONG-SHORT farkı en az 20 puan

# 🎯 VOLATİLİTE FİLTRESİ (SIKI)
MAX_ATR_PERCENT = 5.0      # 8 -> 5 (aşırı volatil coinleri filtrele)
MIN_ATR_PERCENT = 0.4      # 0.3 -> 0.4

# 🎯 PARTIAL TP ORANLARI
TP1_CLOSE_PCT = 0.40       # 30 -> 40 (erken kar al)
TP2_CLOSE_PCT = 0.35       # 30 -> 35
TP3_CLOSE_PCT = 0.25       # 40 -> 25

# 🎯 SL VE TP ÇARPANLARI (OPTİMİZE)
SL_ATR_MULT = 1.5          # 2.0 -> 1.5 (daha sıkı SL)
TP1_RR = 1.2               # 1.5 -> 1.2 (daha gerçekçi)
TP2_RR = 2.0               # 2.5 -> 2.0
TP3_RR = 3.0               # 4.0 -> 3.0

TRAILING_STOP = True
PARTIAL_TP = True

# 🎯 KALDIRAÇ (dinamik)
def get_leverage(score, win_rate):
    if score >= 90 and win_rate >= 75:
        return 10
    elif score >= 80 and win_rate >= 70:
        return 8
    elif score >= 70 and win_rate >= 65:
        return 7
    elif score >= 60:
        return 6
    return 5

# ==========================================
# 📊 İNDİKATÖR HESAPLAMA
# ==========================================
def calculate_indicators(df):
    """İndikatörleri hesapla"""
    df = df.copy()
    df['ema9'] = ta.ema(df['close'], length=9)
    df['ema21'] = ta.ema(df['close'], length=21)
    df['ema50'] = ta.ema(df['close'], length=50)
    df['sma100'] = ta.sma(df['close'], length=100)
    df['rsi'] = ta.rsi(df['close'], length=14)
    
    macd = ta.macd(df['close'])
    if macd is not None:
        df['macd'] = macd.iloc[:, 0]
        df['macd_signal'] = macd.iloc[:, 1]
        df['macd_hist'] = macd.iloc[:, 2]
    else:
        df['macd'] = df['macd_signal'] = df['macd_hist'] = 0
    
    bb = ta.bbands(df['close'], length=20, std=2)
    if bb is not None:
        df['bb_lower'] = bb.iloc[:, 0]
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
    
    stoch = ta.stochrsi(df['close'], length=14)
    if stoch is not None:
        df['stoch_k'] = stoch.iloc[:, 0]
    else:
        df['stoch_k'] = 50
    
    df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=14)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    
    df = df.ffill().fillna(0).infer_objects(copy=False)
    return df

# ==========================================
# 🔍 ÇİFT YÖNLÜ SKOR HESAPLAMA
# ==========================================
def calculate_dual_score(row, prev_row):
    """LONG ve SHORT puanı hesapla"""
    price = float(row['close'])
    
    # Değerleri al
    adx = float(row['adx']) if pd.notna(row['adx']) else 0
    di_plus = float(row['di_plus']) if pd.notna(row['di_plus']) else 0
    di_minus = float(row['di_minus']) if pd.notna(row['di_minus']) else 0
    ema9 = float(row['ema9']) if pd.notna(row['ema9']) else price
    ema21 = float(row['ema21']) if pd.notna(row['ema21']) else price
    ema50 = float(row['ema50']) if pd.notna(row['ema50']) else price
    rsi = float(row['rsi']) if pd.notna(row['rsi']) else 50
    macd_val = float(row['macd']) if pd.notna(row['macd']) else 0
    macd_sig = float(row['macd_signal']) if pd.notna(row['macd_signal']) else 0
    macd_hist = float(row['macd_hist']) if pd.notna(row['macd_hist']) else 0
    bb_pct = float(row['bb_pct']) if pd.notna(row['bb_pct']) else 0.5
    stoch_k = float(row['stoch_k']) if pd.notna(row['stoch_k']) else 50
    mfi = float(row['mfi']) if pd.notna(row['mfi']) else 50
    
    prev_ema9 = float(prev_row['ema9']) if pd.notna(prev_row['ema9']) else price
    prev_ema21 = float(prev_row['ema21']) if pd.notna(prev_row['ema21']) else price
    prev_macd = float(prev_row['macd']) if pd.notna(prev_row['macd']) else 0
    prev_macd_sig = float(prev_row['macd_signal']) if pd.notna(prev_row['macd_signal']) else 0
    
    # ═══════════════════════════════════════════════════════════════
    # LONG/SHORT PUANLAMA (Maks 150 puan) - Kritik metriklere ağırlık verildi
    # ═══════════════════════════════════════════════════════════════
    long_score = 0
    long_reasons = []
    short_score = 0
    short_reasons = []
    # Son 50 mumun EMA50 ve EMA200 dizilimine bakarak trend belirle
    if 'btc_df' in globals() and btc_df is not None and len(btc_df) >= 200:
        ema50_arr = ta.ema(btc_df['close'], length=50)
        ema200_arr = ta.ema(btc_df['close'], length=200)
        # Son 50 mumda EMA50 > EMA200 olan mum sayısı
        bull_count = (ema50_arr[-50:] > ema200_arr[-50:]).sum()
        bear_count = (ema50_arr[-50:] < ema200_arr[-50:]).sum()
        if bull_count >= 30:
            btc_trend_bull = True
            btc_trend_bear = False
        elif bear_count >= 30:
            btc_trend_bull = False
            btc_trend_bear = True
        else:
            btc_trend_bull = False
            btc_trend_bear = False
        btc_ema50 = ema50_arr.iloc[-1]
        btc_ema200 = ema200_arr.iloc[-1]
    else:
        btc_ema50_series = ta.ema(pd.Series([price]), length=50) if hasattr(ta, 'ema') else None
        btc_ema200_series = ta.ema(pd.Series([price]), length=200) if hasattr(ta, 'ema') else None
        if btc_ema200_series is not None and hasattr(btc_ema200_series, 'iloc'):
            btc_ema200 = btc_ema200_series.iloc[-1]
        else:
            btc_ema200 = ema50  # fallback
        if btc_ema50_series is not None and hasattr(btc_ema50_series, 'iloc'):
            btc_ema50 = btc_ema50_series.iloc[-1]
        else:
            btc_ema50 = ema21  # fallback
        btc_trend_bull = price > btc_ema50 and price > btc_ema200
        btc_trend_bear = price < (btc_ema200 * 0.98)
        if btc_ema200 == 0:
            btc_trend_bear = False
            btc_trend_bull = False
    # BTC bullish ise short işlemleri engelle, long'a bonus ver
    if btc_trend_bull:
        long_score += 10
        long_reasons.append('BTC bullish trend (EMA50/200 üstü)')
        short_score_penalty = True
    else:
        short_score_penalty = False
    if btc_trend_bear:
        long_reasons.append('BTC düşüş trendi (EMA200 %2 altı)')
        long_score = 0
        pass
    else:
        # ADX + DI+ (Kritik: +25)
        if adx > 25 and di_plus > di_minus:
            long_score += 25
            long_reasons.append(f"ADX+DI+")
        elif di_plus > di_minus * 1.1:
            long_score += 12
            long_reasons.append("DI+>DI-")
        # EMA Dizilimi (Kritik: +25)
        if price > ema9 > ema21 > ema50:
            long_score += 25
            long_reasons.append("Bullish EMA")
        elif price > ema21 and ema9 > ema21:
            long_score += 12
            long_reasons.append("EMA Bullish")
        # Golden Cross (Kritik: +18)
        if prev_ema9 <= prev_ema21 and ema9 > ema21:
            long_score += 18
            long_reasons.append("GOLDEN CROSS")
        # MACD (Kritik: +18)
        if prev_macd <= prev_macd_sig and macd_val > macd_sig:
            long_score += 18
            long_reasons.append("MACD Cross")
        elif macd_val > macd_sig and macd_hist > 0:
            long_score += 10
            long_reasons.append("MACD+")
        # RSI (Yan: +8/+5)
        if rsi < 30:
            long_score += 8
            long_reasons.append(f"RSI({rsi:.0f})")
        elif rsi < 40:
            long_score += 5
            long_reasons.append(f"RSI({rsi:.0f})")
        elif rsi > 50 and rsi < 70:
            long_score += 3
            long_reasons.append(f"RSI({rsi:.0f})")
        # BB (Yan: +6/+3)
        if bb_pct < 0.1:
            long_score += 6
            long_reasons.append(f"BB({bb_pct*100:.0f}%)")
        elif bb_pct < 0.25:
            long_score += 3
            long_reasons.append(f"BB({bb_pct*100:.0f}%)")
        # StochRSI (Yan: +4/+2)
        if stoch_k < 20:
            long_score += 4
            long_reasons.append(f"Stoch({stoch_k:.0f})")
        elif stoch_k < 35:
            long_score += 2
            long_reasons.append(f"Stoch({stoch_k:.0f})")
        # MFI (Yan: +2)
        if mfi < 25:
            long_score += 2
            long_reasons.append(f"MFI({mfi:.0f})")
    
    # ═══════════════════════════════════════════════════════════════
    # SHORT PUANLAMA (Maks 150 puan)
    # BTC bullish ise short puanından ceza düş
    if 'short_score_penalty' in locals() and short_score_penalty:
        short_score -= 10
        short_reasons.append('BTC bullish trend - short cezası')
    # ═══════════════════════════════════════════════════════════════
    short_score = 0
    short_reasons = []
    
    # ADX + DI-
    if adx > 25 and di_minus > di_plus:
        short_score += 25
        short_reasons.append(f"ADX+DI-")
    elif di_minus > di_plus * 1.1:
        short_score += 12
        short_reasons.append("DI->DI+")
    
    # EMA Dizilimi
    if price < ema9 < ema21 < ema50:
        short_score += 25
        short_reasons.append("Bearish EMA")
    elif price < ema21 and ema9 < ema21:
        short_score += 15
        short_reasons.append("EMA Bearish")
    # Death Cross
    if prev_ema9 >= prev_ema21 and ema9 < ema21:
        short_score += 20
        short_reasons.append("DEATH CROSS")
    
    # RSI
    if rsi > 80:
        short_score += 20
        short_reasons.append(f"RSI({rsi:.0f})")
    elif rsi > 70:
        short_score += 15
        short_reasons.append(f"RSI({rsi:.0f})")
    elif rsi > 50 and rsi < 60:
        short_score += 5
        short_reasons.append(f"RSI({rsi:.0f})")
    
    # MACD
    if prev_macd >= prev_macd_sig and macd_val < macd_sig:
        short_score += 25
        short_reasons.append("MACD Cross")
    elif macd_val < macd_sig and macd_hist < 0:
        short_score += 15
        short_reasons.append("MACD-")
    
    # BB
    if bb_pct > 0.95:
        short_score += 20
        short_reasons.append(f"BB({bb_pct*100:.0f}%)")
    elif bb_pct > 0.8:
        short_score += 12
        short_reasons.append(f"BB({bb_pct*100:.0f}%)")
    
    # StochRSI
    if stoch_k > 85:
        short_score += 15
        short_reasons.append(f"Stoch({stoch_k:.0f})")
    elif stoch_k > 70:
        short_score += 8
        short_reasons.append(f"Stoch({stoch_k:.0f})")
    
    # MFI
    if mfi > 80:
        short_score += 10
        short_reasons.append(f"MFI({mfi:.0f})")
    
    # ═══════════════════════════════════════════════════════════════
    # YÖN BELİRLE
    # ═══════════════════════════════════════════════════════════════
    direction = None
    score = 0
    reasons = []
    
    # Trendle ters yöndeki işlemleri tamamen engelle
    direction = None
    score = 0
    reasons = []
    if btc_trend_bull:
        # Sadece long açılır
        if long_score >= short_score + MIN_SCORE_DIFF and long_score >= SCORE_THRESHOLD_LONG:
            direction = 'LONG'
            score = long_score
            reasons = long_reasons
    elif btc_trend_bear:
        # Sadece short açılır
        if short_score >= long_score + MIN_SCORE_DIFF and short_score >= SCORE_THRESHOLD_SHORT:
            direction = 'SHORT'
            score = short_score
            reasons = short_reasons
    else:
        # Nötr trendde klasik mantık
        if long_score >= short_score + MIN_SCORE_DIFF and long_score >= SCORE_THRESHOLD_LONG:
            direction = 'LONG'
            score = long_score
            reasons = long_reasons
        elif short_score >= long_score + MIN_SCORE_DIFF and short_score >= SCORE_THRESHOLD_SHORT:
            direction = 'SHORT'
            score = short_score
            reasons = short_reasons
    
    return direction, score, reasons, long_score, short_score

# ==========================================
# 🔄 BACKTEST FONKSİYONU
# ==========================================
def backtest_coin(symbol, df):
    """Tek coin için çift yönlü backtest"""
    trades = []
    in_position = False
    position_direction = None
    entry_price = 0
    entry_time = None
    stop_loss = 0
    original_stop = 0
    tp1 = tp2 = tp3 = 0
    tp1_hit = tp2_hit = False
    position_remaining = 1.0
    last_exit_candle = -999
    trade_count = 0
    leverage = 5
    # --- ZARARDA KAPANAN COINLER İÇİN 24 SAAT TIMEOUT ---
    last_loss_exit_time = None
    
    # Volatilite kontrolü
    if len(df) > 50:
        first_atr = df.iloc[50]['atr'] if pd.notna(df.iloc[50]['atr']) else 0
        first_price = df.iloc[50]['close']
        atr_pct = (first_atr / first_price) * 100 if first_price > 0 else 0
        
        if atr_pct > MAX_ATR_PERCENT or atr_pct < MIN_ATR_PERCENT:
            return []
    
    for i in range(51, len(df)):
        row = df.iloc[i]
        prev_row = df.iloc[i-1]
        current_price = float(row['close'])
        current_time = row['timestamp']
        high = float(row['high'])
        low = float(row['low'])
        atr = float(row['atr']) if pd.notna(row['atr']) else current_price * 0.02

        # --- ZARARDA KAPANAN COIN TIMEOUT KONTROLÜ ---
        if last_loss_exit_time is not None:
            if (current_time - last_loss_exit_time).total_seconds() < 24*3600:
                continue  # 24 saat geçmeden tekrar işlem açma

        if in_position:
            # Trailing Stop
            if TRAILING_STOP:
                if position_direction == 'SHORT':
                    if tp1_hit and not tp2_hit:
                        new_stop = entry_price + (original_stop - entry_price) * 0.5
                        if stop_loss > new_stop:
                            stop_loss = new_stop
                    if tp2_hit:
                        if stop_loss > entry_price:
                            stop_loss = entry_price
                else:  # LONG
                    if tp1_hit and not tp2_hit:
                        new_stop = entry_price - (entry_price - original_stop) * 0.5
                        if stop_loss < new_stop:
                            stop_loss = new_stop
                    if tp2_hit:
                        if stop_loss < entry_price:
                            stop_loss = entry_price
            
            # Stop Loss kontrol
            sl_triggered = False
            if position_direction == 'SHORT' and high >= stop_loss:
                sl_triggered = True
                exit_price = stop_loss
            elif position_direction == 'LONG' and low <= stop_loss:
                sl_triggered = True
                exit_price = stop_loss
            
            if sl_triggered:
                if position_direction == 'SHORT':
                    pnl_pct = ((entry_price - exit_price) / entry_price) * 100 * position_remaining * leverage
                else:
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100 * position_remaining * leverage

                result_text = 'STOP LOSS'
                if tp1_hit: result_text = 'TRAILING (TP1+)'
                if tp2_hit: result_text = 'TRAILING (TP2+)'

                trades.append({
                    'symbol': symbol, 'direction': position_direction,
                    'entry_time': entry_time, 'exit_time': current_time,
                    'entry_price': entry_price, 'exit_price': exit_price,
                    'pnl_pct': pnl_pct, 'result': result_text, 'leverage': leverage
                })
                # --- ZARARDA KAPANIŞTA 24 SAAT TIMEOUT AKTİFLE ---
                if pnl_pct < 0:
                    last_loss_exit_time = current_time
                in_position = False
                last_exit_candle = i
                position_remaining = 1.0
                continue
            
            # Partial TP
            if PARTIAL_TP:
                if position_direction == 'SHORT':
                    if not tp1_hit and low <= tp1:
                        tp1_hit = True
                        partial_pnl = ((entry_price - tp1) / entry_price) * 100 * TP1_CLOSE_PCT * leverage
                        trades.append({
                            'symbol': symbol, 'direction': position_direction,
                            'entry_time': entry_time, 'exit_time': current_time,
                            'entry_price': entry_price, 'exit_price': tp1,
                            'pnl_pct': partial_pnl, 'result': f'TP1', 'leverage': leverage
                        })
                        position_remaining = 1.0 - TP1_CLOSE_PCT
                    
                    if tp1_hit and not tp2_hit and low <= tp2:
                        tp2_hit = True
                        partial_pnl = ((entry_price - tp2) / entry_price) * 100 * TP2_CLOSE_PCT * leverage
                        trades.append({
                            'symbol': symbol, 'direction': position_direction,
                            'entry_time': entry_time, 'exit_time': current_time,
                            'entry_price': entry_price, 'exit_price': tp2,
                            'pnl_pct': partial_pnl, 'result': f'TP2', 'leverage': leverage
                        })
                        position_remaining = TP3_CLOSE_PCT
                    
                    if tp2_hit and low <= tp3:
                        partial_pnl = ((entry_price - tp3) / entry_price) * 100 * TP3_CLOSE_PCT * leverage
                        trades.append({
                            'symbol': symbol, 'direction': position_direction,
                            'entry_time': entry_time, 'exit_time': current_time,
                            'entry_price': entry_price, 'exit_price': tp3,
                            'pnl_pct': partial_pnl, 'result': f'TP3', 'leverage': leverage
                        })
                        in_position = False
                        last_exit_candle = i
                        position_remaining = 1.0
                        continue
                
                else:  # LONG
                    if not tp1_hit and high >= tp1:
                        tp1_hit = True
                        partial_pnl = ((tp1 - entry_price) / entry_price) * 100 * TP1_CLOSE_PCT * leverage
                        trades.append({
                            'symbol': symbol, 'direction': position_direction,
                            'entry_time': entry_time, 'exit_time': current_time,
                            'entry_price': entry_price, 'exit_price': tp1,
                            'pnl_pct': partial_pnl, 'result': f'TP1', 'leverage': leverage
                        })
                        position_remaining = 1.0 - TP1_CLOSE_PCT
                    
                    if tp1_hit and not tp2_hit and high >= tp2:
                        tp2_hit = True
                        partial_pnl = ((tp2 - entry_price) / entry_price) * 100 * TP2_CLOSE_PCT * leverage
                        trades.append({
                            'symbol': symbol, 'direction': position_direction,
                            'entry_time': entry_time, 'exit_time': current_time,
                            'entry_price': entry_price, 'exit_price': tp2,
                            'pnl_pct': partial_pnl, 'result': f'TP2', 'leverage': leverage
                        })
                        position_remaining = TP3_CLOSE_PCT
                    
                    if tp2_hit and high >= tp3:
                        partial_pnl = ((tp3 - entry_price) / entry_price) * 100 * TP3_CLOSE_PCT * leverage
                        trades.append({
                            'symbol': symbol, 'direction': position_direction,
                            'entry_time': entry_time, 'exit_time': current_time,
                            'entry_price': entry_price, 'exit_price': tp3,
                            'pnl_pct': partial_pnl, 'result': f'TP3', 'leverage': leverage
                        })
                        in_position = False
                        last_exit_candle = i
                        position_remaining = 1.0
                        continue
        else:
            # Yeni pozisyon aç
            if i - last_exit_candle < COOLDOWN_CANDLES:
                continue
            if trade_count >= MAX_TRADES_PER_COIN:
                continue
            
            result = calculate_dual_score(row, prev_row)
            direction, score, reasons, long_sc, short_sc = result
            
            if direction is None:
                continue
            
            # Win rate hesapla
            win_rate = 60
            if score >= 90: win_rate += 15
            elif score >= 75: win_rate += 10
            elif score >= 60: win_rate += 5
            
            if len(reasons) >= 6: win_rate += 15
            elif len(reasons) >= 5: win_rate += 10
            elif len(reasons) >= 4: win_rate += 5
            
            # Güçlü trend bonusu
            if abs(long_sc - short_sc) >= 30:
                win_rate += 5
            
            # Yön bazlı eşik kontrolü
            if ((direction == 'LONG' and score >= SCORE_THRESHOLD_LONG) or
                (direction == 'SHORT' and score >= SCORE_THRESHOLD_SHORT)) and win_rate >= MIN_WIN_RATE:
                in_position = True
                position_direction = direction
                entry_price = current_price
                entry_time = current_time
                trade_count += 1
                leverage = get_leverage(score, win_rate)
                
                risk = atr * SL_ATR_MULT
                
                if direction == 'SHORT':
                    original_stop = entry_price + risk
                    stop_loss = original_stop
                    tp1 = entry_price - (risk * TP1_RR)
                    tp2 = entry_price - (risk * TP2_RR)
                    tp3 = entry_price - (risk * TP3_RR)
                else:  # LONG
                    original_stop = entry_price - risk
                    stop_loss = original_stop
                    tp1 = entry_price + (risk * TP1_RR)
                    tp2 = entry_price + (risk * TP2_RR)
                    tp3 = entry_price + (risk * TP3_RR)
                
                tp1_hit = tp2_hit = False
                position_remaining = 1.0
                
                # Signal bilgisini kaydet
                signal_info = {
                    'symbol': symbol,
                    'direction': direction,
                    'entry_time': entry_time,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'tp1': tp1,
                    'tp2': tp2,
                    'tp3': tp3,
                    'score': score,
                    'win_rate': win_rate,
                    'leverage': leverage,
                    'reasons': ' | '.join(reasons)
                }
                if not hasattr(backtest_coin, 'signals'):
                    backtest_coin.signals = []
                backtest_coin.signals.append(signal_info)
    
    # Açık pozisyonu kapat
    if in_position:
        last_row = df.iloc[-1]
        exit_price = float(last_row['close'])
        if position_direction == 'SHORT':
            pnl_pct = ((entry_price - exit_price) / entry_price) * 100 * position_remaining * leverage
        else:
            pnl_pct = ((exit_price - entry_price) / entry_price) * 100 * position_remaining * leverage
        
        trades.append({
            'symbol': symbol, 'direction': position_direction,
            'entry_time': entry_time, 'exit_time': last_row['timestamp'],
            'entry_price': entry_price, 'exit_price': exit_price,
            'pnl_pct': pnl_pct, 'result': 'CLOSE (End)', 'leverage': leverage
        })
    
    return trades

# ==========================================
# 🚀 ANA FONKSİYON
# ==========================================
def run_backtest():
    print("=" * 70)
    print("🔄 SWING BACKTEST - ÇİFT YÖNLÜ (LONG + SHORT)")
    print("=" * 70)
    print(f"📅 Tarih Aralığı: {BACKTEST_START.strftime('%Y-%m-%d')} - {BACKTEST_END.strftime('%Y-%m-%d')}")
    print(f"💰 Başlangıç: ${INITIAL_BALANCE}")
    print(f"📊 Pozisyon: %{POSITION_SIZE_PCT}")
    print(f"⚡ Kaldıraç: 5x-10x (dinamik)")
    print("=" * 70)
    
    # CSV dosyalarını bul
    csv_files = [f for f in os.listdir(DATA_FOLDER) if f.endswith('.csv') and not f.startswith('_')]
    
    if SINGLE_COIN:
        safe_symbol = SINGLE_COIN.replace('/', '_').replace(':', '_')
        csv_files = [f for f in csv_files if safe_symbol in f]
    
    print(f"\n📁 {len(csv_files)} coin bulundu.\n")
    
    all_trades = []
    coin_results = []
    
    for csv_file in csv_files:
        symbol = csv_file.replace('_USDT_USDT.csv', '/USDT:USDT').replace('_', '/')
        if symbol.count('/') > 1:
            symbol = symbol.split('/')[0] + '/USDT:USDT'
        
        filepath = os.path.join(DATA_FOLDER, csv_file)
        
        try:
            df = pd.read_csv(filepath)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Tarih filtresi
            df = df[(df['timestamp'] >= BACKTEST_START) & (df['timestamp'] <= BACKTEST_END)]
            
            if len(df) < 100:
                continue
            
            df = calculate_indicators(df)
            trades = backtest_coin(symbol, df)
            
            if trades:
                all_trades.extend(trades)
                
                total_pnl = sum(t['pnl_pct'] for t in trades)
                wins = [t for t in trades if t['pnl_pct'] > 0]
                losses = [t for t in trades if t['pnl_pct'] < 0]
                long_trades = [t for t in trades if t['direction'] == 'LONG']
                short_trades = [t for t in trades if t['direction'] == 'SHORT']
                
                coin_results.append({
                    'symbol': symbol.split('/')[0],
                    'trades': len(trades),
                    'win_rate': len(wins) / len(trades) * 100 if trades else 0,
                    'pnl': total_pnl,
                    'long': len(long_trades),
                    'short': len(short_trades)
                })
                
                print(f"  ✅ {symbol.split('/')[0]}: {len(trades)} işlem | 🟢L:{len(long_trades)} 🔴S:{len(short_trades)} | PnL: {total_pnl:+.1f}%")
        
        except Exception as e:
            print(f"  ❌ {symbol}: {e}")
    
    # Sadece işlem detaylarını yazdır
    print("\n" + "=" * 70)
    print("📋 1 AY ÖNCEKİ 1 HAFTALIK TÜM İŞLEM GİRİŞ/ÇIKIŞLARI")
    print("=" * 70)
    if all_trades:
        for t in sorted(all_trades, key=lambda x: x['entry_time']):
            dir_emoji = "🟢" if t['direction'] == 'LONG' else "🔴"
            pnl_emoji = "✅" if t['pnl_pct'] > 0 else "❌"
            print(f"{dir_emoji} {t['symbol'].split('/')[0]:8} | {t['direction']:5} | {t['entry_time'].strftime('%Y-%m-%d %H:%M')} | Entry: ${t['entry_price']:.4f} | Exit: ${t['exit_price']:.4f} | {t['leverage']}x | {pnl_emoji} {t['pnl_pct']:+.1f}% | {t['result']}")

        total_pnl = sum(t['pnl_pct'] for t in all_trades)
        wins = [t for t in all_trades if t['pnl_pct'] > 0]
        losses = [t for t in all_trades if t['pnl_pct'] < 0]
        long_trades = [t for t in all_trades if t['direction'] == 'LONG']
        short_trades = [t for t in all_trades if t['direction'] == 'SHORT']
        long_pnl = sum(t['pnl_pct'] for t in long_trades)
        short_pnl = sum(t['pnl_pct'] for t in short_trades)
        win_rate = len(wins) / len(all_trades) * 100 if all_trades else 0
        avg_win = sum(t['pnl_pct'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl_pct'] for t in losses) / len(losses) if losses else 0
        final_balance = INITIAL_BALANCE * (1 + (total_pnl * POSITION_SIZE_PCT / 100) / 100)
        returns = [t['pnl_pct'] * POSITION_SIZE_PCT / 100 for t in all_trades]
        if len(returns) > 1:
            import numpy as np
            mean_r = np.mean(returns)
            std_r = np.std(returns)
            sharpe = (mean_r / std_r * (len(returns) ** 0.5)) if std_r > 0 else 0
        else:
            sharpe = 0

        print(f"\n📈 Toplam PnL: {total_pnl:+.2f}%")
        print(f"💵 Başlangıç: ${INITIAL_BALANCE:.2f}")
        print(f"💵 Final Bakiye: ${final_balance:.2f}")
        print(f"✅ Başarılı İşlem: {len(wins)}")
        print(f"❌ Başarısız İşlem: {len(losses)}")
        print(f"📊 Win Rate: {win_rate:.2f}%")
        print(f"📈 Avg Win: {avg_win:+.2f}% | 📉 Avg Loss: {avg_loss:.2f}%")
        print(f"🟢 Toplam LONG: {len(long_trades)} | Karı: {long_pnl:+.2f}%")
        print(f"🔴 Toplam SHORT: {len(short_trades)} | Karı: {short_pnl:+.2f}%")
        print(f"📈 Sharpe Ratio: {sharpe:.2f}")
    else:
        print("❌ Hiç işlem bulunamadı!")
    print("\n" + "=" * 70)
    return all_trades, backtest_coin.signals if hasattr(backtest_coin, 'signals') else []

if __name__ == "__main__":
    trades, signals = run_backtest()
