"""
🧪 Backtest Engine v4.0 — Yapısal Düzeltmeler
1. ATR TP (sabit hedef, Bollinger değil)
2. TP1 sonrası SL yarıya (breakeven değil)
3. Decay KAPALI
4. Daha az, daha kaliteli işlem
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

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_FOLDER = os.path.join(_PROJECT_ROOT, "data", "backtest_data")
RESULTS_DIR = os.path.join(_PROJECT_ROOT, "data")

# ==========================================
# ⚙️ v4.0 PARAMETRELER
# ==========================================
INITIAL_BALANCE = 1000
POSITION_SIZE_PCT = 10
LEVERAGE = 5
TAKER_FEE = 0.0005
FEE_ROUND_TRIP = TAKER_FEE * 2  # Giriş + Çıkış

BACKTEST_START = datetime(2025, 12, 1)
BACKTEST_END = datetime(2026, 1, 13, 23, 59, 59)

# Strateji
SCORE_THRESHOLD = 80
MIN_REASONS = 5              # 4 → 5 (daha kaliteli giriş)
COOLDOWN_CANDLES = 8
MAX_ATR_PERCENT = 4.5
MIN_ATR_PERCENT = 0.5
HARD_STOP_LOSS_PCT = 2.5

# TP/SL — ATR Bazlı Sabit Hedefler
SL_ATR_MULT = 2.4
TP1_RR = 1.5               # 1. hedef: 1.5x risk
TP2_RR = 3.0               # 2. hedef: 3x risk (daha uzak)
TP3_RR = 5.0               # 3. hedef: 5x risk
TP1_CLOSE_PCT = 0.35        # 40→35: Daha az erken kâr al
TP2_CLOSE_PCT = 0.35        # 30→35: Orta hedefe daha fazla bırak
TP3_CLOSE_PCT = 0.30

# TP1 sonrası SL nereye çekilsin?
# 0.0 = girişe (eskisi, breakeven)
# 0.5 = SL ile giriş arası yarı yol
TP1_SL_RETRACE = 0.50       # ✨ ANAHTAR DEĞİŞİKLİK

# Decay = KAPALI (optimization kanıtı)
SIGNAL_DECAY_EXIT = False

# Time Exit
TIME_EXIT_CANDLES = 192

# Blacklist
COIN_BLACKLIST_AFTER = 3
COIN_BLACKLIST_CANDLES = 32
MAX_TRADES_PER_COIN = 30

# Monte Carlo
MONTE_CARLO_SIMS = 5000


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
    df['vol_avg20'] = df['volume'].shift(1).rolling(window=20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_avg20']
    df = df.ffill().fillna(0).infer_objects(copy=False)
    return df


def score_short(row):
    score = 0
    reasons = []
    adx = row['adx']
    di_plus, di_minus = row['di_plus'], row['di_minus']
    rsi = row['rsi']
    bb_pct = row['bb_pct']
    stoch_k = row['stoch_k']
    mfi = row['mfi']
    sma50 = row['sma50']

    # ADX (tek blok)
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

    # MACD
    if row['macd'] < row['macd_signal']:
        score += 5
        reasons.append("MACD-")

    # Bollinger (overextension indicator, TP için değil)
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

    return score, len(reasons), reasons


def backtest_coin(symbol, df):
    trades = []
    in_position = False
    entry_price = sl = tp1 = tp2 = tp3 = original_sl = 0.0
    entry_time = None
    entry_candle = 0
    tp1_hit = tp2_hit = False
    position_remaining = 1.0
    last_exit_candle = -999
    trade_count = 0
    consecutive_losses = 0
    blacklist_until = 0
    entry_reasons = []

    rows = df.to_dict('records')
    n = len(rows)

    for i in range(50, n):
        row = rows[i]
        prev = rows[i - 1]
        price = row['close']
        high = row['high']
        low = row['low']

        if in_position:
            candles_in = i - entry_candle

            # Time Exit
            if candles_in > TIME_EXIT_CANDLES:
                pnl = ((entry_price - price) / entry_price) * 100 * position_remaining
                pnl -= FEE_ROUND_TRIP * 100 * position_remaining
                trades.append({'symbol': symbol, 'entry_time': entry_time, 'exit_time': row['timestamp'],
                    'entry_price': entry_price, 'exit_price': price,
                    'pnl_pct': pnl, 'result': 'TIME_EXIT', 'reasons': entry_reasons})
                in_position = False; last_exit_candle = i; position_remaining = 1.0
                continue

            # Stop Loss
            if high >= sl:
                pnl = ((entry_price - sl) / entry_price) * 100 * position_remaining
                pnl -= FEE_ROUND_TRIP * 100 * position_remaining
                if abs(pnl) > HARD_STOP_LOSS_PCT:
                    pnl = -HARD_STOP_LOSS_PCT

                res = 'STOP_LOSS'
                if tp1_hit: res = 'TRAIL_TP1'
                if tp2_hit: res = 'TRAIL_TP2'

                if pnl < 0:
                    consecutive_losses += 1
                else:
                    consecutive_losses = 0
                if consecutive_losses >= COIN_BLACKLIST_AFTER:
                    blacklist_until = i + COIN_BLACKLIST_CANDLES
                    consecutive_losses = 0

                trades.append({'symbol': symbol, 'entry_time': entry_time, 'exit_time': row['timestamp'],
                    'entry_price': entry_price, 'exit_price': sl,
                    'pnl_pct': pnl, 'result': res, 'reasons': entry_reasons})
                in_position = False; last_exit_candle = i; position_remaining = 1.0
                continue

            # TP1
            if not tp1_hit and low <= tp1:
                tp1_hit = True
                pnl = ((entry_price - tp1) / entry_price) * 100 * TP1_CLOSE_PCT
                pnl -= FEE_ROUND_TRIP * 100 * TP1_CLOSE_PCT
                trades.append({'symbol': symbol, 'entry_time': entry_time, 'exit_time': row['timestamp'],
                    'entry_price': entry_price, 'exit_price': tp1,
                    'pnl_pct': pnl, 'result': 'TP1', 'reasons': entry_reasons})
                position_remaining -= TP1_CLOSE_PCT
                consecutive_losses = 0

                # ✨ SL'i YARIYA çek (girişe değil!)
                # original_sl = entry + risk, entry arada
                # Yarı yol = entry + risk * TP1_SL_RETRACE (giriş yönüne doğru)
                risk = original_sl - entry_price
                sl = entry_price + risk * TP1_SL_RETRACE

            # TP2
            if tp1_hit and not tp2_hit and low <= tp2:
                tp2_hit = True
                pnl = ((entry_price - tp2) / entry_price) * 100 * TP2_CLOSE_PCT
                pnl -= FEE_ROUND_TRIP * 100 * TP2_CLOSE_PCT
                trades.append({'symbol': symbol, 'entry_time': entry_time, 'exit_time': row['timestamp'],
                    'entry_price': entry_price, 'exit_price': tp2,
                    'pnl_pct': pnl, 'result': 'TP2', 'reasons': entry_reasons})
                position_remaining -= TP2_CLOSE_PCT
                # SL'i girişe çek (TP2'den sonra artık güvenli)
                sl = entry_price

            # TP3
            if tp2_hit and low <= tp3:
                pnl = ((entry_price - tp3) / entry_price) * 100 * TP3_CLOSE_PCT
                pnl -= FEE_ROUND_TRIP * 100 * TP3_CLOSE_PCT
                trades.append({'symbol': symbol, 'entry_time': entry_time, 'exit_time': row['timestamp'],
                    'entry_price': entry_price, 'exit_price': tp3,
                    'pnl_pct': pnl, 'result': 'TP3', 'reasons': entry_reasons})
                in_position = False; last_exit_candle = i; position_remaining = 1.0
                continue

        else:
            # ENTRY
            if i - last_exit_candle < COOLDOWN_CANDLES: continue
            if trade_count >= MAX_TRADES_PER_COIN: continue
            if i < blacklist_until: continue

            score, num_reasons, reasons = score_short(row)
            atr = row['atr']
            atr_pct = (atr / price) * 100 if price > 0 else 0
            if atr_pct > MAX_ATR_PERCENT or atr_pct < MIN_ATR_PERCENT: continue

            # RSI momentum filtresi
            if row['rsi'] >= 80 and row['rsi'] >= prev['rsi']: continue

            # Hacim patlaması
            if row['vol_ratio'] > 3.5: continue

            # God Candle
            if abs(row['close'] - row['open']) > atr * 3: continue
            chg = (row['close'] - row['open']) / row['open'] * 100 if row['open'] > 0 else 0
            wick = (row['high'] - row['close']) / (row['high'] - row['low']) if (row['high'] - row['low']) > 0 else 0
            if chg > 3.0 and wick < 0.15: continue

            # Kırmızı mum doğrulaması
            if row['close'] >= row['open']: continue

            # RedConfirm bonus
            if prev['close'] > prev['open']:
                prev_vol = prev['volume'] if prev['volume'] > 0 else 1
                if row['volume'] / prev_vol >= 0.7:
                    score += 10
                    reasons.append("RedConfirm")
                    num_reasons += 1

            # SMA50 cezalı eşik
            threshold = SCORE_THRESHOLD + 15 if price > row['sma50'] else SCORE_THRESHOLD
            if score < threshold or num_reasons < MIN_REASONS: continue

            # ENTRY
            in_position = True
            entry_price = price
            entry_time = row['timestamp']
            entry_candle = i
            entry_reasons = reasons
            trade_count += 1

            risk = atr * SL_ATR_MULT
            original_sl = price + risk
            sl = original_sl
            tp1 = price - (risk * TP1_RR)
            tp2 = price - (risk * TP2_RR)
            tp3 = price - (risk * TP3_RR)
            tp1_hit = tp2_hit = False
            position_remaining = 1.0

    # Dönem sonu
    if in_position:
        pnl = ((entry_price - rows[-1]['close']) / entry_price) * 100 * position_remaining
        pnl -= FEE_ROUND_TRIP * 100 * position_remaining
        trades.append({'symbol': symbol, 'entry_time': entry_time, 'exit_time': rows[-1]['timestamp'],
            'entry_price': entry_price, 'exit_price': rows[-1]['close'],
            'pnl_pct': pnl, 'result': 'DÖNEM_SONU', 'reasons': entry_reasons})
    return trades


def _process_coin(args):
    symbol, filename = args
    if not os.path.exists(filename): return symbol, []
    try:
        df = pd.read_csv(filename)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df[(df['timestamp'] >= BACKTEST_START) & (df['timestamp'] <= BACKTEST_END)].copy()
        if len(df) < 50: return symbol, []
        df = calculate_indicators(df)
        return symbol, backtest_coin(symbol, df)
    except Exception as e:
        return symbol, []


def simulate_portfolio(all_trades):
    from collections import defaultdict
    pos = defaultdict(list)
    for t in all_trades:
        pos[f"{t['symbol']}_{t['entry_time']}"].append(t)

    events = []
    for pid, tt in pos.items():
        tt.sort(key=lambda x: str(x['exit_time']))
        events.append({'time': tt[0]['entry_time'], 'type': 'O', 'pid': pid})
        for t in tt:
            events.append({'time': t['exit_time'], 'type': 'C', 'pid': pid, 'trade': t})
    events.sort(key=lambda e: (str(e['time']), 0 if e['type'] == 'C' else 1))

    avail = INITIAL_BALANCE
    active = {}
    skip = set()
    peak = INITIAL_BALANCE
    mdd = 0

    for ev in events:
        if ev['type'] == 'O':
            m = avail * (POSITION_SIZE_PCT / 100)
            if m < 1: skip.add(ev['pid']); continue
            avail -= m
            active[ev['pid']] = {'m': m, 'r': 1.0}
        else:
            pid = ev['pid']
            if pid in skip or pid not in active: continue
            t = ev['trade']
            p = active[pid]
            if 'TP1' in t['result']: f = TP1_CLOSE_PCT
            elif 'TP2' in t['result']: f = TP2_CLOSE_PCT
            elif 'TP3' in t['result']: f = TP3_CLOSE_PCT
            else: f = p['r']
            fm = p['m'] * f
            raw = t['pnl_pct'] / f if f > 0 else 0
            profit = fm * LEVERAGE * (raw / 100)
            fee = fm * LEVERAGE * TAKER_FEE * 2
            ret = max(fm + profit - fee, 0)
            avail += ret
            p['r'] -= f
            tv = avail + sum(x['m']*x['r'] for x in active.values())
            if tv > peak: peak = tv
            dd = (peak - tv) / peak * 100 if peak > 0 else 0
            if dd > mdd: mdd = dd
            if p['r'] <= 0.01: del active[pid]

    return avail + sum(p['m']*p['r'] for p in active.values()), mdd, len(skip)


def run():
    print("=" * 60)
    print("🧪 BACKTEST v4.0 — Yapısal Düzeltmeler")
    print("=" * 60)
    print(f"📅 {BACKTEST_START.date()} → {BACKTEST_END.date()}")
    print(f"💰 ${INITIAL_BALANCE} | {LEVERAGE}x | Skor≥{SCORE_THRESHOLD} | Min{MIN_REASONS}Neden")
    print(f"📊 SL: {SL_ATR_MULT}x | TP: {TP1_RR}/{TP2_RR}/{TP3_RR}x ATR")
    print(f"🔑 TP1→SL Retrace: {TP1_SL_RETRACE*100:.0f}% (Eski: Breakeven)")
    print(f"🚫 Decay: KAPALI | HSL: {HARD_STOP_LOSS_PCT}%")
    print()

    files = [(f.replace('_USDT_USDT.csv','').replace('_USDT.csv',''), os.path.join(DATA_FOLDER, f))
             for f in os.listdir(DATA_FOLDER) if f.endswith('.csv') and not f.startswith('_')]

    print(f"📂 {len(files)} coin...")

    all_trades = []
    with ProcessPoolExecutor(max_workers=max(1, cpu_count()-2)) as ex:
        for sym, trades in ex.map(_process_coin, files):
            if trades: all_trades.extend(trades)

    if not all_trades:
        print("❌ Hiç işlem yok!")
        return

    all_trades.sort(key=lambda t: str(t['entry_time']))
    total = len(all_trades)
    wins = [t for t in all_trades if t['pnl_pct'] > 0]
    losses = [t for t in all_trades if t['pnl_pct'] <= 0]
    wr = len(wins) / total * 100

    dist = {}
    for t in all_trades:
        dist[t['result']] = dist.get(t['result'], 0) + 1

    final, mdd, skip = simulate_portfolio(all_trades)
    profit = (final - INITIAL_BALANCE) / INITIAL_BALANCE * 100

    print(f"\n{'='*60}")
    print(f"📊 SONUÇLAR")
    print(f"{'='*60}")
    print(f"📋 İşlem   : {total}")
    print(f"✅ WR      : {wr:.1f}%")
    print(f"💰 Final   : ${final:.2f} ({profit:+.1f}%)")
    print(f"📉 Max DD  : {mdd:.1f}%")
    print(f"⏭️ Atlanan : {skip}")

    print(f"\n📊 Dağılım:")
    for r, c in sorted(dist.items(), key=lambda x: -x[1]):
        avg = np.mean([t['pnl_pct'] for t in all_trades if t['result'] == r])
        print(f"  {r:15s}: {c:4d} | Ort: {avg:+.2f}%")

    if wins:
        print(f"\n📈 Ort. Kazanç: +{np.mean([t['pnl_pct'] for t in wins]):.2f}%")
    if losses:
        print(f"📉 Ort. Kayıp : {np.mean([t['pnl_pct'] for t in losses]):.2f}%")

    # R:R
    if wins and losses:
        rr = abs(np.mean([t['pnl_pct'] for t in wins])) / abs(np.mean([t['pnl_pct'] for t in losses]))
        print(f"⚖️ R:R     : 1:{rr:.2f}")

    df_out = pd.DataFrame(all_trades)
    csv_path = os.path.join(RESULTS_DIR, "backtest_v4_trades.csv")
    df_out.to_csv(csv_path, index=False)
    print(f"\n💾 {csv_path}")

    # Monte Carlo
    rets = [t['pnl_pct'] * LEVERAGE for t in all_trades]
    finals = []
    dds = []
    ruin = 0
    for _ in range(MONTE_CARLO_SIMS):
        sh = random.choices(rets, k=len(rets))
        b = INITIAL_BALANCE; pk = b; md = 0
        for p in sh:
            s = b * POSITION_SIZE_PCT / 100
            b += s * p / 100 - s * LEVERAGE * TAKER_FEE * 2
            if b <= 0: b = 0; ruin += 1; break
            if b > pk: pk = b
            d = (pk - b) / pk * 100
            if d > md: md = d
        finals.append(b); dds.append(md)

    finals = np.array(finals)
    print(f"\n{'='*60}")
    print(f"🎲 MONTE CARLO ({MONTE_CARLO_SIMS}x)")
    print(f"{'='*60}")
    print(f"📈 Ortalama : ${np.mean(finals):.0f}")
    print(f"📊 Medyan   : ${np.median(finals):.0f}")
    print(f"🛡️ %5 Kötü  : ${np.percentile(finals, 5):.0f}")
    print(f"🚀 %95 İyi  : ${np.percentile(finals, 95):.0f}")
    print(f"📉 Ort DD   : {np.mean(dds):.1f}%")
    print(f"💀 İflas     : {ruin/MONTE_CARLO_SIMS*100:.2f}%")
    print(f"\n{'='*60}")
    print(f"✅ Tamamlandı!")


if __name__ == "__main__":
    run()
