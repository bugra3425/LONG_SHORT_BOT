import asyncio
import ccxt.async_support as ccxt
from datetime import datetime
import aiohttp
import socket

async def check_top_gainers():
    # DNS fallback connector
    connector = aiohttp.TCPConnector(
        family=socket.AF_INET,
        resolver=aiohttp.AsyncResolver(nameservers=['8.8.8.8', '8.8.4.4'])
    )
    exchange = ccxt.binance({
        'options': {'defaultType': 'future'},
        'session': aiohttp.ClientSession(connector=connector)
    })
    
    try:
        await exchange.load_markets()
        
        # Tüm USDT coinleri al
        all_symbols = [s for s in exchange.symbols if '/USDT' in s and ':USDT' not in s]
        
        print('\n' + '='*120)
        print('TOP 10 PUMP ANALİZİ - 6×4H ROLLING WINDOW')
        print('='*120)
        print(f'{"Sıra":<6} {"Coin":<15} {"Yeşil":<8} {"Pump %":<10} {"Max High":<12} {"Min Low":<12} {"Watchlist?":<12}')
        print('-'*120)
        
        pump_results = []
        
        print(f'\n🔍 {len(all_symbols)} adet USDT coin taranıyor...\n')
        
        for i, symbol in enumerate(all_symbols, 1):
            try:
                if i % 50 == 0:
                    print(f'  ⏳ {i}/{len(all_symbols)} tamamlandı...')
                
                ohlcv = await exchange.fetch_ohlcv(symbol, '4h', limit=7)
                if len(ohlcv) < 7:
                    continue
                
                last_6 = ohlcv[-6:]
                green_count = sum(1 for c in last_6 if c[4] > c[1])
                highs = [c[2] for c in last_6]
                lows = [c[3] for c in last_6]
                pump_pct = ((max(highs) - min(lows)) / min(lows)) * 100
                
                pump_results.append({
                    'symbol': symbol,
                    'green': green_count,
                    'pump': pump_pct,
                    'high': max(highs),
                    'low': min(lows)
                })
            except:
                continue
        
        # Sırala
        pump_results.sort(key=lambda x: x['pump'], reverse=True)
        
        # Top 10
        for i, r in enumerate(pump_results[:20], 1):
            watchlist_ok = '✓✓ EVET' if r['green'] >= 4 and r['pump'] >= 30 else '✗ Hayır'
            print(f'{i:<6} {r["symbol"]:<15} {r["green"]}/6     {r["pump"]:>6.2f}%    {r["high"]:<12.8f} {r["low"]:<12.8f} {watchlist_ok:<12}')
            
            if r['symbol'] == 'ESP/USDT':
                print(f'{"":>6} {">>> ESP BULUNDU! " + str(i) + ". SIRADA <<<":^104}')
        
        print('='*120)
        
        # ESP'nin yerini bul
        esp_index = next((i for i, r in enumerate(pump_results, 1) if r['symbol'] == 'ESP/USDT'), None)
        if esp_index:
            print(f'\n📍 ESP/USDT SIRALAMASI: {esp_index}. sırada')
            if esp_index <= 10:
                print(f'✓ TOP 10\'DA → Watchlist\'e GİRMELİ!')
            else:
                print(f'✗ TOP 10\'DA DEĞİL → Bu yüzden watchlist\'e GİREMİYOR')
        else:
            print(f'\n⚠ ESP/USDT pump listesinde bulunamadı')
        
    finally:
        await exchange.close()

asyncio.run(check_top_gainers())
