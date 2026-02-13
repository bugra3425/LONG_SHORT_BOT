"""
Bugra Bot - Ultra-Fast Scalping Bot
Dosya: bugra_bot.py
Tarih: 13 Şubat 2026
Açıklama: 1 dakikalık mumlarla momentum stratejisi. Her 10 saniyede 50 volatil
          coini tarar, saniyelik hareketleri yakalar. Sadece bilgilendirme.
"""
import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import pandas_ta as ta
import logging
import time

# --- LOG AYARLARI ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class BugraBot:
    def __init__(self):
        # API key'siz çalışır (sadece public data okur)
        self.exchange = ccxt.binance({
            'options': {'defaultType': 'future'},
            'enableRateLimit': True,
        })
        self.leverage = 5
        self.stop_loss_pct = 0.03  # %3
        self.min_volume = 20_000_000
        self.timeframe = '1m'  # 1 dakikalık mumlar - Hızlı sinyal için
        self.min_momentum_pct = 1.0  # Son 3 mumda %1+ hareket = sinyal
        
        # Cooldown sistemi: Aynı coin için 5dk bekleme
        self.last_signal_time = {}  # {symbol: timestamp}
        self.cooldown_seconds = 300  # 5 dakika

    async def fetch_top_gainers(self):
        """Binance Futures'da en çok yükselen 50 küçük/orta boy coini getirir."""
        tickers = await self.exchange.fetch_tickers()
        # Filtreler:
        # 1. USDT çiftleri
        # 2. Hacim > 20M (likidite)
        # 3. Fiyat < $100 (BTC, ETH gibi büyükleri çıkar - volatilite için)
        # 4. Fiyat > $0.0001 (çok düşük hacimli shitcoinleri çıkar)
        futures_tickers = [
            t for t in tickers.values() 
            if '/USDT' in t['symbol'] 
            and t.get('quoteVolume', 0) > self.min_volume
            and 0.0001 < t.get('last', 0) < 100  # Orta boy coinler
        ]
        # Değişim oranına göre sırala ve ilk 50'yi al
        sorted_tickers = sorted(futures_tickers, key=lambda x: x.get('percentage', 0), reverse=True)
        return [t['symbol'] for t in sorted_tickers[:50]]

    async def get_indicators(self, symbol):
        """Verileri çeker - Hızlı momentum hesaplaması."""
        ohlcv = await self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=20)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # Hızlı hesaplamalar
        df['price_change'] = df['close'].pct_change() * 100  # Mum değişimi %
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(10).mean()  # Hacim spike
        
        return df

    def check_signal(self, df):
        """HıZLI MOMENTUM STRATEJİSİ: Son 3 mumda güçlü hareket var mı?"""
        if len(df) < 5:
            return None
            
        last_row = df.iloc[-1]
        last_3_candles = df.iloc[-4:-1]  # Son 3 kapanmış mum
        
        # Son 3 mumdaki toplam fiyat değişimi
        momentum = last_3_candles['price_change'].sum()
        
        # Hacim spike var mı? (Ortalamann 1.3 katından fazla)
        volume_spike = last_row['volume_ratio'] > 1.3
        
        # LONG: Son 3 mumda %1+ yükseliyor VE hacim artıyor
        if momentum > self.min_momentum_pct and volume_spike:
            return 'LONG'
        
        # SHORT: Son 3 mumda %1+ düşüyor VE hacim artıyor
        if momentum < -self.min_momentum_pct and volume_spike:
            return 'SHORT'
        
        return None

    async def execute_trade(self, symbol, side, last_price, sl_price, tp_price, momentum):
        """Sinyal bilgisini terminale yazdırır (Binance'de işlem AÇMAZ)."""
        logging.info(f"")
        logging.info(f"{'='*60}")
        logging.info(f"⚡🚀 {side} SİNYALİ - ACİL!")  
        logging.info(f"{'='*60}")
        logging.info(f"💰 Coin: {symbol}")
        logging.info(f"📊 Yön: {side}")
        logging.info(f"🔥 Momentum: {momentum:+.2f}% (3 mumda)")
        logging.info(f"💵 Giriş: ${last_price:.6f}")
        logging.info(f"🛑 Stop Loss ({self.stop_loss_pct*100:.0f}%): ${sl_price:.6f}")
        logging.info(f"🎯 Take Profit (3%): ${tp_price:.6f}")
        logging.info(f"⚡ Kaldıraç: {self.leverage}x")
        logging.info(f"{'='*60}")
        logging.info(f"")

    async def scan_symbol(self, symbol):
        """Tek bir coini tarar."""
        try:
            # Cooldown kontrolü: Son 5 dakikada sinyal verdiysen atla
            now = time.time()
            if symbol in self.last_signal_time:
                elapsed = now - self.last_signal_time[symbol]
                if elapsed < self.cooldown_seconds:
                    return  # Henüz 5 dk geçmemiş, atla
            
            df = await self.get_indicators(symbol)
            signal = self.check_signal(df)
            
            if signal:
                last_price = df.iloc[-1]['close']
                momentum = df.iloc[-4:-1]['price_change'].sum()  # Son 3 mum momentum
                
                # Stop Loss ve Take Profit hesapla
                if signal == 'LONG':
                    sl_price = last_price * (1 - self.stop_loss_pct)
                    tp_price = last_price * 1.03  # %3 profit (hızlı scalp)
                else:  # SHORT
                    sl_price = last_price * (1 + self.stop_loss_pct)
                    tp_price = last_price * 0.97  # %3 profit
                
                await self.execute_trade(symbol, signal, last_price, sl_price, tp_price, momentum)
                
                # Sinyal verdi, cooldown başlat
                self.last_signal_time[symbol] = now
                
        except Exception:
            pass # Bazı yeni coinlerde veri eksikliği olabilir, atla.

    async def run(self):
        logging.info("⚡🚀 HİZLANDIRILMIŞ MOD - Her 10 saniyede tarama!")
        logging.info("📌 1 dakikalık mumlar | Momentum stratejisi")
        logging.info("📌 Filtre: $0.0001 < Fiyat < $100 (Yüksek volatilite)\n")
        
        scan_count = 0
        while True:
            scan_count += 1
            symbols = await self.fetch_top_gainers()
            if symbols:
                logging.info(f"🔍 Tarama #{scan_count} - {len(symbols)} coin kontrol ediliyor...")
            tasks = [self.scan_symbol(s) for s in symbols]
            await asyncio.gather(*tasks)
            
            await asyncio.sleep(10)  # 10 SANİYE'de bir tarama (hızlı!)

    async def close(self):
        """Exchange bağlantısını kapat."""
        await self.exchange.close()

# --- ÇALIŞTIRMA ---
if __name__ == "__main__":
    print("="*60)
    print("⚡🚀 BUGRA BOT - HİZLI SCALPING MODU 🚀⚡")
    print("📌 Binance'de işlem AÇMAZ, SADECE SİNYALLER!")
    print("📌 Strateji: 1m Momentum + Volume Spike")
    print("📌 Tarama: HER 10 SANİYE - Top 50 volatil coin")
    print("📌 Cooldown: Aynı coin için 5 dakika bekleme")
    print("📌 Hedef: Saniyelik hareketleri yakala")
    print("📌 BTC/ETH gibi ağır coinler FİLTRE DİŞI")
    print("="*60)
    print("")
    
    bot = BugraBot()  # API key'siz çalışır
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\n🛑 Bot durduruldu.")
    finally:
        asyncio.run(bot.close())
