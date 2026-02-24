"""2 günlük backtest: 22.02.2026 08:00 -> 24.02.2026 08:00 UTC"""
import asyncio
import sys
import os
from datetime import datetime, timezone

# canlı işlem klasörünü path'e ekle
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "canlı işlem"))

# Ana modülü import et
os.chdir(os.path.dirname(__file__))

# Modülü doğrudan çalıştır
import importlib.util
spec = importlib.util.spec_from_file_location(
    "bot_module",
    os.path.join("canlı işlem", "18.02.2026.py"),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

start_dt = datetime(2026, 2, 22, 8, 0, 0, tzinfo=timezone.utc)
end_dt   = datetime(2026, 2, 24, 8, 0, 0, tzinfo=timezone.utc)

print(f"\n{'='*60}")
print(f"  2 GÜNLÜK BACKTEST")
print(f"  {start_dt.strftime('%d.%m.%Y %H:%M')} → {end_dt.strftime('%d.%m.%Y %H:%M')} UTC")
print(f"  Full Universe (tüm USDT-M futures)")
print(f"{'='*60}\n")

asyncio.run(mod.main_backtest(full_universe=True, start_dt=start_dt, end_dt=end_dt))
