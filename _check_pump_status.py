import asyncio, ccxt.async_support as ccxt, pandas as pd
from datetime import datetime, timezone, timedelta
from aiohttp import TCPConnector, ClientSession
from aiohttp.resolver import ThreadedResolver

async def check():
    resolver = ThreadedResolver()
    connector = TCPConnector(resolver=resolver)
    session = ClientSession(connector=connector)
    ex = ccxt.binance({
        'options':{'defaultType':'future'},
        'session': session,
        'enableRateLimit': True,
    })
    try:
        for sym in ['COLLECT/USDT:USDT','BULLA/USDT:USDT','AKE/USDT:USDT','PIPPIN/USDT:USDT']:
            data = await ex.fetch_ohlcv(sym, '4h', limit=10)
            df = pd.DataFrame(data, columns=['ts','o','h','l','c','v'])
            df['dt'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
            df['color'] = df.apply(lambda r: 'GREEN' if r['c']>r['o'] else 'RED', axis=1)
            df['body_pct'] = ((df['c']-df['o'])/df['o']*100).round(2)
            print(f'\n=== {sym} ===')
            for idx,r in df.iterrows():
                mark = '<<CANLI>>' if idx == len(df)-1 else ''
                print(f"  {r['dt'].strftime('%m/%d %H:%M')}  {r['color']:5}  O:{r['o']:.6f}  C:{r['c']:.6f}  body:{r['body_pct']:+.2f}%  {mark}")
            closed = df.iloc[:-1]
            last6 = closed.tail(6)
            greens = (last6['color']=='GREEN').sum()
            pump_h = last6['h'].max()
            pump_l = last6['l'].min()
            gain = (pump_h - pump_l)/pump_l*100
            print(f'  Son 6 kapanmis mum: {greens} yesil, gain: {gain:.1f}%')
            print(f'  Pump kosullari: min_green=4 {"OK" if greens>=4 else "FAIL"}, min_pump=30% {"OK" if gain>=30 else "FAIL"}')
    finally:
        await ex.close()
        await session.close()

asyncio.run(check())
