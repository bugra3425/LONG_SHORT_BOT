"""
==============================================================================
PUMP & DUMP REVERSION STRATEGY
Tarih : 18 Şubat 2026
Geliştirici: Buğra Türkoğlu
18.02.2026.py'den doğrudan import edilir - Orjinal strateji korunmuştur
==============================================================================
"""
import sys
from pathlib import Path

# Ana dosyayı import et
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# 18.02.2026.py içindeki tüm sınıf ve fonksiyonları import et
try:
    from importlib.machinery import SourceFileLoader
    
    main_strategy_path = project_root / "18.02.2026.py"
    loader = SourceFileLoader("main_strategy", str(main_strategy_path))
    main_strategy = loader.load_module()
    
    # Export all classes and functions
    PumpSnifferBot = main_strategy.PumpSnifferBot
    Config = main_strategy.Config
    WatchlistItem = main_strategy.WatchlistItem
    TradeRecord = main_strategy.TradeRecord
    Backtester = main_strategy.Backtester
    FullUniverseBacktester = main_strategy.FullUniverseBacktester
    
    # Export helper functions
    calc_bollinger_bands = main_strategy.calc_bollinger_bands
    calc_rsi = main_strategy.calc_rsi
    calc_volume_avg = main_strategy.calc_volume_avg
    
    __all__ = [
        'PumpSnifferBot', 'Config', 'WatchlistItem', 'TradeRecord',
        'Backtester', 'FullUniverseBacktester',
        'calc_bollinger_bands', 'calc_rsi', 'calc_volume_avg'
    ]
    
except Exception as e:
    print(f"❌ Ana strateji dosyası (18.02.2026.py) yüklenemedi: {e}")
    print(f"Dosya konumu: {main_strategy_path}")
    raise
