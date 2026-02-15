"""
UZUN VADELİ BOT - Apex Sniper Stratejisi
Dosya: uzun_vadeli_bot.py
Tarih: 15 Şubat 2026
Strateji: 4H Teknik Analiz + Fibonacci Retracement + Bearish Divergence
Timeframe: 4 saatlik mumlar
Hedef: Üst banddan SHORT fırsatları

Özellikler:
    • Top 150 hacim, ilk 40 gainer hariç (parabolik coinlerden uzak)
    • BTC Shield: BTC 15dk'da %2+ zıplarsa tüm shortları kapat
    • Fibonacci onaylı giriş/çıkış noktaları
    • TP1 (Fib 0.5): %50 pozisyon kapat + SL breakeven'e
    • TP2 (Fib 0.618 - Golden Pocket): Kalan %50 kapat
    • BTC Korelasyonlu Dinamik TP: BTC düşüşünde TP'yi Fib 1.0'a uzaklaştır
    • BTC Emergency Flip: BTC 15dk'da %1.5+ yeşil mum -> acil kapat
    • 5 Basamaklı Onay Sistemi (MACD, EMA200, Fib, RSI/MFI, Volume)
    • Göstergeler: BB, RSI, MFI, ATR, EMA200, MACD
    • Bearish Divergence tespiti
    • Her 10 dakikada tarama
    • API key GEREKLİ!
    
Kullanım:
    python uzun_vadeli_bot.py
"""
import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import pandas_ta as ta
import logging
import sys
import time
from datetime import datetime

# --- LOG AYARLARI ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- KONFİGÜRASYON YÜKLEME ---
def load_config():
    """config.py dosyasından API anahtarlarını yükle (varsa)"""
    try:
        import config
        return config.BINANCE_API_KEY, config.BINANCE_API_SECRET
    except ImportError:
        return None, None
    except AttributeError:
        return None, None

class BugraBotApex:
    """
    Apex Sniper Bot - Teknik Analiz Odaklı SHORT Stratejisi
    
    Özellikler:
    - Top 150 hacim, ilk 40 gainer hariç (parabolik coinlerden uzak)
    - BTC Shield: BTC 15dk'da %2+ zıplarsa tüm shortları kapat
    - Göstergeler: Bollinger Bands, RSI, MFI, ATR, EMA200
    - Ayı Uyumsuzluğu (Bearish Divergence) tespiti
    - 4H timeframe - Daha sağlam sinyaller
    """
    
    def __init__(self, api_key, api_secret):
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'options': {'defaultType': 'future'},
            'enableRateLimit': True,
            'timeout': 30000,  # 30 saniye timeout
            'rateLimit': 50,
        })
        self.timeframe = '4h'
        self.leverage = 5
        self.max_active_trades = 4
        self.active_trades = {}
        self.cooldowns = {}
        self.btc_panic = False
        
        # Connection retry
        self.max_retries = 3
        self.retry_delay = 5
    
    async def test_connection(self):
        """API bağlantısını ve kimlik bilgilerini test et"""
        try:
            # API anahtarını test et
            balance = await self.exchange.fetch_balance()
            logging.info("✅ API bağlantısı başarılı!")
            logging.info(f"📊 Hesap durumu: {balance.get('USDT', {}).get('free', 0):.2f} USDT serbest")
            return True
        except ccxt.AuthenticationError as e:
            logging.error("❌ API kimlik doğrulama hatası!")
            logging.error("   • API Key ve Secret'ı kontrol edin")
            logging.error("   • Binance'de API izinlerini kontrol edin (Futures)")
            logging.error(f"   • Hata detayı: {e}")
            return False
        except Exception as e:
            logging.error(f"❌ Bağlantı testi başarısız: {e}")
            return False

    async def fetch_eligible_symbols(self):
        """Top 150 Hacim - İlk 40 Gainer Hariç Filtreleme"""
        tickers = await self.exchange.fetch_tickers()
        futures_data = [t for t in tickers.values() if '/USDT' in t['symbol'] and t['quoteVolume'] > 30_000_000]
        
        # Hacme göre ilk 150'yi al
        top_150 = sorted(futures_data, key=lambda x: x['quoteVolume'], reverse=True)[:150]
        
        # Yüzde artışına göre sırala ve ilk 40 gainer'ı (parabolik) ele
        sorted_by_gain = sorted(top_150, key=lambda x: x['percentage'], reverse=True)
        eligible = [t['symbol'] for t in sorted_by_gain[40:]]  # İlk 40 gainer elendi
        
        return eligible

    async def check_btc_shield(self):
        """BTC 15dk'lık fiyatta %2 zıplarsa tüm SHORT'ları kapat."""
        ohlcv = await self.exchange.fetch_ohlcv('BTC/USDT', timeframe='15m', limit=2)
        change = (ohlcv[1][4] - ohlcv[0][1]) / ohlcv[0][1]
        if change >= 0.02:
            logging.warning(f"⚠️ BTC ANLIK SIÇRAMA (%{change*100:.2f})! ACİL DURUM KAPATMASI!")
            return True
        return False

    async def check_btc_trend(self):
        """
        BTC Trend Teyidi (BTC Trend Confirmation)
        
        Her 10 dakikada BTC/USDT'yi 4H ve 1H'da kontrol eder.
        Eğer BTC hem 4H hem 1H'da EMA 200 altındaysa ve son mum kırmızıysa,
        piyasa 'Aşırı Ayı' (Extreme Bearish) modundadır.
        
        Returns:
            dict: {
                'mode': 'extreme_bearish' | 'bearish' | 'bullish' | 'extreme_bullish' | 'neutral',
                'btc_4h_below_ema200': bool,
                'btc_1h_below_ema200': bool,
                'btc_4h_red': bool,
                'btc_1h_red': bool,
                'btc_1h_change': float  # Son 1H mumun değişim yüzdesi
            }
        """
        try:
            # 4H grafiği
            ohlcv_4h = await self.exchange.fetch_ohlcv('BTC/USDT', timeframe='4h', limit=201)
            df_4h = pd.DataFrame(ohlcv_4h, columns=['t', 'o', 'h', 'l', 'c', 'v'])
            df_4h['ema200'] = ta.ema(df_4h['c'], length=200)
            
            # 1H grafiği
            ohlcv_1h = await self.exchange.fetch_ohlcv('BTC/USDT', timeframe='1h', limit=201)
            df_1h = pd.DataFrame(ohlcv_1h, columns=['t', 'o', 'h', 'l', 'c', 'v'])
            df_1h['ema200'] = ta.ema(df_1h['c'], length=200)
            
            # Son mumlar
            curr_4h = df_4h.iloc[-1]
            curr_1h = df_1h.iloc[-1]
            
            # Kontroller
            btc_4h_below_ema200 = curr_4h['c'] < curr_4h['ema200']
            btc_1h_below_ema200 = curr_1h['c'] < curr_1h['ema200']
            btc_4h_red = curr_4h['c'] < curr_4h['o']
            btc_1h_red = curr_1h['c'] < curr_1h['o']
            btc_1h_change = (curr_1h['c'] - curr_1h['o']) / curr_1h['o']
            
            # 4H değişim kontrolü (boğa trendi tespiti için)
            btc_4h_change = (curr_4h['c'] - df_4h.iloc[-2]['c']) / df_4h.iloc[-2]['c']
            btc_4h_above_ema200 = curr_4h['c'] > curr_4h['ema200']
            
            # Mod Tespiti
            mode = 'neutral'
            
            # Aşırı Ayı: Hem 4H hem 1H EMA200 altında + son mumlar kırmızı
            if btc_4h_below_ema200 and btc_1h_below_ema200 and btc_4h_red and btc_1h_red:
                mode = 'extreme_bearish'
            # Ayı: 1H EMA200 altında veya 4H kırmızı
            elif btc_1h_below_ema200 or btc_4h_red:
                mode = 'bearish'
            # Aşırı Boğa: 4H EMA200 üstü + %2+ yükseliş
            elif btc_4h_above_ema200 and btc_4h_change >= 0.02:
                mode = 'extreme_bullish'
            # Boğa: 4H EMA200 üstü veya 1H yeşil
            elif btc_4h_above_ema200 or not btc_1h_red:
                mode = 'bullish'
            
            return {
                'mode': mode,
                'btc_4h_below_ema200': btc_4h_below_ema200,
                'btc_1h_below_ema200': btc_1h_below_ema200,
                'btc_4h_red': btc_4h_red,
                'btc_1h_red': btc_1h_red,
                'btc_1h_change': btc_1h_change,
                'btc_4h_change': btc_4h_change,
                'btc_price': curr_1h['c']
            }
            
        except Exception as e:
            logging.warning(f"⚠️ BTC trend kontrolü başarısız: {str(e)[:50]}")
            return {'mode': 'neutral', 'btc_1h_change': 0}

    async def check_btc_emergency_flip(self):
        """
        BTC Acil Durum Kontrolü (Emergency Flip)
        
        SHORT pozisyon varken BTC 15 dakikalık grafikte sert bir boğa mumu (%1.5+) 
        yakarsa, altcoinlerin kârda olup olmadığına bakmaksızın pozisyonu piyasa 
        fiyatından kapat.
        
        Returns:
            bool: Emergency flip tetiklendi mi?
        """
        try:
            ohlcv = await self.exchange.fetch_ohlcv('BTC/USDT', timeframe='15m', limit=2)
            curr = ohlcv[-1]
            change = (curr[4] - curr[1]) / curr[1]  # close - open
            
            if change >= 0.015:  # %1.5+ yeşil mum
                logging.warning(f"🚨 BTC ACİL DURUM FLIP! 15m'de %{change*100:.1f} yeşil mum!")
                return True
            return False
            
        except Exception as e:
            logging.warning(f"⚠️ BTC Emergency Flip kontrolü başarısız: {str(e)[:50]}")
            return False

    async def get_indicators(self, symbol):
        ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe=self.timeframe, limit=100)
        df = pd.DataFrame(ohlcv, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        
        # Göstergeler
        bb = ta.bbands(df['c'], length=20, std=2)
        df['bb_upper'] = bb['BBU_20_2.0']
        df['bb_mid'] = bb['BBM_20_2.0']
        df['rsi'] = ta.rsi(df['c'], length=14)
        df['mfi'] = ta.mfi(df['h'], df['l'], df['c'], df['v'], length=14)
        df['atr'] = ta.atr(df['h'], df['l'], df['c'], length=14)
        df['ema200'] = ta.ema(df['c'], length=200)
        
        # MACD (12, 26, 9) - Trend yorgunluğu tespiti için
        macd = ta.macd(df['c'], fast=12, slow=26, signal=9)
        df['macd'] = macd['MACD_12_26_9']
        df['macd_signal'] = macd['MACDs_12_26_9']
        df['macd_hist'] = macd['MACDh_12_26_9']
        
        return df
    
    def calculate_fibonacci_levels(self, df, lookback=75):
        """
        Fibonacci Retracement seviyelerini hesapla (4H mumlar için).
        Son 50-100 mumdan Swing High/Low tespit eder.
        """
        # Son 75 mumu al (4H * 75 = yaklaşık 12.5 gün)
        recent_data = df.iloc[-lookback:] if len(df) >= lookback else df
        
        # Swing High (En yüksek tepe) ve Swing Low (En düşük dip)
        swing_high = recent_data['h'].max()
        swing_low = recent_data['l'].min()
        
        # Fark
        diff = swing_high - swing_low
        
        # Fibonacci seviyeleri (SHORT için - Yukarıdan aşağıya)
        fib_levels = {
            'peak': swing_high,  # 0% - Zirve
            'fib_0': swing_high,  # 0%
            'fib_236': swing_high - (diff * 0.236),  # 23.6%
            'fib_382': swing_high - (diff * 0.382),  # 38.2%
            'fib_500': swing_high - (diff * 0.500),  # 50% (TP1 hedefi)
            'fib_618': swing_high - (diff * 0.618),  # 61.8% (Golden Pocket - TP2)
            'fib_786': swing_high - (diff * 0.786),  # 78.6%
            'fib_1': swing_low,  # 100% - Dip
            'ext_1272': swing_high + (diff * 0.272),  # 127.2% Uzatma
            'ext_1618': swing_high + (diff * 0.618),  # 161.8% Uzatma
        }
        
        return fib_levels

    def check_divergence(self, df):
        """Ayı Uyumsuzluğu (Bearish Divergence) Kontrolü"""
        # Fiyat yeni bir yüksek yapıyor ama RSI bir önceki tepenin altında kalıyor mu?
        if df['c'].iloc[-1] > df['c'].iloc[-5:-1].max() and df['rsi'].iloc[-1] < df['rsi'].iloc[-10:-1].max():
            return True
        return False

    def check_signal(self, df, fib_levels):
        """
        BASAMAKLI ONAY SİSTEMİ (Step-by-Step Confirmation)
        Her basamak geçilmeden bir sonrakine gidilmez.
        Reddedilme nedeni loglanır.
        """
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # ========================================
        # BASAMAK 1: PİYASA ve HACİM FİLTRESİ (The Environment)
        # ========================================
        # İlk 150 hacimli coin, ilk 40 gainer ele - fetch_eligible_symbols() yapıyor
        
        # MACD Trend Yorgunluğu Kontrolü
        # MACD Histogram küçülüyor mu veya negatif mi?
        macd_hist_curr = curr['macd_hist']
        macd_hist_prev = df.iloc[-2]['macd_hist']
        macd_hist_declining = macd_hist_curr < macd_hist_prev  # Küçülüyor
        macd_hist_negative = macd_hist_curr < 0  # Negatif bölgede
        
        if not (macd_hist_declining or macd_hist_negative):
            logging.info(f"❌ Basamak 1: MACD histogram yorulmamış (hist: {macd_hist_curr:.4f})")
            return None
        
        # ========================================
        # BASAMAK 2: LOKASYON ve TREND ONAYI (The Territory)
        # ========================================
        # 1. Fiyat EMA 200 üzerinde mi?
        if curr['c'] < curr['ema200']:
            logging.info(f"❌ Basamak 2: Fiyat EMA200 altında (fiyat: {curr['c']:.2f}, EMA200: {curr['ema200']:.2f})")
            return None
        
        # 2. Fiyat Bollinger Üst Bandına dokunuyor mu?
        if curr['c'] < curr['bb_upper']:
            logging.info(f"❌ Basamak 2: Fiyat BB üst banda dokunmuyor (fiyat: {curr['c']:.2f}, BB üst: {curr['bb_upper']:.2f})")
            return None
        
        # ========================================
        # BASAMAK 3: MATEMATİKSEL ZİRVE ve FİBONACCI (The Harmonic Gate)
        # ========================================
        # Fibonacci seviyelerini kontrol et
        tolerance = 0.005  # %0.5
        
        # Fiyat Fibonacci 0, 1.272 veya 1.618 seviyelerine yakın mı?
        near_fib_0 = abs(curr['h'] - fib_levels['fib_0']) / fib_levels['fib_0'] < tolerance
        near_ext_1272 = abs(curr['h'] - fib_levels['ext_1272']) / fib_levels['ext_1272'] < tolerance
        near_ext_1618 = abs(curr['h'] - fib_levels['ext_1618']) / fib_levels['ext_1618'] < tolerance
        
        at_fibonacci_key_level = near_fib_0 or near_ext_1272 or near_ext_1618
        
        if not at_fibonacci_key_level:
            logging.info(f"❌ Basamak 3: Fiyat Fibonacci kritik seviyelerinde değil")
            return None
        
        # Trend Kırılımı: Kapanış Fib 0.236 ALTINDA mı?
        closed_below_fib236 = curr['c'] < fib_levels['fib_236']
        
        if not closed_below_fib236:
            logging.info(f"❌ Basamak 3: Fib 0.236 kırılmadı (kapanış: {curr['c']:.2f}, Fib 0.236: {fib_levels['fib_236']:.2f})")
            return None
        
        # ========================================
        # BASAMAK 4: MOMENTUM ve UYUMSUZLUK (The Exhaustion)
        # ========================================
        # 1. RSI > 60 ve MFI > 75 mi?
        if curr['rsi'] < 60:
            logging.info(f"❌ Basamak 4: RSI yeterli değil (RSI: {curr['rsi']:.1f})")
            return None
        
        if curr['mfi'] < 75:
            logging.info(f"❌ Basamak 4: MFI yeterli değil (MFI: {curr['mfi']:.1f})")
            return None
        
        # 2. Bearish Divergence var mı?
        if not self.check_divergence(df):
            logging.info(f"❌ Basamak 4: Bearish Divergence tespit edilemedi")
            return None
        
        # ========================================
        # BASAMAK 5: TETİKLEYİCİ ve HACİM PATLAMASI (The Trigger)
        # ========================================
        # Son mum KIRMIZI mı?
        is_red = curr['c'] < curr['o']
        if not is_red:
            logging.info(f"❌ Basamak 5: Son mum kırmızı değil (yeşil mum)")
            return None
        
        # Gövde %3'ten büyük mü?
        body_pct = abs(curr['c'] - curr['o']) / curr['o']
        if body_pct < 0.03:
            logging.info(f"❌ Basamak 5: Gövde yeterli büyük değil (gövde: %{body_pct*100:.2f})")
            return None
        
        # Hacim son 5 mumun ortalamasından 1.5 kat fazla mı?
        avg_volume = df['v'].iloc[-6:-1].mean()
        vol_spike = curr['v'] > (avg_volume * 1.5)
        
        if not vol_spike:
            logging.info(f"❌ Basamak 5: Hacim patlaması yok (hacim: {curr['v']:.0f}, ort: {avg_volume:.0f})")
            return None
        
        # ========================================
        # ✅ TÜM BASAMAKLAR BAŞARIYLA GEÇİLDİ!
        # ========================================
        logging.info("✅ BASAMAKLI ONAY SİSTEMİ: Tüm kriterler OK!")
        logging.info(f"   Basamak 1: MACD histogram {'negatif' if macd_hist_negative else 'düşüyor'} ✓")
        logging.info(f"   Basamak 2: Fiyat EMA200 üstünde + BB üst bandda ✓")
        logging.info(f"   Basamak 3: Fibonacci kritik seviyede + 0.236 kırıldı ✓")
        logging.info(f"   Basamak 4: RSI={curr['rsi']:.1f} MFI={curr['mfi']:.1f} + Divergence ✓")
        logging.info(f"   Basamak 5: Kırmızı mum + Gövde %{body_pct*100:.1f} + Hacim 1.5x ✓")
        
        # İki farklı sinyal tipi: Ani düşüş veya 2 mum onayı
        if body_pct >= 0.03 and vol_spike:
            return "SHORT_IMMEDIATE"
        elif is_red and df.iloc[-2]['c'] < df.iloc[-2]['o']:
            return "SHORT_CONFIRMED_2_CANDLES"

        return None

    async def open_position(self, symbol, signal, df, fib_levels):
        """
        Pozisyon aç - Fibonacci bazlı kademeli kar al sistemi.
        TP1: Fib 0.5 (%50 kapat + SL'yi breakeven'e çek)
        TP2: Fib 0.618 (Golden Pocket - kalan %50'yi kapat)
        SL: ATR*2 veya Fib 0 (peak) + %0.5 (hangisi daha güvenliyse)
        """
        try:
            curr = df.iloc[-1]
            entry_price = curr['c']
            atr = curr['atr']
            
            # TP1: Fibonacci 0.5 seviyesi (İlk hedef - %50 pozisyonu kapat)
            tp1_price = fib_levels['fib_500']
            
            # TP2: Fibonacci 0.618 (Golden Pocket - Kalan %50'yi kapat)
            tp2_price = fib_levels['fib_618']
            
            # Stop Loss Hesaplama:
            # Seçenek 1: ATR * 2 (klasik volatilite bazlı)
            sl_atr_based = entry_price + (atr * 2)
            
            # Seçenek 2: Fibonacci Peak + %0.5 (zirvenin biraz üstü)
            sl_fib_based = fib_levels['peak'] * 1.005
            
            # İkisinden daha güvenli olanı (yani giriş fiyatına daha yakın olanı) seç
            sl_price = min(sl_atr_based, sl_fib_based)
            
            # Risk/Reward hesapla (TP1 bazlı)
            risk = sl_price - entry_price
            reward_tp1 = entry_price - tp1_price
            reward_tp2 = entry_price - tp2_price
            rr_ratio_tp1 = reward_tp1 / risk if risk > 0 else 0
            rr_ratio_tp2 = reward_tp2 / risk if risk > 0 else 0
            
            logging.info(f"")
            logging.info(f"{'='*75}")
            logging.info(f"🎯 APEX SHORT - FİBONACCI KADEMELİ KÂR AL SİSTEMİ")
            logging.info(f"{'='*75}")
            logging.info(f"💰 Coin: {symbol}")
            logging.info(f"📊 Sinyal: {signal}")
            logging.info(f"💵 Giriş: ${entry_price:.6f}")
            logging.info(f"")
            logging.info(f"📐 FIBONACCI SEVİYELERİ (4H):")
            logging.info(f"   Peak (0%):    ${fib_levels['peak']:.6f}")
            logging.info(f"   Ext 161.8%:   ${fib_levels['ext_1618']:.6f}")
            logging.info(f"   Ext 127.2%:   ${fib_levels['ext_1272']:.6f}")
            logging.info(f"   Fib 0.236:    ${fib_levels['fib_236']:.6f}")
            logging.info(f"   Fib 0.382:    ${fib_levels['fib_382']:.6f}")
            logging.info(f"   Fib 0.500:    ${fib_levels['fib_500']:.6f} ← TP1")
            logging.info(f"   Fib 0.618:    ${fib_levels['fib_618']:.6f} ← TP2 (Golden Pocket)")
            logging.info(f"   Fib 0.786:    ${fib_levels['fib_786']:.6f}")
            logging.info(f"   Dip (100%):   ${fib_levels['fib_1']:.6f}")
            logging.info(f"")
            logging.info(f"🎯 KADEMELİ KÂR AL STRATEJİSİ:")
            logging.info(f"   TP1 (Fib 0.5):   ${tp1_price:.6f} → %50 pozisyon kapat + SL breakeven'e")
            logging.info(f"   TP2 (Fib 0.618): ${tp2_price:.6f} → Kalan %50 pozisyon kapat")
            logging.info(f"")
            logging.info(f"🛑 STOP LOSS:")
            logging.info(f"   ATR*2 bazlı:     ${sl_atr_based:.6f}")
            logging.info(f"   Fib Peak+0.5%:   ${sl_fib_based:.6f}")
            logging.info(f"   Seçilen SL:      ${sl_price:.6f} (%{((sl_price/entry_price-1)*100):.2f})")
            logging.info(f"")
            logging.info(f"📈 RİSK/REWARD:")
            logging.info(f"   TP1 R/R: 1:{rr_ratio_tp1:.2f}")
            logging.info(f"   TP2 R/R: 1:{rr_ratio_tp2:.2f}")
            logging.info(f"   Ortalama R/R: 1:{(rr_ratio_tp1 + rr_ratio_tp2)/2:.2f}")
            logging.info(f"")
            logging.info(f"📊 İNDİKATÖRLER:")
            logging.info(f"   RSI: {curr['rsi']:.1f} | MFI: {curr['mfi']:.1f}")
            logging.info(f"   ATR: ${atr:.6f}")
            logging.info(f"")
            logging.info(f"⚡ Kaldıraç: {self.leverage}x")
            logging.info(f"{'='*75}")
            logging.info(f"")
            
            # Pozisyon bilgilerini sakla
            self.active_trades[symbol] = {
                'entry': entry_price,
                'sl': sl_price,
                'tp1': tp1_price,
                'tp2': tp2_price,
                'original_tp2': tp2_price,  # Orijinal TP2 (Fib 0.618) - BTC dinamik TP için
                'signal': signal,
                'time': datetime.now(),
                'fib_levels': fib_levels,
                'quantity': 1.0,  # Başlangıç pozisyon boyutu (simülasyon)
                'tp1_hit': False,  # TP1'e ulaşıldı mı?
                'tp2_hit': False,  # TP2'ye ulaşıldı mı?
                'sl_moved_to_breakeven': False,  # SL breakeven'e çekildi mi?
                'dynamic_tp_active': False,  # BTC bazlı dinamik TP aktif mi?
                'last_btc_mode': 'neutral'  # Son BTC trend modu
            }
            
        except Exception as e:
            logging.error(f"❌ {symbol} pozisyon açma hatası: {e}")

    async def monitor_active_positions(self):
        """
        Aktif pozisyonları izle, TP1/TP2'ye ulaşanları kademeli kapat.
        TP1: %50 kapat + SL breakeven
        TP2: Kalan %50'yi kapat
        
        BTC Korelasyonlu Dinamik TP:
        - BTC 'Aşırı Ayı' modundaysa SHORT TP'yi Fib 1.0'a uzaklaştır
        - BTC yukarı dönerse TP'yi Fib 0.618'e geri çek
        """
        if not self.active_trades:
            return
        
        # BTC Trend Kontrolü (10 dakikada bir)
        btc_trend = await self.check_btc_trend()
        btc_mode = btc_trend['mode']
        
        # BTC Emergency Flip Kontrolü (SHORT pozisyonlar için)
        emergency_flip = await self.check_btc_emergency_flip()
        
        if emergency_flip and self.active_trades:
            logging.warning("🚨 BTC ACI DURUM FLIP - TÜM SHORT POZİSYONLAR KAPATILIYOR!")
            for symbol in list(self.active_trades.keys()):
                trade = self.active_trades[symbol]
                
                try:
                    ticker = await self.exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                    profit_pct = ((trade['entry'] - current_price) / trade['entry']) * 100
                    
                    logging.warning(f"   ❌ {symbol} ACİL KAPATMA (Piyasa: ${current_price:.6f}, Kar: %{profit_pct:.2f})")
                    del self.active_trades[symbol]
                    self.cooldowns[symbol] = time.time()
                    
                except Exception as e:
                    logging.error(f"⚠️ {symbol} acil kapatma hatası: {str(e)[:50]}")
            
            return
        
        for symbol in list(self.active_trades.keys()):
            try:
                trade = self.active_trades[symbol]
                
                # BTC Bazlı Dinamik TP Güncelleme (Sadece TP1 sonrası, TP2 öncesi)
                if trade['tp1_hit'] and not trade['tp2_hit']:
                    # Aşırı Ayı Modu: TP2'yi Fib 1.0'a uzaklaştır
                    if btc_mode == 'extreme_bearish' and not trade['dynamic_tp_active']:
                        old_tp2 = trade['tp2']
                        new_tp2 = trade['fib_levels']['fib_1']  # Fibonacci 1.0 (Tam Dip)
                        trade['tp2'] = new_tp2
                        trade['dynamic_tp_active'] = True
                        trade['last_btc_mode'] = btc_mode
                        
                        logging.info(f"📉 {symbol}: BTC düşüşü teyit edildi!")
                        logging.info(f"   TP2 güncellendi: ${old_tp2:.6f} → ${new_tp2:.6f} (Fib 1.0)")
                        logging.info(f"   💰 Kâr potansiyeli arttı!")
                    
                    # BTC Yukarı Döndü: TP2'yi güvenli seviyeye geri çek
                    elif btc_mode in ['bullish', 'extreme_bullish'] and trade['dynamic_tp_active']:
                        old_tp2 = trade['tp2']
                        # Güvenli çıkış: Orijinal Fib 0.618 veya BB Orta Bandı
                        new_tp2 = trade['original_tp2']  # Fib 0.618
                        trade['tp2'] = new_tp2
                        trade['dynamic_tp_active'] = False
                        trade['last_btc_mode'] = btc_mode
                        
                        logging.warning(f"📈 {symbol}: BTC yukarı döndü!")
                        logging.warning(f"   ⚠️ TP2 güvenli seviyeye çekildi: ${old_tp2:.6f} → ${new_tp2:.6f}")
                        logging.warning(f"   🛡️ Kar koruma modu aktif")
                
                # Güncel fiyatı al
                ticker = await self.exchange.fetch_ticker(symbol)
                current_price = ticker['last']
                
                # TP1 Kontrolü (Fib 0.5)
                if not trade['tp1_hit'] and current_price <= trade['tp1']:
                    logging.info(f"🎯 {symbol} TP1'E ULAŞTI! (${current_price:.6f} <= ${trade['tp1']:.6f})")
                    logging.info(f"   → %50 pozisyon kapatılıyor...")
                    logging.info(f"   → SL breakeven'e çekiliyor (${trade['entry']:.6f})")
                    
                    # Pozisyonu güncelle
                    trade['tp1_hit'] = True
                    trade['sl'] = trade['entry']  # SL breakeven
                    trade['sl_moved_to_breakeven'] = True
                    trade['quantity'] = trade['quantity'] * 0.5  # Kalan %50
                    
                    logging.info(f"   ✅ {symbol} pozisyonu güncellendi - Kalan: %50")
                
                # TP2 Kontrolü (Fib 0.618 veya Dinamik TP)
                elif trade['tp1_hit'] and not trade['tp2_hit'] and current_price <= trade['tp2']:
                    tp_type = "Dinamik (Fib 1.0)" if trade['dynamic_tp_active'] else "Fib 0.618"
                    logging.info(f"🎯🎯 {symbol} TP2'YE ULAŞTI! ({tp_type})")
                    logging.info(f"   → Fiyat: ${current_price:.6f} <= ${trade['tp2']:.6f}")
                    logging.info(f"   → Kalan %50 pozisyon kapatılıyor...")
                    
                    # Pozisyon flag'ini güncelle
                    trade['tp2_hit'] = True
                    
                    # Kar hesapla
                    profit_pct = ((trade['entry'] - current_price) / trade['entry']) * 100
                    logging.info(f"   ✅ Toplam Kar: %{profit_pct:.2f}")
                    
                    if trade['dynamic_tp_active']:
                        logging.info(f"   🚀 BTC korelasyonlu dinamik TP sayesinde daha fazla kar!")
                    
                    # Pozisyonu kapat
                    del self.active_trades[symbol]
                    self.cooldowns[symbol] = time.time()
                    
                    logging.info(f"   🏁 {symbol} pozisyonu tamamen kapatıldı!")
                
                # SL Kontrolü (TP1'den önce veya sonra)
                elif current_price >= trade['sl']:
                    if trade['sl_moved_to_breakeven']:
                        logging.info(f"🔄 {symbol} Breakeven SL tetiklendi (${current_price:.6f} >= ${trade['sl']:.6f})")
                        logging.info(f"   → Zarar yok, %50 kar realize edildi")
                    else:
                        loss_pct = ((current_price - trade['entry']) / trade['entry']) * 100
                        logging.warning(f"🛑 {symbol} SL tetiklendi! (${current_price:.6f} >= ${trade['sl']:.6f})")
                        logging.warning(f"   → Zarar: %{loss_pct:.2f}")
                    
                    del self.active_trades[symbol]
                    self.cooldowns[symbol] = time.time()
                    
            except Exception as e:
                logging.error(f"⚠️ {symbol} pozisyon izleme hatası: {str(e)[:50]}")

    async def close_all_shorts(self):
        """BTC Shield tetiklendiğinde tüm short pozisyonları kapat"""
        if not self.active_trades:
            return
        
        logging.warning("🚨 TÜM SHORT POZİSYONLAR KAPATILIYOR (BTC SHIELD)!")
        for symbol in list(self.active_trades.keys()):
            logging.warning(f"   ❌ {symbol} pozisyonu kapatıldı")
            del self.active_trades[symbol]
        
        self.btc_panic = True

    async def run_logic(self):
        logging.info("")
        logging.info("="*70)
        logging.info("🎯 APEX SNIPER BOT BAŞLATILIYOR")
        logging.info("="*70)
        logging.info("📌 Strateji: 4H Teknik Analiz + Bearish Divergence")
        logging.info("📌 Hedef: Üst banddan SHORT fırsatları")
        logging.info("📌 Filtre: Top 150 hacim (ilk 40 gainer hariç)")
        logging.info("📌 Koruma: BTC Shield aktif (15m %2+ -> kapat)")
        logging.info("📌 Yeni: BTC Emergency Flip (15m %1.5+ -> acil kapat)")
        logging.info("📌 Yeni: BTC Dinamik TP (BTC düşüşünde TP1.0'a uzaklaştır)")
        logging.info("📌 Max Pozisyon: 4 eş zamanlı")
        logging.info("="*70)
        logging.info("")
        
        # API bağlantısını test et
        logging.info("🔄 API bağlantısı test ediliyor...")
        if not await self.test_connection():
            logging.error("❌ API bağlantısı başarısız, bot durduruluyor.")
            return
        
        logging.info("")
        logging.info("🚀 Bot çalışmaya başladı!")
        logging.info("")
        
        scan_count = 0
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        while True:
            try:
                scan_count += 1
                
                # BTC Shield Kontrolü
                try:
                    if await self.check_btc_shield():
                        await self.close_all_shorts()
                        # 30 dakika bekleme (panic mode)
                        logging.warning("⏸️ BTC Panic! 30 dakika bekleme...")
                        await asyncio.sleep(1800)
                        self.btc_panic = False
                        continue
                except Exception as e:
                    logging.warning(f"⚠️ BTC Shield kontrolü başarısız: {str(e)[:50]}")

                if self.btc_panic:
                    continue  # Hala panic modundaysa tarama yapma

                # Aktif pozisyonları izle (TP1/TP2 kontrolü)
                await self.monitor_active_positions()

                try:
                    symbols = await self.fetch_eligible_symbols()
                    if not symbols:
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logging.error("⏸️ Tekrarlayan bağlantı hatası - 60 saniye bekleniyor...")
                            await asyncio.sleep(60)
                            consecutive_errors = 0
                        continue
                    
                    consecutive_errors = 0  # Başarılı - counter sıfırla
                    
                except Exception as e:
                    logging.warning(f"⚠️ Symbol listesi alınamadı: {str(e)[:50]}")
                    await asyncio.sleep(60)
                    continue
                
                logging.info(f"🔍 Apex Tarama #{scan_count} - {len(symbols)} uygun coin | Aktif: {len(self.active_trades)}/{self.max_active_trades}")
                
                for symbol in symbols:
                    if len(self.active_trades) >= self.max_active_trades:
                        break
                    if symbol in self.active_trades or symbol in self.cooldowns:
                        continue

                    try:
                        df = await self.get_indicators(symbol)
                        
                        # Fibonacci seviyelerini hesapla (4H için 75 candle lookback)
                        fib_levels = self.calculate_fibonacci_levels(df)
                        
                        signal = self.check_signal(df, fib_levels)

                        if signal:
                            logging.info(f"✅ SİNYAL BULUNDU: {symbol} ({signal})")
                            await self.open_position(symbol, signal, df, fib_levels)
                            
                    except Exception as e:
                        pass  # Veri hatası, atla
                
                await asyncio.sleep(600)  # Her 10 dakikada bir tarama
                
            except KeyboardInterrupt:
                logging.info("\n🛑 Kullanıcı tarafından durduruldu.")
                break
            except Exception as e:
                logging.error(f"❌ Ana döngü hatası: {str(e)[:100]}")
                await asyncio.sleep(60)

    async def close(self):
        """Exchange bağlantısını kapat."""
        await self.exchange.close()


# --- ÇALIŞTIRMA ---
if __name__ == "__main__":
    # Config'den API anahtarlarını yükle
    api_key, api_secret = load_config()
    
    if api_key and api_secret:
        # Config'den yüklendi, direkt başlat
        print("="*70)
        print("✅ config.py'den API anahtarları yüklendi")
        print("🚀 Uzun Vadeli Bot (Apex Sniper) başlatılıyor...")
        print("="*70)
        print("")
        print("📌 Strateji: 4H Teknik Analiz + Fibonacci Retracement")
        print("📌 Hedef: Üst banddan SHORT fırsatları")
        print("📌 TP1 (Fib 0.5): %50 pozisyon kapat + SL breakeven'e")
        print("📌 TP2 (Fib 0.618): Kalan %50 Golden Pocket'ta kapat")
        print("📌 🆕 BTC Dinamik TP: BTC düşüşünde TP'yi Fib 1.0'a uzaklaştır")
        print("📌 🆕 BTC Emergency Flip: 15dk'da %1.5+ yeşil mum -> acil kapat")
        print("📌 Filtre: Top 150 hacim (ilk 40 gainer hariç)")
        print("📌 BTC Shield aktif (15m %2+ -> kapat)")
        print("📌 Her 10 dakikada tarama")
        print("="*70)
        print("")
    else:
        # Config yok, kullanıcıdan iste
        print("="*70)
        print("⚠️ UZUN VADELİ BOT - API ANAHTARI GEREKLİ")
        print("="*70)
        print("")
        print("ℹ️ config.py dosyası bulunamadı veya boş")
        print("💡 İpucu: config_example.py'yi config.py olarak kopyalayıp düzenleyin")
        print("   Böylece bir daha API key girmenize gerek kalmaz!")
        print("")
        print("📌 API Key Gereksinimleri:")
        print("   • Binance hesabınızdan API Key oluşturun")
        print("   • 'Enable Futures' izni aktif olmalı")
        print("   • IP kısıtlaması varsa kaldırın veya IP'nizi ekleyin")
        print("")
        
        api_key = input("Binance API Key: ").strip()
        api_secret = input("Binance API Secret: ").strip()
        print("")
        
        if not api_key or not api_secret:
            print("❌ API bilgileri eksik, çıkılıyor...")
            sys.exit(1)
    
    # Botu başlat
    bot = BugraBotApex(api_key, api_secret)
    try:
        asyncio.run(bot.run_logic())
    except KeyboardInterrupt:
        print("\n🛑 Bot durduruldu.")
    except Exception as e:
        print(f"\n❌ Beklenmeyen hata: {e}")
    finally:
        asyncio.run(bot.close())
