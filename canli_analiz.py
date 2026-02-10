from swing_bot import *

print('='*60)
print('CANLI ANALIZ - 10 SUBAT 2026')
print('='*60)

# BTC Trend
btc_trend = analyze_btc_trend()
btc_dir, btc_str = btc_trend
print(f'BTC TREND: {btc_dir} (Guc: {btc_str})')
print()

# En iyi coinleri tara
signals = []
for symbol in TOP_PERFORMERS:
    coin = symbol.split('/')[0]
    try:
        result = analyze_coin_swing(symbol, 1, btc_trend)
        if result:
            signals.append(result)
            dir_e = 'LONG' if result['direction'] == 'LONG' else 'SHORT'
            print(f'{coin}: {dir_e} | Skor:{result["score"]} | WR:{result["win_rate"]:.0f}% | {result["leverage"]}x')
    except Exception as e:
        pass
    time.sleep(0.3)

print()
print('='*60)
print('SONUC VE KARAR')
print('='*60)

if signals:
    # En iyi sinyali sec
    signals.sort(key=lambda x: (x['score'] + x['win_rate']), reverse=True)
    best = signals[0]
    
    print()
    print('>>> EN IYI SINYAL <<<')
    print(f'  Coin: {best["symbol"].split("/")[0]}')
    print(f'  Yon: {best["direction"]}')
    print(f'  Skor: {best["score"]}')
    print(f'  Win Rate: {best["win_rate"]:.0f}%')
    print(f'  Kaldirac: {best["leverage"]}x')
    print(f'  Giris: ${best["price"]:.4f}')
    print(f'  Stop Loss: ${best["stop_loss"]:.4f}')
    print(f'  TP1: ${best["tp1"]:.4f}')
    print(f'  TP2: ${best["tp2"]:.4f}')
    print(f'  TP3: ${best["tp3"]:.4f}')
    
    # BTC uyumu
    if (best['direction'] == 'LONG' and btc_dir == 'BULLISH') or (best['direction'] == 'SHORT' and btc_dir == 'BEARISH'):
        print()
        print('*** BTC ILE UYUMLU - GUVENLI ***')
    elif btc_dir == 'NEUTRAL':
        print()
        print('*** BTC NOTR - DIKKATLI ***')
    else:
        print()
        print('*** BTC TERS YON - RISKLI ***')
        
    # Tum sinyaller
    print()
    print('='*60)
    print('TUM SINYALLER (Sirali)')
    print('='*60)
    for i, s in enumerate(signals[:5], 1):
        coin = s["symbol"].split("/")[0]
        print(f'{i}. {coin} | {s["direction"]} | Skor:{s["score"]} | WR:{s["win_rate"]:.0f}%')
else:
    print('Sinyal bulunamadi')
