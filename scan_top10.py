"""
GERÇEK CANLI TOP 10 PUMP SCANNER
Bot kodundaki detect_pump() mantığını kullanarak Top 10'u bulur
"""
import asyncio
import ccxt.async_support as ccxt
import aiohttp
import socket
from datetime import datetime, timedelta, timezone
import pandas as pd

async def scan_top10():
    # DNS fallback
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
        all_symbols = [s for s in exchange.symbols if '/USDT' in s and ':USDT' not in s]
        
        print('\n' + '='*120)
        print(f'🔍 {len(all_symbols)} USDT COIN TARANACAK (6×4H Rolling Pump)')
        print('='*120)
        
        pump_results = []
        
        for i, symbol in enumerate(all_symbols, 1):
            try:
                if i % 50 == 0:
                    print(f'  ⏳ {i}/{len(all_symbols)} tamamlandı...')
                
                ohlcv = await exchange.fetch_ohlcv(symbol, '4h', limit=7)
                if len(ohlcv) < 7:
                    continue
                
                # Son mum canlı mı kontrolü (basit)
                last_candle_ts = ohlcv[-1][0]
                now_ts = datetime.now(timezone.utc).timestamp() * 1000
                candle_duration_ms = 4 * 60 * 60 * 1000  # 4h in ms
                candle_end_ts = last_candle_ts + candle_duration_ms
                
                # Canlı mumu at
                if now_ts < candle_end_ts:
                    analysis_candles = ohlcv[-7:-1]  # Son 6 kapanan
                else:
                    analysis_candles = ohlcv[-6:]  # Son 6 kapanan
                
                if len(analysis_candles) < 6:
                    continue
                
                # Yeşil mum sayısı
                green_count = sum(1 for c in analysis_candles if c[4] > c[1])
                
                # Pump %
                highs = [c[2] for c in analysis_candles]
                lows = [c[3] for c in analysis_candles]
                pump_pct = ((max(highs) - min(lows)) / min(lows)) * 100
                
                # Anti-Rocket: bir önceki mumun tek başına yükselişi
                prev_candle = analysis_candles[-1]  # tetikleyiciden önceki mum
                if prev_candle[1] > 0:
                    prev_body_pct = (prev_candle[4] - prev_candle[1]) / prev_candle[1] * 100.0
                else:
                    prev_body_pct = 0.0

                # Kriterleri kontrol et
                if green_count >= 4 and pump_pct >= 30:
                    pump_results.append({
                        'symbol': symbol,
                        'green': green_count,
                        'pump': pump_pct,
                        'high': max(highs),
                        'low': min(lows),
                        'prev_body_pct': prev_body_pct,
                    })
                    
            except Exception as e:
                continue
        
        ANTI_ROCKET_PCT = 30.0  # Bot ile aynı eşik
        valid   = [r for r in pump_results if r['prev_body_pct'] < ANTI_ROCKET_PCT]
        blocked = [r for r in pump_results if r['prev_body_pct'] >= ANTI_ROCKET_PCT]

        print(f'\n✅ Tarama tamamlandı!')
        print(f'📊 {len(pump_results)} coin ≥4 yeşil + ≥30% pump → '
              f'{len(valid)} GEÇERLİ / {len(blocked)} ANTI-ROCKET (önceki mum ≥%{ANTI_ROCKET_PCT})')
        print('\n' + '='*130)
        print('✅ GEÇERLİ COINLER (Bot watchlist adayları)')
        print('='*130)
        print(f'{"Sıra":<6} {"Coin":<18} {"Yeşil":<8} {"Pump %":<12} {"Önceki Mum %":<16} {"Max High":<15} {"Min Low":<15}')
        print('-'*130)
        valid.sort(key=lambda x: x['pump'], reverse=True)
        for i, r in enumerate(valid[:10], 1):
            print(f'{i:<6} {r["symbol"]:<18} {r["green"]}/6     {r["pump"]:>8.2f}%    {r["prev_body_pct"]:>+10.1f}%      {r["high"]:<15.8f} {r["low"]:<15.8f}')
        if not valid:
            print('  (Geçerli coin yok)')

        if blocked:
            print(f'\n🚫 ANTI-ROCKET FİLTREDE TAKILDI (önceki tek mum ≥%{ANTI_ROCKET_PCT} — sahte düşüş riski)')
            print('='*130)
            print(f'{"Sıra":<6} {"Coin":<18} {"Yeşil":<8} {"Pump %":<12} {"Önceki Mum %":<16} {"Max High":<15} {"Min Low":<15}')
            print('-'*130)
            blocked.sort(key=lambda x: x['pump'], reverse=True)
            for i, r in enumerate(blocked, 1):
                print(f'{i:<6} {r["symbol"]:<18} {r["green"]}/6     {r["pump"]:>8.2f}%    {r["prev_body_pct"]:>+10.1f}%  ❌  {r["high"]:<15.8f} {r["low"]:<15.8f}')

        print('\n' + '='*130)

    finally:
        await exchange.close()

if __name__ == '__main__':
    asyncio.run(scan_top10())
