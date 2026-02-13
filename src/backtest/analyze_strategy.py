import pandas as pd

df = pd.read_csv('backtest_positions.csv', sep=';', decimal=',')

total = len(df)
wins = df[df['total_pnl_usd'] > 0]
losses = df[df['total_pnl_usd'] <= 0]

print(f"=== GENEL İSTATİSTİKLER ===")
print(f"Toplam Pozisyon: {total}")
print(f"Kazanan: {len(wins)} ({len(wins)/total*100:.1f}%)")
print(f"Kaybeden: {len(losses)} ({len(losses)/total*100:.1f}%)")
print(f"Toplam Kâr (kazananlar): ${wins['total_pnl_usd'].sum():.2f}")
print(f"Toplam Zarar (kaybedenler): ${losses['total_pnl_usd'].sum():.2f}")
print(f"Net: ${df['total_pnl_usd'].sum():.2f}")
print(f"Ort Kazanç: ${wins['total_pnl_usd'].mean():.2f}")
print(f"Ort Zarar: ${losses['total_pnl_usd'].mean():.2f}")

# Coin bazlı analiz
print(f"\n=== COİN BAZLI PERFORMANS ===")
coin_stats = df.groupby('symbol').agg(
    trades=('total_pnl_usd', 'count'),
    wins=('total_pnl_usd', lambda x: (x > 0).sum()),
    total_pnl=('total_pnl_usd', 'sum'),
    avg_pnl=('total_pnl_usd', 'mean'),
).reset_index()
coin_stats['win_rate'] = (coin_stats['wins'] / coin_stats['trades'] * 100).round(1)
coin_stats = coin_stats.sort_values('total_pnl')

print("\n--- EN KÖTÜ 10 COİN ---")
for _, r in coin_stats.head(10).iterrows():
    print(f"  {r['symbol']}: {r['trades']} işlem | WR: {r['win_rate']}% | NET: ${r['total_pnl']:.2f}")

print("\n--- EN İYİ 10 COİN ---")
for _, r in coin_stats.tail(10).iterrows():
    print(f"  {r['symbol']}: {r['trades']} işlem | WR: {r['win_rate']}% | NET: ${r['total_pnl']:.2f}")

# Result türüne göre analiz
print(f"\n=== SONUÇ TİPİ ANALİZİ ===")
# STOP LOSS vs TP pozisyon sayısı
stop_only = df[df['results'].str.contains('STOP LOSS', na=False) & ~df['results'].str.contains('TP', na=False)]
tp_reached = df[df['results'].str.contains('TP', na=False)]
trailing_only = df[df['results'].str.contains('TRAILING', na=False) & ~df['results'].str.contains('TP3', na=False)]
full_tp = df[df['results'].str.contains('TP3', na=False) | df['results'].str.contains('TP2 (30%), TP3', na=False)]

print(f"Sadece STOP LOSS: {len(stop_only)} ({len(stop_only)/total*100:.1f}%) | Ort: ${stop_only['total_pnl_usd'].mean():.2f}")
print(f"TP'ye ulaşan: {len(tp_reached)} ({len(tp_reached)/total*100:.1f}%) | Ort: ${tp_reached['total_pnl_usd'].mean():.2f}")
print(f"TP3'e ulaşan: {len(full_tp)} ({len(full_tp)/total*100:.1f}%) | Ort: ${full_tp['total_pnl_usd'].mean():.2f}")

# Art arda kayıp analizi
print(f"\n=== ART ARDA KAYIP SERİLERİ (Coin bazlı) ===")
for sym in df['symbol'].unique():
    coin_df = df[df['symbol'] == sym].reset_index(drop=True)
    max_streak = 0
    streak = 0
    for _, row in coin_df.iterrows():
        if row['total_pnl_usd'] <= 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    if max_streak >= 5:
        print(f"  ⚠️  {sym}: {max_streak} art arda kayıp!")

# Aynı giriş zamanında birden fazla coin (Korelasyon riski)
print(f"\n=== EŞ ZAMANLI GİRİŞ ANALİZİ ===")
entry_counts = df.groupby('entry_time').size()
multi_entries = entry_counts[entry_counts >= 4]
if len(multi_entries) > 0:
    print(f"  4+ pozisyonun aynı anda açıldığı zamanlar: {len(multi_entries)}")
    for t, c in multi_entries.head(5).items():
        coins = df[df['entry_time'] == t]['symbol'].tolist()
        results = df[df['entry_time'] == t]['total_pnl_usd'].sum()
        print(f"    {t}: {c} pozisyon | NET: ${results:.2f}")
        
# Bakiye düşüş analizi (Drawdown)
print(f"\n=== BAKİYE DÜŞÜŞ ANALİZİ ===")
balance_start = df.iloc[0]['balance_at_start']
peak = balance_start
max_dd = 0
max_dd_peak = 0
for _, row in df.iterrows():
    bal = row['balance_at_start']
    if bal > peak:
        peak = bal
    dd = (peak - bal) / peak * 100
    if dd > max_dd:
        max_dd = dd
        max_dd_peak = peak
print(f"Max Drawdown: %{max_dd:.1f} (Tepe: ${max_dd_peak:.2f})")
