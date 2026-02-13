"""
🧪 Backtest Engine v3.0 — v2.2.0 Canlı Motor Uyumlu
Bollinger TP + ADX Fix + BB R:R Guard + Fee PnL + Time Exit + Kırmızı Mum
"""
import pandas as pd
import pandas_ta as ta
import numpy as np
import os
import random
import warnings
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count

warnings.filterwarnings('ignore')
pd.set_option('future.no_silent_downcasting', True)

# ==========================================
# ⚙️ BACKTEST AYARLARI (v2.2.0 Config ile Senkron)
# ==========================================
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_FOLDER = os.path.join(_PROJECT_ROOT, "data", "backtest_data")
RESULTS_DIR = os.path.join(_PROJECT_ROOT, "data")

INITIAL_BALANCE = 1000
POSITION_SIZE_PCT = 10
LEVERAGE = 5
MAKER_FEE = 0.0002
TAKER_FEE = 0.0005
STRATEGY_SIDE = 'SHORT'

# Tarih aralığı
BACKTEST_START = datetime(2025, 11, 1)
BACKTEST_END = datetime(2026, 2, 13, 23, 59, 59)

# Strateji filtreleri (config.py ile uyumlu)
SCORE_THRESHOLD = 80
MIN_REASONS = 4
COOLDOWN_CANDLES = 5
MAX_ATR_PERCENT = 4.5
MIN_ATR_PERCENT = 0.5
HARD_STOP_LOSS_PCT = 3.5

# TP/SL (ATR bazlı fallback + Bollinger dinamik)
SL_ATR_MULT = 2.0
TP1_RR = 1.3
TP2_RR = 2.4
TP3_RR = 4.0
TP1_CLOSE_PCT = 0.40
TP2_CLOSE_PCT = 0.30
TP3_CLOSE_PCT = 0.30

# Decay/Squeeze
SIGNAL_DECAY_EXIT = True
SIGNAL_DECAY_GRACE_CANDLES = 4
SQUEEZE_RATIO = 1.25
DECAY_RATIO = 0.40

# Time Exit
TIME_EXIT_CANDLES = 192  # 48 saat = 192 x 15m

# Blacklist
COIN_BLACKLIST_AFTER = 3
COIN_BLACKLIST_CANDLES = 32
MAX_TRADES_PER_COIN = 30

# Monte Carlo
RUN_MONTE_CARLO = True
MONTE_CARLO_SIMULATIONS = 5000

# Output
SAVE_CSV = True
SHOW_TRADE_DETAILS = True

# ==========================================
# 📊 İNDİKATÖR HESAPLAMA (strategy.py ile birebir)
# ==========================================
def calculate_indicators(df):
    df = df.copy()
    df['ema9'] = ta.ema(df['close'], length=9)
    df['ema21'] = ta.ema(df['close'], length=21)
    df['sma50'] = ta.sma(df['close'], length=50)
    df['rsi'] = ta.rsi(df['close'], length=14)

    macd = ta.macd(df['close'])
    if macd is not None:
        df['macd'] = macd.iloc[:, 0]
        df['macd_signal'] = macd.iloc[:, 2]
    else:
        df['macd'] = df['macd_signal'] = 0

    bb = ta.bbands(df['close'], length=20, std=2)
    if bb is not None:
        df['bb_lower'] = bb.iloc[:, 0]
        df['bb_middle'] = bb.iloc[:, 1]
        df['bb_upper'] = bb.iloc[:, 2]
        df['bb_pct'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    else:
        df['bb_lower'] = df['bb_middle'] = df['bb_upper'] = df['close']
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

    # Hacim analizi
    df['vol_avg20'] = df['volume'].shift(1).rolling(window=20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_avg20']

    df = df.ffill().fillna(0).infer_objects(copy=False)
    return df


# ==========================================
# 🧠 SKORLAMA (strategy.py score_short ile birebir)
# ==========================================
def score_short_row(row, prev_row):
    """Tek satır için SHORT skor — canlı motorla birebir"""
    score = 0
    reasons = []

    adx = row['adx']
    di_plus, di_minus = row['di_plus'], row['di_minus']
    rsi = row['rsi']
    macd_val, macd_sig = row['macd'], row['macd_signal']
    bb_pct = row['bb_pct']
    stoch_k = row['stoch_k']
    mfi = row['mfi']
    ema9, ema21, sma50 = row['ema9'], row['ema21'], row['sma50']

    # ADX + DI (Tek blok — çift sayım yok)
    if adx < 25:
        score += 20
        reasons.append(f"ADX({adx:.0f})Low")
        if di_minus > di_plus:
            score += 5
            reasons.append("DI->DI+")
    elif adx <= 50:
        if di_minus > di_plus:
            score += 10
            reasons.append(f"ADX({adx:.0f})+DI-")
    else:
        score -= 10
        reasons.append("ADX-High")

    # SMA50 Overextension
    dist = (row['close'] - sma50) / sma50 * 100 if sma50 > 0 else 0
    if dist > 4:
        score += 25
        reasons.append(f"SMA50_OE({dist:.1f}%)")
    elif dist > 2:
        score += 10
        reasons.append(f"SMA50_OE({dist:.1f}%)")

    # RSI
    if rsi > 80:
        score += 30
        reasons.append(f"RSI({rsi:.0f})")
    elif rsi > 65:
        score += 20
        reasons.append(f"RSI({rsi:.0f})")
    elif rsi > 60:
        reasons.append(f"RSI({rsi:.0f})")

    # MACD
    if macd_val < macd_sig:
        score += 5
        reasons.append("MACD-")

    # Bollinger
    if bb_pct > 0.95:
        score += 25
        reasons.append(f"BB({bb_pct*100:.0f}%)")
    elif bb_pct > 0.8:
        score += 15
        reasons.append(f"BB({bb_pct*100:.0f}%)")

    # StochRSI
    if stoch_k > 80:
        score += 20
        reasons.append(f"Stoch({stoch_k:.0f})")

    # MFI
    if mfi > 80:
        score += 15
        reasons.append(f"MFI({mfi:.0f})")

    # EMA Bearish
    if ema9 < ema21 < sma50:
        reasons.append("EMA Bearish")

    return score, len(reasons), reasons


# ==========================================
# 🔄 BACKTEST MOTORU (v2.2.0 Uyumlu)
# ==========================================
def backtest_coin(symbol, df):
    """Tek coin backtest — Canlı motorla birebir uyumlu mantık"""
    trades = []
    in_position = False
    entry_price = 0.0
    entry_time = None
    entry_score = 0
    entry_candle = 0
    stop_loss = 0.0
    tp1 = tp2 = tp3 = 0.0
    tp1_hit = tp2_hit = False
    position_remaining = 1.0
    last_exit_candle = -999
    trade_count = 0
    consecutive_losses = 0
    coin_blacklist_until = 0
    entry_reasons = []

    rows = df.to_dict('records')
    n = len(rows)

    for i in range(50, n):
        row = rows[i]
        prev = rows[i - 1]
        price = row['close']
        high = row['high']
        low = row['low']
        atr = row['atr']

        if in_position:
            # ── TIME EXIT ──
            candles_in = i - entry_candle
            if candles_in > TIME_EXIT_CANDLES:
                pnl = ((entry_price - price) / entry_price) * 100 * position_remaining
                fee_pct = TAKER_FEE * 100 * 2
                pnl -= fee_pct * position_remaining
                trades.append({
                    'symbol': symbol, 'entry_time': entry_time,
                    'exit_time': row['timestamp'],
                    'entry_price': entry_price, 'exit_price': price,
                    'pnl_pct': pnl, 'result': 'TIME_EXIT',
                    'reasons': entry_reasons, 'entry_score': entry_score
                })
                in_position = False
                last_exit_candle = i
                position_remaining = 1.0
                continue

            # ── STOP LOSS ──
            is_stopped = high >= stop_loss

            if is_stopped:
                pnl = ((entry_price - stop_loss) / entry_price) * 100 * position_remaining
                fee_pct = TAKER_FEE * 100 * 2
                pnl -= fee_pct * position_remaining

                if abs(pnl) > HARD_STOP_LOSS_PCT:
                    pnl = -HARD_STOP_LOSS_PCT

                res = 'STOP LOSS'
                if tp1_hit: res = 'TRAILING (TP1+)'
                if tp2_hit: res = 'TRAILING (TP2+)'

                if pnl < 0:
                    consecutive_losses += 1
                else:
                    consecutive_losses = 0

                if consecutive_losses >= COIN_BLACKLIST_AFTER:
                    coin_blacklist_until = i + COIN_BLACKLIST_CANDLES
                    consecutive_losses = 0

                trades.append({
                    'symbol': symbol, 'entry_time': entry_time,
                    'exit_time': row['timestamp'],
                    'entry_price': entry_price, 'exit_price': stop_loss,
                    'pnl_pct': pnl, 'result': res,
                    'reasons': entry_reasons, 'entry_score': entry_score
                })
                in_position = False
                last_exit_candle = i
                position_remaining = 1.0
                continue

            # ── DINAMIK BOLLINGER TP ──
            bb_mid = row['bb_middle']
            bb_low_band = row['bb_lower']

            # TP1: Bollinger Orta Bandı
            if not tp1_hit and price <= bb_mid:
                tp1_hit = True
                pnl = ((entry_price - bb_mid) / entry_price) * 100 * TP1_CLOSE_PCT
                fee_pct = TAKER_FEE * 100 * 2
                pnl -= fee_pct * TP1_CLOSE_PCT
                trades.append({
                    'symbol': symbol, 'entry_time': entry_time,
                    'exit_time': row['timestamp'],
                    'entry_price': entry_price, 'exit_price': bb_mid,
                    'pnl_pct': pnl, 'result': 'TP1 (BB Mid)',
                    'reasons': entry_reasons, 'entry_score': entry_score
                })
                position_remaining = 1.0 - TP1_CLOSE_PCT
                # Stopu girişe çek (BE)
                stop_loss = entry_price
                consecutive_losses = 0

            # TP2: Bollinger Alt Bandı
            elif tp1_hit and not tp2_hit and price <= bb_low_band:
                tp2_hit = True
                pnl = ((entry_price - bb_low_band) / entry_price) * 100 * TP2_CLOSE_PCT
                fee_pct = TAKER_FEE * 100 * 2
                pnl -= fee_pct * TP2_CLOSE_PCT
                trades.append({
                    'symbol': symbol, 'entry_time': entry_time,
                    'exit_time': row['timestamp'],
                    'entry_price': entry_price, 'exit_price': bb_low_band,
                    'pnl_pct': pnl, 'result': 'TP2 (BB Low)',
                    'reasons': entry_reasons, 'entry_score': entry_score
                })
                position_remaining = TP3_CLOSE_PCT
                # SL'i daha da aşağı çek
                stop_loss = entry_price - (entry_price - bb_mid) * 0.5

            # TP3: ATR bazlı sabit hedef (fallback)
            elif tp2_hit and low <= tp3:
                pnl = ((entry_price - tp3) / entry_price) * 100 * TP3_CLOSE_PCT
                fee_pct = TAKER_FEE * 100 * 2
                pnl -= fee_pct * TP3_CLOSE_PCT
                trades.append({
                    'symbol': symbol, 'entry_time': entry_time,
                    'exit_time': row['timestamp'],
                    'entry_price': entry_price, 'exit_price': tp3,
                    'pnl_pct': pnl, 'result': 'TP3 (ATR)',
                    'reasons': entry_reasons, 'entry_score': entry_score
                })
                in_position = False
                last_exit_candle = i
                position_remaining = 1.0
                continue

            # ── SIGNAL DECAY / SQUEEZE ──
            if SIGNAL_DECAY_EXIT and candles_in >= SIGNAL_DECAY_GRACE_CANDLES:
                cur_score, _, _ = score_short_row(row, prev)
                if entry_score > 0:
                    ratio = cur_score / entry_score
                    cur_pnl = ((entry_price - price) / entry_price) * 100

                    # Squeeze: Skor artıyor + zarar
                    if ratio > SQUEEZE_RATIO and cur_pnl < -0.5:
                        pnl = cur_pnl * position_remaining
                        fee_pct = TAKER_FEE * 100 * 2
                        pnl -= fee_pct * position_remaining
                        trades.append({
                            'symbol': symbol, 'entry_time': entry_time,
                            'exit_time': row['timestamp'],
                            'entry_price': entry_price, 'exit_price': price,
                            'pnl_pct': pnl, 'result': 'SQUEEZE_EXIT',
                            'reasons': entry_reasons, 'entry_score': entry_score
                        })
                        in_position = False
                        last_exit_candle = i
                        position_remaining = 1.0
                        continue

                    # Decay: Skor düşüyor + zarar
                    if ratio < DECAY_RATIO and cur_pnl < 0.2:
                        pnl = cur_pnl * position_remaining
                        fee_pct = TAKER_FEE * 100 * 2
                        pnl -= fee_pct * position_remaining
                        trades.append({
                            'symbol': symbol, 'entry_time': entry_time,
                            'exit_time': row['timestamp'],
                            'entry_price': entry_price, 'exit_price': price,
                            'pnl_pct': pnl, 'result': 'DECAY_EXIT',
                            'reasons': entry_reasons, 'entry_score': entry_score
                        })
                        in_position = False
                        last_exit_candle = i
                        position_remaining = 1.0
                        continue

        else:
            # ── GİRİŞ MANTIĞI ──
            if i - last_exit_candle < COOLDOWN_CANDLES: continue
            if trade_count >= MAX_TRADES_PER_COIN: continue
            if i < coin_blacklist_until: continue

            score, num_reasons, reasons = score_short_row(row, prev)

            # Volatilite filtresi
            atr_pct = (atr / price) * 100 if price > 0 else 0
            if atr_pct > MAX_ATR_PERCENT or atr_pct < MIN_ATR_PERCENT:
                continue

            # Momentum filtresi (RSI 80+ ve hala artıyorsa girme)
            if row['rsi'] >= 80 and row['rsi'] >= prev['rsi']:
                continue

            # Hacim patlaması filtresi
            if row['vol_ratio'] > 3.5:
                continue

            # God Candle filtresi
            candle_body = abs(row['close'] - row['open'])
            if candle_body > (atr * 3):
                continue
            candle_change = (row['close'] - row['open']) / row['open'] * 100 if row['open'] > 0 else 0
            wick_size = (row['high'] - row['close']) / (row['high'] - row['low']) if (row['high'] - row['low']) > 0 else 0
            if candle_change > 3.0 and wick_size < 0.15:
                continue

            # Kırmızı mum doğrulaması
            last_is_red = row['close'] < row['open']
            if not last_is_red:
                continue

            # Kırmızı mum hacim bonusu
            prev_is_green = prev['close'] > prev['open']
            if last_is_red and prev_is_green:
                prev_vol = prev['volume'] if prev['volume'] > 0 else 1
                vol_confirm = row['volume'] / prev_vol
                if vol_confirm >= 0.7:
                    score += 10
                    reasons.append("RedConfirm")
                    num_reasons += 1

            # SMA50 üzerinde cezalı eşik
            sma50 = row['sma50']
            if price > sma50:
                threshold = SCORE_THRESHOLD + 15
            else:
                threshold = SCORE_THRESHOLD

            if score < threshold or num_reasons < MIN_REASONS:
                continue

            # BB R:R Guard
            risk = atr * SL_ATR_MULT
            bb_mid_dist = price - row['bb_middle']
            if bb_mid_dist < risk * 0.5:
                continue

            # ENTRY!
            in_position = True
            entry_price = price
            entry_time = row['timestamp']
            entry_score = score
            entry_candle = i
            entry_reasons = reasons
            trade_count += 1

            stop_loss = price + risk
            tp1 = price - (risk * TP1_RR)  # fallback
            tp2 = price - (risk * TP2_RR)  # fallback
            tp3 = price - (risk * TP3_RR)
            tp1_hit = tp2_hit = False
            position_remaining = 1.0

    # Dönem sonu açık pozisyon
    if in_position:
        exit_p = rows[-1]['close']
        pnl = ((entry_price - exit_p) / entry_price) * 100 * position_remaining
        fee_pct = TAKER_FEE * 100 * 2
        pnl -= fee_pct * position_remaining
        trades.append({
            'symbol': symbol, 'entry_time': entry_time,
            'exit_time': rows[-1]['timestamp'],
            'entry_price': entry_price, 'exit_price': exit_p,
            'pnl_pct': pnl, 'result': 'DÖNEM SONU',
            'reasons': entry_reasons, 'entry_score': entry_score
        })

    return trades


# ==========================================
# 🏭 PARALEL WORKER
# ==========================================
def _process_coin(args):
    symbol, filename = args
    if not os.path.exists(filename):
        return symbol, []
    try:
        df = pd.read_csv(filename)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        mask = (df['timestamp'] >= BACKTEST_START) & (df['timestamp'] <= BACKTEST_END)
        df = df.loc[mask].copy()
        if len(df) < 50:
            return symbol, []
        df = calculate_indicators(df)
        trades = backtest_coin(symbol, df)
        if trades:
            print(f"  ✅ {symbol}: {len(trades)} işlem")
        return symbol, trades
    except Exception as e:
        print(f"  ❌ {symbol}: {e}")
        return symbol, []


# ==========================================
# 📊 PORTFÖY SİMÜLATÖRÜ
# ==========================================
def simulate_portfolio(all_trades):
    """Kronolojik portföy simülasyonu"""
    from collections import defaultdict

    pos_trades = defaultdict(list)
    for t in all_trades:
        pos_id = f"{t['symbol']}_{t['entry_time']}"
        pos_trades[pos_id].append(t)

    events = []
    for pos_id, trades in pos_trades.items():
        trades.sort(key=lambda x: str(x['exit_time']))
        events.append({'time': trades[0]['entry_time'], 'type': 'OPEN', 'pos_id': pos_id})
        for t in trades:
            events.append({'time': t['exit_time'], 'type': 'CLOSE', 'pos_id': pos_id, 'trade': t})

    events.sort(key=lambda e: (str(e['time']), 0 if e['type'] == 'CLOSE' else 1))

    available = INITIAL_BALANCE
    active = {}
    skipped = set()
    peak = INITIAL_BALANCE
    max_dd = 0

    for ev in events:
        if ev['type'] == 'OPEN':
            pid = ev['pos_id']
            margin = available * (POSITION_SIZE_PCT / 100)
            if margin < 1:
                skipped.add(pid)
                continue
            available -= margin
            active[pid] = {'margin': margin, 'remaining': 1.0}

        elif ev['type'] == 'CLOSE':
            pid = ev['pos_id']
            if pid in skipped or pid not in active:
                continue
            trade = ev['trade']
            pos = active[pid]

            # Kapatılan oran
            if 'TP1' in trade['result']:
                frac = TP1_CLOSE_PCT
            elif 'TP2' in trade['result']:
                frac = TP2_CLOSE_PCT
            elif 'TP3' in trade['result']:
                frac = TP3_CLOSE_PCT
            else:
                frac = pos['remaining']

            freed_margin = pos['margin'] * frac
            raw_pnl = trade['pnl_pct'] / frac if frac > 0 else 0
            profit = freed_margin * LEVERAGE * (raw_pnl / 100)
            fee = freed_margin * LEVERAGE * (MAKER_FEE + TAKER_FEE)
            net = profit - fee
            returned = max(freed_margin + net, 0)
            available += returned
            pos['remaining'] -= frac

            total_locked = sum(p['margin'] * p['remaining'] for p in active.values())
            total_val = available + total_locked
            if total_val > peak:
                peak = total_val
            dd = (peak - total_val) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

            if pos['remaining'] <= 0.01:
                del active[pid]

    final = available + sum(p['margin'] * p['remaining'] for p in active.values())
    return final, max_dd, len(skipped)


# ==========================================
# 🎲 MONTE CARLO
# ==========================================
def run_monte_carlo(all_trades):
    if not all_trades:
        return
    returns = [t['pnl_pct'] * LEVERAGE for t in all_trades]
    finals = []
    drawdowns = []
    ruined = 0

    for _ in range(MONTE_CARLO_SIMULATIONS):
        shuffled = random.choices(returns, k=len(returns))
        bal = INITIAL_BALANCE
        pk = INITIAL_BALANCE
        mdd = 0
        for pnl in shuffled:
            pos = bal * (POSITION_SIZE_PCT / 100)
            profit = pos * (pnl / 100)
            fee = pos * LEVERAGE * (MAKER_FEE + TAKER_FEE)
            bal += profit - fee
            if bal <= 0:
                bal = 0
                ruined += 1
                break
            if bal > pk:
                pk = bal
            dd = (pk - bal) / pk * 100
            if dd > mdd:
                mdd = dd
        finals.append(bal)
        drawdowns.append(mdd)

    finals = np.array(finals)
    drawdowns = np.array(drawdowns)

    print(f"\n{'='*60}")
    print(f"🎲 MONTE CARLO ANALİZİ ({MONTE_CARLO_SIMULATIONS} Simülasyon)")
    print(f"{'='*60}")
    print(f"📈 Ortalama Final : ${np.mean(finals):.2f}")
    print(f"📊 %50 Medyan     : ${np.median(finals):.2f}")
    print(f"🛡️ En Kötü (%5)   : ${np.percentile(finals, 5):.2f}")
    print(f"🚀 En İyi (%95)   : ${np.percentile(finals, 95):.2f}")
    print(f"📉 Ort. Max DD    : %{np.mean(drawdowns):.1f}")
    print(f"💀 İflas Riski     : %{ruined/MONTE_CARLO_SIMULATIONS*100:.2f}")


# ==========================================
# 🚀 ANA FONKSİYON
# ==========================================
def run_backtest():
    print("=" * 60)
    print("🧪 BACKTEST ENGINE v3.0 — Canlı Motor Uyumlu (v2.2.0)")
    print("=" * 60)
    print(f"📅 Tarih: {BACKTEST_START.date()} → {BACKTEST_END.date()}")
    print(f"💰 Başlangıç: ${INITIAL_BALANCE} | Kaldıraç: {LEVERAGE}x")
    print(f"🎯 Skor Eşiği: {SCORE_THRESHOLD} | Min Neden: {MIN_REASONS}")
    print(f"📊 SL: {SL_ATR_MULT}x ATR | TP: Bollinger Dinamik")
    print(f"⏰ Time Exit: {TIME_EXIT_CANDLES} mum ({TIME_EXIT_CANDLES * 15 / 60:.0f}h)")
    print(f"🛡️ BB R:R Guard: Aktif | Fee: Dahil")
    print()

    # CSV dosyalarını topla
    csv_files = []
    for f in os.listdir(DATA_FOLDER):
        if f.endswith('.csv') and not f.startswith('_'):
            symbol = f.replace('_USDT_USDT.csv', '').replace('_USDT.csv', '')
            csv_files.append((symbol, os.path.join(DATA_FOLDER, f)))

    print(f"📂 {len(csv_files)} coin taranacak...")
    print()

    # Paralel backtest
    all_trades = []
    workers = max(1, cpu_count() - 2)

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_process_coin, args): args[0] for args in csv_files}
        for future in as_completed(futures):
            symbol, trades = future.result()
            all_trades.extend(trades)

    if not all_trades:
        print("❌ Hiç işlem üretilemedi!")
        return

    # Sonuçları hesapla
    all_trades.sort(key=lambda t: str(t['entry_time']))

    total = len(all_trades)
    wins = [t for t in all_trades if t['pnl_pct'] > 0]
    losses = [t for t in all_trades if t['pnl_pct'] <= 0]
    win_rate = len(wins) / total * 100

    # İşlem türü dağılımı
    result_counts = {}
    for t in all_trades:
        r = t['result']
        result_counts[r] = result_counts.get(r, 0) + 1

    # Portföy simülasyonu
    final_bal, max_dd, skipped = simulate_portfolio(all_trades)
    profit_pct = (final_bal - INITIAL_BALANCE) / INITIAL_BALANCE * 100

    # SONUÇLAR
    print()
    print("=" * 60)
    print("📊 BACKTEST SONUÇLARI")
    print("=" * 60)
    print(f"📋 Toplam İşlem   : {total}")
    print(f"✅ Kazanan        : {len(wins)} ({win_rate:.1f}%)")
    print(f"❌ Kaybeden       : {len(losses)} ({100-win_rate:.1f}%)")
    print(f"💰 Başlangıç      : ${INITIAL_BALANCE}")
    print(f"💰 Final Bakiye   : ${final_bal:.2f}")
    print(f"📈 Toplam Kâr     : {profit_pct:+.1f}%")
    print(f"📉 Max Drawdown   : %{max_dd:.1f}")
    print(f"⏭️ Atlanan (Bakiye): {skipped}")

    print(f"\n📊 İşlem Türü Dağılımı:")
    for result, count in sorted(result_counts.items(), key=lambda x: -x[1]):
        pcts = [t['pnl_pct'] for t in all_trades if t['result'] == result]
        avg_pnl = np.mean(pcts)
        print(f"  {result:20s}: {count:4d} işlem | Ort PnL: {avg_pnl:+.2f}%")

    # Ort. kazanç/kayıp
    if wins:
        avg_win = np.mean([t['pnl_pct'] for t in wins])
        print(f"\n📈 Ort. Kazanç: +{avg_win:.2f}%")
    if losses:
        avg_loss = np.mean([t['pnl_pct'] for t in losses])
        print(f"📉 Ort. Kayıp : {avg_loss:.2f}%")

    # CSV kaydet
    if SAVE_CSV:
        csv_path = os.path.join(RESULTS_DIR, "backtest_v3_trades.csv")
        df_trades = pd.DataFrame(all_trades)
        df_trades.to_csv(csv_path, index=False)
        print(f"\n💾 İşlemler kaydedildi: {csv_path}")

    # Monte Carlo
    if RUN_MONTE_CARLO:
        run_monte_carlo(all_trades)

    print(f"\n{'='*60}")
    print(f"✅ Backtest Tamamlandı!")
    print(f"{'='*60}")


if __name__ == "__main__":
    run_backtest()
