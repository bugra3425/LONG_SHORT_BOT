"""
🔬 Backtest Parameter Optimizer — Grid Search
engine_v3 motorunu farklı parametre setleriyle çalıştırır.
En iyi kombinasyonu bulur.
"""
import sys
import os
import itertools
import time
from multiprocessing import cpu_count

# engine_v3'ü import edebilmek için path ayarla
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import src.backtest.engine_v3 as eng

# ==========================================
# 🔬 OPTİMİZASYON GRID'İ
# ==========================================
PARAM_GRID = {
    'SIGNAL_DECAY_EXIT': [True, False],
    'DECAY_RATIO': [0.20, 0.30],               # 0.40 çok agresifti
    'HARD_STOP_LOSS_PCT': [2.5, 3.0, 3.5],
    'SL_ATR_MULT': [1.8, 2.0, 2.4],
    'SCORE_THRESHOLD': [80, 90],
    'COOLDOWN_CANDLES': [5, 8],
}

# Decay kapalıyken DECAY_RATIO'yu test etmeye gerek yok → akıllı eleme
def generate_combos(grid):
    keys = list(grid.keys())
    values = list(grid.values())
    combos = []
    for combo in itertools.product(*values):
        params = dict(zip(keys, combo))
        # Decay kapalıysa ratio'yu test etme (duplicate azalt)
        if not params['SIGNAL_DECAY_EXIT'] and params['DECAY_RATIO'] != 0.20:
            continue
        combos.append(params)
    return combos


def run_single_backtest(params):
    """Tek parametre seti ile backtest çalıştır"""
    import pandas as pd
    import pandas_ta as ta

    # Parametreleri engine'e yaz
    eng.SIGNAL_DECAY_EXIT = params['SIGNAL_DECAY_EXIT']
    eng.DECAY_RATIO = params['DECAY_RATIO']
    eng.HARD_STOP_LOSS_PCT = params['HARD_STOP_LOSS_PCT']
    eng.SL_ATR_MULT = params['SL_ATR_MULT']
    eng.SCORE_THRESHOLD = params['SCORE_THRESHOLD']
    eng.COOLDOWN_CANDLES = params['COOLDOWN_CANDLES']

    # CSV dosyalarını topla
    csv_files = []
    for f in os.listdir(eng.DATA_FOLDER):
        if f.endswith('.csv') and not f.startswith('_'):
            symbol = f.replace('_USDT_USDT.csv', '').replace('_USDT.csv', '')
            csv_files.append((symbol, os.path.join(eng.DATA_FOLDER, f)))

    # Sıralı backtest (paralel process içinde paralel açamayız)
    all_trades = []
    for args in csv_files:
        symbol, trades = eng._process_coin(args)
        all_trades.extend(trades)

    if not all_trades:
        return {
            'params': params,
            'total': 0, 'win_rate': 0, 'final': 0,
            'profit_pct': -100, 'max_dd': 100, 'skipped': 0,
            'sharpe': -99
        }

    total = len(all_trades)
    wins = [t for t in all_trades if t['pnl_pct'] > 0]
    win_rate = len(wins) / total * 100

    # Portföy simülasyonu
    final_bal, max_dd, skipped = eng.simulate_portfolio(all_trades)
    profit_pct = (final_bal - eng.INITIAL_BALANCE) / eng.INITIAL_BALANCE * 100

    # Basit Sharpe proxy: ortalama PnL / stddev PnL
    import numpy as np
    pnls = np.array([t['pnl_pct'] for t in all_trades])
    avg_pnl = np.mean(pnls)
    std_pnl = np.std(pnls) if np.std(pnls) > 0 else 1
    sharpe = avg_pnl / std_pnl

    # İşlem türü dağılımı
    result_dist = {}
    for t in all_trades:
        r = t['result']
        result_dist[r] = result_dist.get(r, 0) + 1

    return {
        'params': params,
        'total': total,
        'win_rate': win_rate,
        'final': final_bal,
        'profit_pct': profit_pct,
        'max_dd': max_dd,
        'skipped': skipped,
        'sharpe': sharpe,
        'result_dist': result_dist,
        'avg_pnl': avg_pnl
    }


def main():
    combos = generate_combos(PARAM_GRID)
    print("=" * 70)
    print("🔬 BACKTEST PARAMETER OPTIMIZER")
    print("=" * 70)
    print(f"📊 Test edilecek kombinasyon: {len(combos)}")
    print(f"📅 Tarih: {eng.BACKTEST_START.date()} → {eng.BACKTEST_END.date()}")
    print()

    results = []
    start = time.time()

    for idx, params in enumerate(combos, 1):
        decay_str = f"Decay={params['DECAY_RATIO']}" if params['SIGNAL_DECAY_EXIT'] else "Decay=OFF"
        label = (
            f"SL={params['SL_ATR_MULT']} | "
            f"HSL={params['HARD_STOP_LOSS_PCT']}% | "
            f"Skor={params['SCORE_THRESHOLD']} | "
            f"CD={params['COOLDOWN_CANDLES']} | "
            f"{decay_str}"
        )
        print(f"\n[{idx}/{len(combos)}] {label}")
        print("-" * 50)

        result = run_single_backtest(params)
        results.append(result)

        emoji = "✅" if result['profit_pct'] > 0 else "❌"
        print(
            f"  {emoji} İşlem: {result['total']} | "
            f"WR: {result['win_rate']:.1f}% | "
            f"Final: ${result['final']:.0f} ({result['profit_pct']:+.1f}%) | "
            f"DD: {result['max_dd']:.1f}% | "
            f"Sharpe: {result['sharpe']:.3f}"
        )

    elapsed = time.time() - start

    # Sonuçları sırala (profit_pct'ye göre, drawdown penalty ile)
    # Skor = profit_pct - (max_dd * 0.5) → Kârlı ve düşük DD olan kazanır
    for r in results:
        r['composite'] = r['profit_pct'] - (r['max_dd'] * 0.3)

    results.sort(key=lambda x: x['composite'], reverse=True)

    # TOP 10
    print("\n")
    print("=" * 70)
    print("🏆 EN İYİ 10 KOMBİNASYON (Kâr - DD*0.3)")
    print("=" * 70)

    for i, r in enumerate(results[:10], 1):
        p = r['params']
        decay_str = f"Decay={p['DECAY_RATIO']}" if p['SIGNAL_DECAY_EXIT'] else "Decay=OFF"
        medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"#{i}"

        print(
            f"\n{medal} Composite: {r['composite']:+.1f} | "
            f"Kâr: {r['profit_pct']:+.1f}% | "
            f"DD: {r['max_dd']:.1f}% | "
            f"WR: {r['win_rate']:.1f}% | "
            f"İşlem: {r['total']} | "
            f"Sharpe: {r['sharpe']:.3f}"
        )
        print(
            f"   SL_ATR={p['SL_ATR_MULT']} | "
            f"HSL={p['HARD_STOP_LOSS_PCT']}% | "
            f"Skor={p['SCORE_THRESHOLD']} | "
            f"CD={p['COOLDOWN_CANDLES']} | "
            f"{decay_str}"
        )
        if 'result_dist' in r:
            dist = r['result_dist']
            top3 = sorted(dist.items(), key=lambda x: -x[1])[:4]
            dist_str = " | ".join([f"{k}:{v}" for k, v in top3])
            print(f"   Dağılım: {dist_str}")

    # EN KÖTÜ 3
    print(f"\n{'='*70}")
    print("💀 EN KÖTÜ 3 KOMBİNASYON")
    print("=" * 70)
    for r in results[-3:]:
        p = r['params']
        decay_str = f"Decay={p['DECAY_RATIO']}" if p['SIGNAL_DECAY_EXIT'] else "Decay=OFF"
        print(
            f"  ❌ Kâr: {r['profit_pct']:+.1f}% | DD: {r['max_dd']:.1f}% | "
            f"SL={p['SL_ATR_MULT']} | HSL={p['HARD_STOP_LOSS_PCT']}% | "
            f"Skor={p['SCORE_THRESHOLD']} | {decay_str}"
        )

    print(f"\n⏱️ Toplam süre: {elapsed:.0f}s ({elapsed/60:.1f}m)")
    print(f"{'='*70}")

    # En iyi parametreleri öner
    best = results[0]
    bp = best['params']
    print(f"\n🎯 ÖNERİLEN PARAMETRELER:")
    print(f"   SIGNAL_DECAY_EXIT = {bp['SIGNAL_DECAY_EXIT']}")
    print(f"   DECAY_RATIO = {bp['DECAY_RATIO']}")
    print(f"   HARD_STOP_LOSS_PCT = {bp['HARD_STOP_LOSS_PCT']}")
    print(f"   SL_ATR_MULT = {bp['SL_ATR_MULT']}")
    print(f"   SCORE_THRESHOLD = {bp['SCORE_THRESHOLD']}")
    print(f"   COOLDOWN_CANDLES = {bp['COOLDOWN_CANDLES']}")


if __name__ == "__main__":
    main()
