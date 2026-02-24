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
                
                # Kriterleri kontrol et
                if green_count >= 4 and pump_pct >= 30:
                    pump_results.append({
                        'symbol': symbol,
                        'green': green_count,
                        'pump': pump_pct,
                        'high': max(highs),
                        'low': min(lows)
                    })
                    
            except Exception as e:
                continue
        
        print(f'\n✅ Tarama tamamlandı!')
        print(f'📊 {len(pump_results)} coin kriterleri karşılıyor (≥4 yeşil, ≥30% pump)')
        print('\n' + '='*120)
        print('TOP 10 EN YÜKSEK PUMP (Bot kriterlerine göre)')
        print('='*120)
        print(f'{"Sıra":<6} {"Coin":<15} {"Yeşil":<8} {"Pump %":<12} {"Max High":<15} {"Min Low":<15}')
        print('-'*120)
        
        # Sırala ve Top 10
        pump_results.sort(key=lambda x: x['pump'], reverse=True)
        
        esp_index = None
        for i, r in enumerate(pump_results[:20], 1):  # Top 20 göster
            marker = ''
            if r['symbol'] == 'ESP/USDT':
                marker = ' <<<< ESP BULUNDU!'
                esp_index = i
            
            print(f'{i:<6} {r["symbol"]:<15} {r["green"]}/6     {r["pump"]:>8.2f}%    {r["high"]:<15.8f} {r["low"]:<15.8f}{marker}')
        
        print('='*120)
        
        # ESP'nin durumu
        if esp_index:
            if esp_index <= 10:
                print(f'\n✅ ESP/USDT {esp_index}. SIRADA → TOP 10\'DA → Watchlist\'e GİRMELİ!')
            else:
                print(f'\n⚠ ESP/USDT {esp_index}. SIRADA → TOP 10\'DA DEĞİL → Watchlist\'e GİREMEZ')
        else:
            # ESP'yi bul ve analizini göster
            esp_data = next((r for r in pump_results if r['symbol'] == 'ESP/USDT'), None)
            if esp_data:
                esp_rank = pump_results.index(esp_data) + 1
                print(f'\n📍 ESP/USDT {esp_rank}. SIRADA (≥30% + ≥4 yeşil var AMA diğerleri daha yüksek)')
                print(f'   ESP: {esp_data["green"]}/6 yeşil, {esp_data["pump"]:.2f}% pump')
            else:
                print(f'\n❌ ESP/USDT kriterleri karşılamıyor (ya <4 yeşil ya da <30% pump)')
                # ESP'yi direkt kontrol et
                try:
                    esp_ohlcv = await exchange.fetch_ohlcv('ESP/USDT', '4h', limit=7)
                    if len(esp_ohlcv) >= 6:
                        # Canlı mum kontrolü
                        last_ts = esp_ohlcv[-1][0]
                        now = datetime.now(timezone.utc).timestamp() * 1000
                        end_ts = last_ts + (4 * 60 * 60 * 1000)
                        
                        if now < end_ts:
                            esp_candles = esp_ohlcv[-7:-1]
                        else:
                            esp_candles = esp_ohlcv[-6:]
                        
                        esp_green = sum(1 for c in esp_candles if c[4] > c[1])
                        esp_highs = [c[2] for c in esp_candles]
                        esp_lows = [c[3] for c in esp_candles]
                        esp_pump = ((max(esp_highs) - min(esp_lows)) / min(esp_lows)) * 100
                        
                        print(f'   ESP Detayları: {esp_green}/6 yeşil, {esp_pump:.2f}% pump')
                        if esp_green < 4:
                            print(f'   ❌ Yeşil mum yetersiz ({esp_green} < 4)')
                        if esp_pump < 30:
                            print(f'   ❌ Pump yetersiz ({esp_pump:.2f}% < 30%)')
                except:
                    pass
        
        print('='*120)
        
    finally:
        await exchange.close()

if __name__ == '__main__':
    asyncio.run(scan_top10())
