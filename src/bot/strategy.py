import pandas as pd
import pandas_ta as ta
import logging
from .config import MOMENTUM_THRESHOLD_PCT, VOLUME_THRESHOLD_MUL, SL_ATR_MULT, TP1_RR, TP2_RR, TP3_RR

logger = logging.getLogger("strategy")

class Strategy:
    """
    ⚡ MOMENTUM SCALPING STRATEGY
    Anlık fiyat hareketlerini ve hacim patlamalarını yakalar.
    """

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Gerekli indikatörleri hesaplar. 
        Momentum için ATR ve MA gibi yardımcı veriler eklenebilir.
        """
        if df is None or df.empty:
            return df

        # ATR (SL hesabı için gerekli)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        # Hacim Ortalaması (Patlama tespiti için)
        df['vol_ma'] = ta.sma(df['volume'], length=20)
        
        return df

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> dict:
        """
        Mum verilerini analiz eder ve sinyal üretir.
        
        Sinyal formatı:
        {
            'symbol': 'BTCUSDT',
            'side': 'LONG' | 'SHORT' | 'WAIT',
            'entry_price': 123.45,
            'sl': 120.0,
            'tp1': 125.0,
            ...
        }
        """
        if df is None or len(df) < 20:
            return {'side': 'WAIT'}

        last_candle = df.iloc[-1]
        
        # 🟢 LONG/SHORT ŞARTLARI
        # 1. Mum gövdesi % threshold'dan büyük mü?
        body_pct = (last_candle['close'] - last_candle['open']) / last_candle['open'] * 100
        
        # 2. Hacim ortalamanın üzerinde mi? (Son 20 mumun ortalaması)
        vol_ma = df['vol_ma'].iloc[-1]
        vol_spike = last_candle['volume'] > (vol_ma * VOLUME_THRESHOLD_MUL)
        
        side = 'WAIT'
        reason = ""

        if body_pct >= MOMENTUM_THRESHOLD_PCT and vol_spike:
            side = 'LONG'
            reason = f"🚀 Momentum: %{body_pct:.2f} yükseliş + Hacim Patlaması"
        
        elif body_pct <= -MOMENTUM_THRESHOLD_PCT and vol_spike:
            side = 'SHORT'
            reason = f"🔻 Momentum: %{body_pct:.2f} düşüş + Hacim Patlaması"

        if side == 'WAIT':
            return {'side': 'WAIT'}

        # SL / TP Hesaplama
        price = last_candle['close']
        atr = last_candle['atr'] or (price * 0.01) # Default %1 if ATR fails
        
        risk = atr * SL_ATR_MULT
        
        if side == 'LONG':
            sl = price - risk
            tp1 = price + (risk * TP1_RR)
            tp2 = price + (risk * TP2_RR)
            tp3 = price + (risk * TP3_RR)
        else:
            sl = price + risk
            tp1 = price - (risk * TP1_RR)
            tp2 = price - (risk * TP2_RR)
            tp3 = price - (risk * TP3_RR)

        return {
            'symbol': symbol,
            'side': side,
            'entry_price': price,
            'sl': sl,
            'tp1': tp1,
            'tp2': tp2,
            'tp3': tp3,
            'reason': reason
        }
