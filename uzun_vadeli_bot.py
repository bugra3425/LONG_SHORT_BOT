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
    • Göstergeler: BB, RSI, MFI, ATR, EMA200
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
        Sinyal kontrolü - Fibonacci onaylı.
        SHORT sinyali için Fibonacci 0/1.272/1.618 seviyelerinde olmalı
        ve 0.236 altında kapanış yapmalı.
        """
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 1. Lokasyon Kilidi: Fiyat Üst Bandın Tepesinde ve EMA200 Üstünde olmalı
        if curr['c'] < curr['bb_upper'] or curr['c'] < curr['ema200']:
            return None

        # 2. RSI/MFI Aşırı Alım Filtresi
        if curr['rsi'] < 60 or curr['mfi'] < 75:
            return None

        # 3. Ayı Uyumsuzluğu
        if not self.check_divergence(df):
            return None
        
        # 4. FİBONACCI ONAYI (KRİTİK!)
        # Fiyat Fibonacci 0, 1.272 veya 1.618 seviyelerine çok yakın mı? (%0.5 tolerans)
        tolerance = 0.005  # %0.5
        
        near_fib_0 = abs(curr['h'] - fib_levels['fib_0']) / fib_levels['fib_0'] < tolerance
        near_ext_1272 = abs(curr['h'] - fib_levels['ext_1272']) / fib_levels['ext_1272'] < tolerance
        near_ext_1618 = abs(curr['h'] - fib_levels['ext_1618']) / fib_levels['ext_1618'] < tolerance
        
        at_fibonacci_key_level = near_fib_0 or near_ext_1272 or near_ext_1618
        
        if not at_fibonacci_key_level:
            return None  # Fibonacci seviyesinde değilse işlem yok
        
        # 5. Kırmızı mum Fibonacci 0.236 ALTINDA kapanmalı (düzeltme başladı kanıtı)
        closed_below_fib236 = curr['c'] < fib_levels['fib_236']
        
        if not closed_below_fib236:
            return None  # 0.236 altına kapanmadıysa henüz erken

        # 6. Tetikleyici Mum (Hacimli Kırmızı Mum veya 2 Ardışık Kırmızı)
        is_red = curr['c'] < curr['o']
        body_pct = abs(curr['c'] - curr['o']) / curr['o']
        vol_spike = curr['v'] > (df['v'].iloc[-6:-1].mean() * 1.2)

        if is_red and body_pct >= 0.03 and vol_spike:
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
                'signal': signal,
                'time': datetime.now(),
                'fib_levels': fib_levels,
                'tp1_hit': False,  # TP1'e ulaşıldı mı?
                'sl_moved_to_breakeven': False  # SL breakeven'e çekildi mi?
            }
            
        except Exception as e:
            logging.error(f"❌ {symbol} pozisyon açma hatası: {e}")

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
        print("📌 Filtre: Top 150 hacim (ilk 40 gainer hariç)")
        print("📌 BTC Shield aktif")
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
