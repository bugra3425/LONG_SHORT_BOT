import ccxt
import pandas as pd

exchange = ccxt.binance({'options': {'defaultType': 'future'}})

# RDNT/USDT 4H barları — giriş: 2025-10-11 20:00 UTC
since = exchange.parse8601('2025-10-07T00:00:00Z')
ohlcv = exchange.fetch_ohlcv('RDNT/USDT', '4h', since=since, limit=50)

df = pd.DataFrame(ohlcv, columns=['ts','open','high','low','close','vol'])
df['time'] = pd.to_datetime(df['ts'], unit='ms', utc=True).dt.strftime('%d.%m.%Y %H:%M')
df = df.drop(columns=['ts','vol'])

# Giriş barının indexini bul (2025-10-11 20:00 UTC)
entry_idx = None
for i, row in df.iterrows():
    if '11.10.2025 20:00' in row['time']:
        entry_idx = i
        break

print(f"Giriş barı index: {entry_idx}")
print()

if entry_idx is None:
    print("HATA: Giriş barı bulunamadı!")
    print(df[['time','open','high','low','close']].to_string())
else:
    print("=== TÜM BARLAR (giriş ±5) ===")
    print(df.iloc[max(0,entry_idx-10):entry_idx+3][['time','open','high','low','close']].to_string())
    print()

    n = 6
    # Backtest pump window: ts_idx - n + k, k=0..5
    # Yani giriş barı entry_idx, pump window = entry_idx-6 .. entry_idx-1
    window_start = entry_idx - n
    window = df.iloc[window_start:entry_idx]
    print(f"=== PUMP WINDOW (6 bar: {window.iloc[0]['time']} → {window.iloc[-1]['time']}) ===")
    for _, r in window.iterrows():
        color = "🟢" if r['close'] > r['open'] else "🔴"
        body = abs(r['close'] - r['open']) / r['open'] * 100
        print(f"  {color} {r['time']}  O:{r['open']:.6f}  H:{r['high']:.6f}  L:{r['low']:.6f}  C:{r['close']:.6f}  gövde:%{body:.2f}")

    green_count = sum(1 for _, r in window.iterrows() if r['close'] > r['open'])
    pump_high = window['high'].max()
    pump_low  = window['low'].min()
    net_gain  = (pump_high - pump_low) / pump_low * 100

    print()
    print(f"  Yeşil mum sayısı: {green_count}/6  (min 4) → {'✅ GEÇER' if green_count >= 4 else '❌ GEÇEMİYOR'}")
    print(f"  pump_low        : {pump_low:.6f}")
    print(f"  pump_high       : {pump_high:.6f}")
    print(f"  net_gain        : %{net_gain:.2f}  (min %30) → {'✅ GEÇER' if net_gain >= 30 else '❌ GEÇEMİYOR'}")

    print()
    entry_bar = df.iloc[entry_idx]
    prev_bar  = df.iloc[entry_idx - 1]

    is_red = entry_bar['close'] < entry_bar['open']
    red_body = (entry_bar['open'] - entry_bar['close']) / entry_bar['open'] * 100

    is_prev_green = prev_bar['close'] > prev_bar['open']
    prev_body = (prev_bar['close'] - prev_bar['open']) / prev_bar['open'] * 100 if is_prev_green else 0

    close_below_pump_high = entry_bar['close'] < pump_high

    print(f"=== GİRİŞ BARI ({entry_bar['time']}) ===")
    print(f"  O:{entry_bar['open']:.6f}  H:{entry_bar['high']:.6f}  L:{entry_bar['low']:.6f}  C:{entry_bar['close']:.6f}")
    print(f"  Kırmızı mum?           {'✅ EVET' if is_red else '❌ HAYIR'}")
    print(f"  Gövde %{red_body:.2f}              {'✅ GEÇER (≥%4)' if red_body >= 4 else '❌ GEÇEMİYOR (<4%)'}")
    print(f"  close < pump_high?     {entry_bar['close']:.6f} < {pump_high:.6f} → {'✅ EVET' if close_below_pump_high else '❌ HAYIR'}")

    print()
    print(f"=== ÖNCEKİ BAR ({prev_bar['time']}) ===")
    print(f"  O:{prev_bar['open']:.6f}  C:{prev_bar['close']:.6f}")
    print(f"  Yeşil mum?             {'✅ EVET' if is_prev_green else '❌ HAYIR'}")
    if is_prev_green:
        print(f"  Gövde %{prev_body:.2f}              {'✅ GEÇER (≤%30)' if prev_body <= 30 else '❌ GEÇEMİYOR (>30%)'}")

    print()
    all_ok = (green_count >= 4 and net_gain >= 30 and is_red and red_body >= 4
              and close_below_pump_high and is_prev_green and prev_body <= 30)
    print(f"=== SONUÇ: {'✅ TÜM KOŞULLAR SAĞLANIYOR — GİRİŞ GEÇERLİ' if all_ok else '❌ KOŞULLARDAN EN AZ BİRİ SAĞLANMIYOR'} ===")
