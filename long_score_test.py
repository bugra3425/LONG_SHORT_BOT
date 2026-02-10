import pandas as pd
import pandas_ta as ta
from datetime import datetime

# Test için örnek veri (BTC düşüş haftası simülasyonu)
data = {
    'timestamp': pd.date_range(start='2026-01-14', periods=48, freq='H'),
    'close': [45000 - i*200 for i in range(48)],  # Sürekli düşen fiyat
    'high': [45000 - i*200 + 100 for i in range(48)],
    'low': [45000 - i*200 - 100 for i in range(48)],
    'open': [45000 - i*200 + 50 for i in range(48)],
    'volume': [1000 + i*10 for i in range(48)]
}
df = pd.DataFrame(data)

df['ema9'] = ta.ema(df['close'], length=9)
df['ema21'] = ta.ema(df['close'], length=21)
df['ema50'] = ta.ema(df['close'], length=50)
df['rsi'] = ta.rsi(df['close'], length=14)
macd = ta.macd(df['close'])
if macd is not None:
    df['macd'] = macd.iloc[:, 0]
    df['macd_signal'] = macd.iloc[:, 1]
    df['macd_hist'] = macd.iloc[:, 2]
else:
    df['macd'] = df['macd_signal'] = df['macd_hist'] = 0

def long_score(row, prev_row):
    score = 0
    reasons = []
    price = row['close']
    ema9 = row['ema9']
    ema21 = row['ema21']
    ema50 = row['ema50']
    rsi = row['rsi']
    macd = row['macd']
    macd_signal = row['macd_signal']
    prev_ema9 = prev_row['ema9']
    prev_ema21 = prev_row['ema21']
    prev_macd = prev_row['macd']
    prev_macd_signal = prev_row['macd_signal']
    # BTC trend filtresi (örnek: EMA50 ve EMA200 altında ise long puanı sıfır)
    # BTC fiyatı = price (simülasyon için)
    btc_ema50 = ema50
    btc_ema200 = ta.ema(df['close'], length=200).iloc[row.name] if row.name >= 199 else 0
    btc_trend_bear = price < btc_ema50 and price < btc_ema200
    if btc_trend_bear:
        reasons.append('BTC düşüş trendi (EMA50/200 altı)')
        return 0, reasons
    # EMA dizilimi (puanlar azaltıldı)
    if price > ema9 > ema21 > ema50:
        score += 10
        reasons.append('Bullish EMA')
    elif price > ema21 and ema9 > ema21:
        score += 5
        reasons.append('EMA Bullish')
    # Golden Cross
    if prev_ema9 <= prev_ema21 and ema9 > ema21:
        score += 8
        reasons.append('Golden Cross')
    # RSI
    if rsi < 30:
        score += 8
        reasons.append(f'RSI({rsi:.0f})')
    elif rsi < 40:
        score += 5
        reasons.append(f'RSI({rsi:.0f})')
    elif rsi > 50 and rsi < 70:
        score += 2
        reasons.append(f'RSI({rsi:.0f})')
    # MACD
    if prev_macd <= prev_macd_signal and macd > macd_signal:
        score += 8
        reasons.append('MACD Cross')
    elif macd > macd_signal and row['macd_hist'] > 0:
        score += 5
        reasons.append('MACD+')
    return score, reasons

print('Saat | Fiyat | EMA9 | EMA21 | EMA50 | RSI | MACD | MACD_S | Long Score | Nedenler')
for i in range(1, len(df)):
    row = df.iloc[i].fillna(0)
    prev_row = df.iloc[i-1].fillna(0)
    score, reasons = long_score(row, prev_row)
    print(f"{row['timestamp']} | {row['close']:.2f} | {row['ema9']:.2f} | {row['ema21']:.2f} | {row['ema50']:.2f} | {row['rsi']:.2f} | {row['macd']:.2f} | {row['macd_signal']:.2f} | {score} | {', '.join(reasons)}")
