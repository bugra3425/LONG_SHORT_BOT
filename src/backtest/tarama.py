"""
Anlık Piyasa Tarama Scripti
Dosya: tarama.py
Tarih: 12 Şubat 2026
Açıklama: Binance Futures'dan en çok yükselen 50 coini çeker,
          BB + RSI + MACD + Hacim Spike teknik analiziyle tarar
          ve sinyal bulunanları terminalde detaylı gösterir.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
from voltalite import *

print('='*60)
print(' PUMP/DUMP YAKALAYICI - ANLIK FUTURES TARAMA')
print(f' Tarih: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print('='*60)

# 1) Futures ticker verilerini çek
print('\n[1] Binance FUTURES ticker verileri çekiliyor...')
tickers = get_futures_tickers()
if not tickers:
    print('HATA: Futures ticker verisi alınamadı!')
    exit()
print(f'  Toplam {len(tickers)} futures ticker alındı')

# 2) En çok yükselen Top 50 coin
print('\n[2] En çok yükselen Top 50 coin filtreleniyor...')
top_coins = filter_top_volatile_coins(tickers)
print(f'  {len(top_coins)} coin filtrelendi\n')

print('='*60)
print(f'  TOP {len(top_coins)} FUTURES - En Çok Yükselen (24s)')
print('='*60)
for i, c in enumerate(top_coins, 1):
    name = c['symbol'].replace('USDT', '')
    pct = c['price_change_pct']
    vol_m = c['volume_usd'] / 1e6
    sign = '+' if pct >= 0 else ''
    print(f'  {i:>3}. {name:<12} | ${c["price"]:<12.6g} | 24s: {sign}{pct:.2f}% | Hacim: ${vol_m:.1f}M')

# 3) Teknik analiz
print('\n' + '='*60)
print('  TEKNİK ANALİZ (BB + RSI + MACD + Hacim)')
print('='*60)

signals = []
total = len(top_coins)
for idx, coin_info in enumerate(top_coins, 1):
    symbol = coin_info['symbol']
    clean = symbol.replace('USDT', '')
    print(f'  [{idx}/{total}] {clean:<12} analiz ediliyor...', end='', flush=True)
    try:
        sig = analyze_coin(symbol)
        if sig:
            signals.append((sig, coin_info))
            dir_label = 'LONG ' if sig['direction'] == 'LONG' else 'SHORT'
            rsi_val = sig['rsi']
            rsi_str = f'{rsi_val:.1f}' if rsi_val else 'N/A'
            macd_h = sig['macd_hist']
            macd_str = '+' if (macd_h and macd_h > 0) else '-'
            vol_str = 'SPIKE' if sig['volume_spike'] else 'normal'
            print(f' >> {dir_label} | Mum: {sig["candle_change_pct"]:+.2f}% | RSI: {rsi_str} | MACD: {macd_str} | Hacim: {vol_str} | Skor: {sig["score"]} | {sig["leverage"]}x')
        else:
            print(' sinyal yok')
    except KeyboardInterrupt:
        print(f'\n\n  🛑 TARAMA KULLANICI TARAFINDAN DURDURULDU.')
        break
    except Exception as e:
        print(f' HATA: {e}')
    time.sleep(0.12)

print('\n' + '='*60)
if signals:
    print(f'  TOPLAM {len(signals)} SİNYAL BULUNDU!')
    print('='*60)
    signals.sort(key=lambda x: x[0]['score'], reverse=True)
    for i, (sig, ci) in enumerate(signals, 1):
        clean = sig['symbol'].replace('USDT', '')
        dir_e = sig['direction']
        rsi_val = sig['rsi']
        rsi_str = f'{rsi_val:.1f}' if rsi_val else 'N/A'
        spike_str = 'EVET' if sig['volume_spike'] else 'HAYIR'
        print(f'\n  [{i}] {dir_e} - {clean}/USDT')
        print(f'      Giriş: ${sig["entry_price"]:.6g}')
        print(f'      TP(%4): ${sig["tp_price"]:.6g}')
        print(f'      SL(%2): ${sig["sl_price"]:.6g}')
        print(f'      Kaldıraç: {sig["leverage"]}x | Skor: {sig["score"]}/100')
        print(f'      RSI: {rsi_str} | BB Alt: ${sig["bb_lower"]:.6g} | BB Üst: ${sig["bb_upper"]:.6g}')
        print(f'      Mum Değişim: {sig["candle_change_pct"]:+.2f}% | Hacim Spike: {spike_str} (x{sig["vol_ratio"]:.1f})')
else:
    print(f'  ŞU AN SİNYAL YOK - Piyasa BB+%{MIN_CANDLE_CHANGE_PCT} koşullarını sağlamıyor')
    print('='*60)

print(f'\n  Tarama tamamlandı: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
