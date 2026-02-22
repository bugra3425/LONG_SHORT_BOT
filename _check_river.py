import ccxt, pandas as pd
exchange = ccxt.binance({'options': {'defaultType': 'future'}})

since = exchange.parse8601('2026-01-25T16:00:00Z')
ohlcv = exchange.fetch_ohlcv('RIVER/USDT', '4h', since=since, limit=30)
df = pd.DataFrame(ohlcv, columns=['ts','open','high','low','close','vol'])
df['time'] = pd.to_datetime(df['ts'], unit='ms', utc=True).dt.strftime('%d.%m.%Y %H:%M')

entry_price = 69.789
sl = 80.257350

print(f"Giriş: {entry_price}  |  SL: {sl}")
print()
print(f"{'#':<3} {'Zaman':<18} {'Open':>10} {'High':>10} {'Low':>10} {'Close':>10}  HIGH>=SL?")
print('-'*80)
for i, row in df.iterrows():
    hit = row['high'] >= sl
    flag = '  <<<  SL TETİKLENDİ' if hit else ''
    print(f"{i:<3} {row['time']:<18} {row['open']:>10.3f} {row['high']:>10.3f} {row['low']:>10.3f} {row['close']:>10.3f}  {str(hit)}{flag}")
