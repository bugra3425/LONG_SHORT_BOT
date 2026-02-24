"""
Verilen bir coini botun TÜM giriş filtrelerine göre analiz eder.
Kullanım: python _analyze_coin.py STEEM
"""
import asyncio
import sys
import socket
import aiohttp
import ccxt.async_support as ccxt
from datetime import datetime, timezone

SYMBOL_BASE = sys.argv[1].upper() if len(sys.argv) > 1 else "STEEM"
SYMBOL_SPOT = f"{SYMBOL_BASE}/USDT"
SYMBOL_F    = f"{SYMBOL_BASE}/USDT:USDT"

# --- Bot Konfig eşikleri ---
PUMP_MIN_GREEN   = 4
PUMP_MIN_PCT     = 30.0
ANTI_ROCKET_PCT  = 30.0
RED_BODY_MIN_PCT = 2.0

async def analyze():
    connector = aiohttp.TCPConnector(
        family=socket.AF_INET,
        resolver=aiohttp.AsyncResolver(nameservers=["8.8.8.8"]),
    )
    ex = ccxt.binance({
        "options": {"defaultType": "future"},
        "session": aiohttp.ClientSession(connector=connector),
    })
    await ex.load_markets()

    if SYMBOL_F not in ex.markets:
        print(f"HATA: {SYMBOL_F} Binance Futures'ta yok!")
        await ex.close(); return

    # 8 mum al (canlı mum dahil)
    ohlcv  = await ex.fetch_ohlcv(SYMBOL_F, "4h", limit=8)
    ticker = await ex.fetch_ticker(SYMBOL_F)
    mark   = float(ticker.get("mark") or ticker.get("last") or 0)
    vol24h = float(ticker.get("quoteVolume") or 0)

    # Canlı mum tespiti
    last_ts    = ohlcv[-1][0]
    now_ms     = datetime.now(timezone.utc).timestamp() * 1000
    candle_end = last_ts + (4 * 3600 * 1000)
    is_live    = now_ms < candle_end
    remaining  = max(0, (candle_end - now_ms) / 60000)

    # 6 kapanmış mum
    closed = ohlcv[-7:-1] if is_live else ohlcv[-6:]

    def ts(ms):
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%m-%d %H:%M")

    print()
    print("=" * 72)
    print(f"  {SYMBOL_F}  —  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Mark Price: {mark:.6f}  |  24H Hacim: {vol24h:,.0f} USDT")
    print("=" * 72)

    # ── 6 kapanmış mum tablosu ──────────────────────────────────────────
    print(f"\n  {'#':<3} {'Zaman':<14} {'Açılış':>10} {'Kapanış':>10} "
          f"{'High':>10} {'Low':>10}  {'Renk':<10} {'Gövde%':>7}")
    print("  " + "-" * 70)
    green_count = 0
    highs, lows = [], []
    for i, c in enumerate(closed, 1):
        color  = "YEŞİL  🟢" if c[4] > c[1] else "KIRMIZI 🔴"
        body   = (c[4] - c[1]) / c[1] * 100 if c[1] > 0 else 0
        marker = "  ← SON KAPANAN" if i == len(closed) else ""
        if c[4] > c[1]: green_count += 1
        highs.append(c[2]); lows.append(c[3])
        print(f"  {i:<3} {ts(c[0]):<14} {c[1]:>10.6f} {c[4]:>10.6f} "
              f"{c[2]:>10.6f} {c[3]:>10.6f}  {color:<12} {body:>+6.1f}%{marker}")

    # canlı mum
    lc = ohlcv[-1]
    lc_color = "YEŞİL  🟢" if lc[4] > lc[1] else "KIRMIZI 🔴"
    lc_body  = (lc[4] - lc[1]) / lc[1] * 100 if lc[1] > 0 else 0
    print(f"  {'C':<3} {ts(lc[0]):<14} {lc[1]:>10.6f} {lc[4]:>10.6f} "
          f"{lc[2]:>10.6f} {lc[3]:>10.6f}  {lc_color:<12} {lc_body:>+6.1f}%"
          f"  ← CANLI (kapanışa {remaining:.0f} dk)")

    pump_high = max(highs)
    pump_low  = min(lows)
    pump_pct  = (pump_high - pump_low) / pump_low * 100

    print(f"\n  Pump zirve: {pump_high:.6f}  |  Pump dip: {pump_low:.6f}  |  Net pump: {pump_pct:.2f}%")

    # ── FİLTRE 1: detect_pump ─────────────────────────────────────────
    print("\n" + "─" * 72)
    print("  FİLTRE 1 — DETECT_PUMP (watchlist'e girme koşulu)")
    print("─" * 72)
    f1a = green_count >= PUMP_MIN_GREEN
    f1b = pump_pct >= PUMP_MIN_PCT
    # Retained gain: son kapanan mumun kapanışı hâlâ dipten %70×PUMP_MIN_PCT yukarıda mı?
    last_close     = closed[-1]["close"]
    retained_gain  = (last_close - pump_low) / pump_low * 100.0
    min_retained   = PUMP_MIN_PCT * 0.70   # 30% * 0.70 = 21%
    f1c = retained_gain >= min_retained
    print(f"  {'✅' if f1a else '❌'}  Yeşil mum >= {PUMP_MIN_GREEN}           →  {green_count}/6")
    print(f"  {'✅' if f1b else '❌'}  Net pump  >= %{PUMP_MIN_PCT:.0f}         →  {pump_pct:.2f}%")
    print(f"  {'✅' if f1c else '❌'}  Retained gain >= %{min_retained:.0f}   →  dipten %{retained_gain:.1f} korunmuş"
          f"{'  (tren kaçmış!)' if not f1c else ''}")
    pump_ok = f1a and f1b and f1c

    # ── FİLTRE 2: ANTI-ROCKET (son kapanan mum) ───────────────────────
    print("\n" + "─" * 72)
    print("  FİLTRE 2 — ANTI-ROCKET (tetikleyiciden önceki mum)")
    print("─" * 72)
    prev   = closed[-1]
    prev_b = (prev[4] - prev[1]) / prev[1] * 100 if prev[1] > 0 else 0
    prev_green = prev[4] > prev[1]
    f2a = prev_green
    f2b = prev_b < ANTI_ROCKET_PCT
    print(f"  {'✅' if f2a else '❌'}  Önceki mum YEŞİL olmalı        →  {'YEŞİL' if prev_green else 'KIRMIZI'} ({prev_b:+.1f}%)")
    print(f"  {'✅' if f2b else '❌'}  Önceki mum gövdesi < %{ANTI_ROCKET_PCT:.0f}     →  {prev_b:+.1f}%"
          f"  {'(ANTI-ROCKET! Giriş engellenir)' if not f2b else ''}")
    anti_ok = f2a and f2b

    # ── FİLTRE 3: check_entry_signal (tetikleyici kırmızı mum) ────────
    print("\n" + "─" * 72)
    print("  FİLTRE 3 — CHECK_ENTRY_SIGNAL (tetikleyici — sonraki 4H kapanış)")
    print("─" * 72)
    trig_close = float(lc[4])
    trig_open  = float(lc[1])
    is_red     = trig_close < trig_open
    red_body   = (trig_open - trig_close) / trig_open * 100 if is_red and trig_open > 0 else 0
    f3a = is_red
    f3b = red_body >= RED_BODY_MIN_PCT if is_red else False
    f3c = trig_close < pump_high if is_red else False
    print(f"  {'✅' if f3a else '⏳'}  Canlı mum KIRMIZI kapanacak     →  Şu an {lc_color.strip()}  ({lc_body:+.1f}%,  {remaining:.0f} dk kaldı)")
    if is_red:
        print(f"  {'✅' if f3b else '❌'}  Kırmızı gövde >= %{RED_BODY_MIN_PCT:.0f}           →  {red_body:.1f}%")
        print(f"  {'✅' if f3c else '❌'}  Kapanış < Pump zirve           →  {trig_close:.6f} vs {pump_high:.6f}")
    else:
        print(f"  ⏳  Mum henüz kapanmadı — {remaining:.0f} dk sonra netleşecek")
    entry_ok = is_red and f3b and f3c

    # ── ÖZET ───────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  ÖZET")
    print("=" * 72)
    print(f"  {'✅' if pump_ok  else '❌'}  FİLTRE 1 — Watchlist (detect_pump)")
    print(f"  {'✅' if anti_ok  else '❌'}  FİLTRE 2 — Anti-rocket")
    print(f"  {'✅' if entry_ok else '⏳'}  FİLTRE 3 — Giriş sinyali (tetikleyici)")

    if pump_ok and anti_ok and entry_ok:
        print(f"\n  🚀 TÜM KOŞULLAR SAĞLANDI — BOT SHORT AÇAR!")
    elif pump_ok and anti_ok and not entry_ok:
        next_close = datetime.fromtimestamp(candle_end / 1000, tz=timezone.utc).strftime("%H:%M UTC")
        print(f"\n  ⏳ Watchlist'te — {next_close} kapanışı bekleniyor ({remaining:.0f} dk)")
    else:
        print(f"\n  ❌ Koşullar sağlanmıyor — giriş yok")
    print("=" * 72 + "\n")

    await ex.close()

asyncio.run(analyze())
