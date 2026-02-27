"""
================================================================================
PUMP & DUMP REVERSION BOT — TEMEL PRENSİPLER
================================================================================

ROL: Algoritmik Ticaret Botu (Quant Strategy)
AMAÇ: Pump yapan low/mid-cap altcoinlerde dağıtım (distribution) sinyali
      yakalamak ve SHORT pozisyon açmak.

⚠️  DİKKAT: Bu dosya SADECE temel prensipler ve giriş mantığını içerir.
    Risk yönetimi (SL/TSL/TP) ve pozisyon kapatma mantığı YOKTUR.

MODÜLLER:
  1. Zaman Ayarlı Asenkron Motor (Timing Engine)
  2. Radar ve Av Tespiti (Universe & Watchlist)
  3. Keskin Nişancı Tetiği (Entry Trigger)
  4. Kasa Yönetimi (Position Sizing)

================================================================================
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

import pandas as pd
import ccxt.async_support as ccxt

# ── Logging Yapılandırması ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
#  KONFİGÜRASYON PARAMETRELERİ
# ══════════════════════════════════════════════════════════════════════════

class Config:
    """
    Bot parametreleri — merkezi yapılandırma sınıfı.
    """
    # ── Binance API Bilgileri ─────────────────────────────────────────────
    API_KEY = "your_binance_api_key"
    API_SECRET = "your_binance_api_secret"
    
    # ── Zaman Çerçevesi ───────────────────────────────────────────────────
    TIMEFRAME = "4h"  # 4 saatlik mumlar
    
    # ── Modül 2: Pump Tespiti Parametreleri ──────────────────────────────
    PUMP_LOOKBACK_CANDLES = 6      # Son 6 adet 4H muma bakılır (24 saat)
    PUMP_MIN_GREEN_COUNT = 4       # En az 4 yeşil mum olmalı
    PUMP_MIN_PCT = 30.0            # Minimum %30 yükseliş (ilk low → son close)
    TOP_N_GAINERS = 10             # En çok pump yapan top 10 coin
    
    # Hariç tutulacak major coinler
    EXCLUDED_BASES = {"BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE"}
    
    # ── Modül 3: Giriş Tetiği Parametreleri ──────────────────────────────
    ENTRY_RED_BODY_MIN_PCT = 4.0   # Kırmızı mum gövde düşüşü minimum %4
    
    # ── Modül 4: Kasa Yönetimi ────────────────────────────────────────────
    MARGIN_PCT = 20.0              # Bakiyenin %20'si kullanılır
    LEVERAGE = 3                   # Sabit 3x kaldıraç


# ══════════════════════════════════════════════════════════════════════════
#  ANA BOT SINIFI
# ══════════════════════════════════════════════════════════════════════════

class PumpReversionBot:
    """
    Pump & Dump Reversion Trading Bot — Temel Prensipleri
    
    Çalışma Mantığı:
      1. 4H kapanışına 10 dakika kala uyanır, universe taraması yapar
      2. Pump yapan coinleri tespit edip watchlist oluşturur
      3. 4H kapanışından 2 saniye sonra uyanır, kırmızı mum kontrolü yapar
      4. Koşullar sağlanırsa SHORT pozisyon açar (bakiyenin %20'si ile)
    """
    
    def __init__(self):
        """Bot başlatıcı — exchange bağlantısı ve veri yapıları."""
        self.exchange = ccxt.binance({
            'apiKey': Config.API_KEY,
            'secret': Config.API_SECRET,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}  # USDT-M Vadeli İşlemler
        })
        
        self.universe: List[str] = []      # Tüm USDT-M çiftleri (filtrelenmiş)
        self.watchlist: Dict[str, float] = {}  # {symbol: pump_pct} — İzleme listesi
        
        log.info("✅ Bot başlatıldı — Binance USDT-M Futures bağlantısı hazır")
    
    
    # ══════════════════════════════════════════════════════════════════════
    #  MODÜL 1: ZAMAN AYARLI ASENKRONİK MOTOR (Timing Engine)
    # ══════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def _seconds_until_next_4h_close() -> float:
        """
        Şu andan bir sonraki 4H mum kapanışına kadar kalan saniyeyi hesaplar.
        
        4H mumlar UTC bazında 00:00, 04:00, 08:00, 12:00, 16:00, 20:00'da kapanır.
        
        Returns:
            float: Kapanışa kalan saniye
        """
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        # Bir sonraki 4H kapanış saatini bul
        next_close_hour = ((hour // 4) + 1) * 4
        if next_close_hour >= 24:
            next_close_hour = 0
            close_dt = (now + timedelta(days=1)).replace(
                hour=next_close_hour, minute=0, second=0, microsecond=0
            )
        else:
            close_dt = now.replace(
                hour=next_close_hour, minute=0, second=0, microsecond=0
            )
        
        remaining = (close_dt - now).total_seconds()
        return remaining
    
    
    async def _prep_scan_loop(self):
        """
        PREP (Hazırlık) Döngüsü — 4H kapanışına 10 dakika kala uyanır.
        
        Görevler:
          1. Universe'i güncelle (tüm USDT-M vadeli çiftlerini çek)
          2. Modül 2'yi çalıştır: Pump yapan coinleri tara ve watchlist oluştur
          3. Kapanış saatine kadar bekle, sonra döngüye devam et
        
        Mantık:
          - 4H kapanışına 10 dakika kala (600 saniye) hazırlık taraması başlar
          - Tarama bittiğinde kapanış saatini bekler
          - Kapanış geçince yeni döngü için bir sonraki 4H bekler
        """
        log.info("🔄 [PREP LOOP] Başlatıldı — 4H kapanışına 10 dakika kala tarama yapacak")
        
        while True:
            try:
                # Bir sonraki 4H kapanışına kalan süreyi hesapla
                remaining = self._seconds_until_next_4h_close()
                
                # 10 dakika (600 saniye) kalana kadar bekle
                prep_offset = 600  # 10 dakika
                if remaining > prep_offset:
                    sleep_time = remaining - prep_offset
                    log.info(f"⏳ [PREP] Sonraki taramaya {sleep_time:.0f} saniye ({sleep_time/3600:.1f} saat)")
                    await asyncio.sleep(sleep_time)
                
                # Kapanış saatini hesapla
                close_time = datetime.now(timezone.utc) + timedelta(seconds=self._seconds_until_next_4h_close())
                log.info(f"🔍 [PREP] Tarama başlıyor — Hedef kapanış: {close_time.strftime('%H:%M')} UTC")
                
                # MODÜL 2: Universe güncelle ve pump taraması yap
                await self._update_universe()
                await self._scan_for_pumps()
                
                log.info(f"✅ [PREP] Tarama tamamlandı — {len(self.watchlist)} coin watchlist'te")
                
                # Kapanış saatine kadar kalan süreyi bekle
                remaining = self._seconds_until_next_4h_close()
                if remaining > 0:
                    log.info(f"⏸️  [PREP] Kapanışa {remaining:.0f} saniye bekleniyor...")
                    await asyncio.sleep(remaining + 5)  # +5 saniye margin
                
            except Exception as e:
                log.error(f"❌ [PREP LOOP] Hata: {e}")
                await asyncio.sleep(60)
    
    
    async def _trigger_loop(self):
        """
        TRIGGER (Tetik) Döngüsü — 4H kapanışından 2 saniye sonra uyanır.
        
        Görevler:
          1. Watchlist'teki coinlerin yeni kapanan mumunu kontrol et
          2. Modül 3'ü çalıştır: Kırmızı mum tespiti yap
          3. Koşul sağlanırsa Modül 4'ü çalıştır: SHORT pozisyon aç
          4. Sonraki 4H kapanışını bekle
        
        Mantık:
          - 4H kapanışından tam 2 saniye sonra uyanır
          - Yeni kapanan mumu kontrol eder
          - SHORT sinyali varsa pozisyon açar
        """
        log.info("🎯 [TRIGGER LOOP] Başlatıldı — 4H kapanışından 2 saniye sonra tetiklenecek")
        
        while True:
            try:
                # Bir sonraki 4H kapanışını bekle
                remaining = self._seconds_until_next_4h_close()
                
                if remaining > 10:  # Eğer henüz erken saatte başlatıldıysa
                    log.info(f"⏳ [TRIGGER] Sonraki kapanışa {remaining:.0f} saniye ({remaining/3600:.1f} saat)")
                    await asyncio.sleep(remaining + 2)  # Kapanıştan 2 saniye sonra
                else:
                    await asyncio.sleep(2)  # Kapanış çok yakınsa direkt 2 saniye bekle
                
                log.info("🔥 [TRIGGER] 4H kapandı — watchlist kontrol ediliyor...")
                
                # MODÜL 3: Watchlist'teki coinleri kontrol et
                for symbol in list(self.watchlist.keys()):
                    await self._check_entry_signal(symbol)
                
                # Sonraki 4H kapanışını bekle
                remaining = self._seconds_until_next_4h_close()
                if remaining > 0:
                    await asyncio.sleep(remaining)
                
            except Exception as e:
                log.error(f"❌ [TRIGGER LOOP] Hata: {e}")
                await asyncio.sleep(60)
    
    
    # ══════════════════════════════════════════════════════════════════════
    #  MODÜL 2: RADAR VE AV TESPİTİ (Universe & Watchlist)
    # ══════════════════════════════════════════════════════════════════════
    
    async def _update_universe(self):
        """
        Binance USDT-M vadeli işlemler piyasasındaki tüm coinleri çeker.
        
        Filtreleme:
          - Sadece USDT-M vadeli çiftler (ör: BTC/USDT:USDT)
          - Major coinler (BTC, ETH, BNB vb.) hariç tutulur
        
        Sonuç:
          self.universe listesi güncellenir (ör: ['TRB/USDT:USDT', ...])
        """
        try:
            markets = await self.exchange.load_markets()
            universe = []
            
            for symbol, market in markets.items():
                # Sadece USDT-M vadeli çiftler
                if not market.get('future') or not market.get('linear'):
                    continue
                if not symbol.endswith('/USDT:USDT'):
                    continue
                
                # Base coin'i al (ör: BTC/USDT:USDT → BTC)
                base = market.get('base', '')
                
                # Major coinleri hariç tut
                if base in Config.EXCLUDED_BASES:
                    continue
                
                universe.append(symbol)
            
            self.universe = universe
            log.info(f"📡 Universe güncellendi — {len(self.universe)} USDT-M vadeli çift bulundu")
            
        except Exception as e:
            log.error(f"❌ Universe güncelleme hatası: {e}")
    
    
    async def _scan_for_pumps(self):
        """
        Universe'deki tüm coinleri tarar ve pump yapanları tespit eder.
        
        Pump Koşulları:
          1. Son 6 adet 4H mumdan en az 4 tanesi yeşil olmalı
          2. İlk mumun en dibi (low) ile son mumun kapanışı (close) arasında
             en az %30 yükseliş olmalı
        
        Sonuç:
          - En çok pump yapan Top 10 coin watchlist'e eklenir
          - self.watchlist = {symbol: pump_pct, ...}
        """
        log.info(f"🔍 Pump taraması başlıyor — {len(self.universe)} coin kontrol edilecek...")
        
        pump_candidates: Dict[str, float] = {}  # {symbol: pump_pct}
        
        for symbol in self.universe:
            try:
                # Son 6 adet 4H mumu çek (limit=7 çünkü son mum henüz kapanmamış olabilir)
                ohlcv = await self.exchange.fetch_ohlcv(
                    symbol, 
                    timeframe=Config.TIMEFRAME, 
                    limit=7
                )
                
                if len(ohlcv) < Config.PUMP_LOOKBACK_CANDLES:
                    continue
                
                # Son 6 mumu al (en sonuncuyu hariç tut çünkü henüz kapanmamış olabilir)
                candles = ohlcv[-7:-1]  # Son 7'den ilk 6'sını al
                
                # DataFrame'e çevir
                df = pd.DataFrame(
                    candles,
                    columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
                )
                
                # Yeşil mum sayısını hesapla (close > open)
                green_count = (df['close'] > df['open']).sum()
                
                if green_count < Config.PUMP_MIN_GREEN_COUNT:
                    continue
                
                # Pump yüzdesini hesapla: İlk mumun en dibi → Son mumun kapanışı
                first_low = df.iloc[0]['low']
                last_close = df.iloc[-1]['close']
                pump_pct = ((last_close - first_low) / first_low) * 100.0
                
                if pump_pct >= Config.PUMP_MIN_PCT:
                    pump_candidates[symbol] = pump_pct
                
            except Exception as e:
                # Sessizce devam et (rate limit vb. hatalardan etkilenmesin)
                continue
        
        # En çok pump yapan Top N coin'i al
        sorted_pumps = sorted(
            pump_candidates.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:Config.TOP_N_GAINERS]
        
        self.watchlist = dict(sorted_pumps)
        
        if self.watchlist:
            log.info(f"🚨 TOP {len(self.watchlist)} PUMP TESPİT EDİLDİ:")
            for symbol, pct in self.watchlist.items():
                log.info(f"   • {symbol:<20} +{pct:>6.2f}%")
        else:
            log.info("ℹ️  Pump koşullarını sağlayan coin bulunamadı")
    
    
    # ══════════════════════════════════════════════════════════════════════
    #  MODÜL 3: KESKİN NİŞANCI TETİĞİ (Entry Trigger)
    # ══════════════════════════════════════════════════════════════════════
    
    async def _check_entry_signal(self, symbol: str):
        """
        Belirli bir coin için SHORT giriş sinyali kontrolü yapar.
        
        Koşullar:
          1. Yeni kapanan mum KIRMIZI olmalı (close < open)
          2. Kırmızı mumun gövde düşüşü minimum %4 olmalı
          3. Bir önceki mum YEŞİL olmalı (close > open)
        
        Args:
            symbol: Kontrol edilecek coin (ör: 'TRB/USDT:USDT')
        
        Sonuç:
            Koşullar sağlanırsa Modül 4 çağrılır (SHORT pozisyon açılır)
        """
        try:
            # Son 3 mumu çek (son kapanan + bir önceki + margin)
            ohlcv = await self.exchange.fetch_ohlcv(symbol, Config.TIMEFRAME, limit=3)
            
            if len(ohlcv) < 2:
                return
            
            # Son kapanan mum (index -1) ve bir önceki mum (index -2)
            prev_candle = ohlcv[-2]
            last_candle = ohlcv[-1]
            
            prev_open = prev_candle[1]
            prev_close = prev_candle[4]
            
            last_open = last_candle[1]
            last_close = last_candle[4]
            
            # KOŞUL 1: Bir önceki mum yeşil mi?
            if prev_close <= prev_open:
                return
            
            # KOŞUL 2: Son mum kırmızı mı?
            if last_close >= last_open:
                return
            
            # KOŞUL 3: Kırmızı mumun gövde düşüşü minimum %4 mü?
            body_drop_pct = ((last_open - last_close) / last_open) * 100.0
            
            if body_drop_pct < Config.ENTRY_RED_BODY_MIN_PCT:
                return
            
            # ✅ TÜM KOŞULLAR SAĞLANDI — SHORT GİRİŞİ YAP
            log.info(f"📉 SHORT SİNYALİ: {symbol}  |  Kırmızı gövde: -{body_drop_pct:.2f}%")
            
            # MODÜL 4: Pozisyon aç
            await self._open_short_position(symbol, last_close)
            
        except Exception as e:
            log.error(f"❌ Entry signal kontrolü hatası ({symbol}): {e}")
    
    
    # ══════════════════════════════════════════════════════════════════════
    #  MODÜL 4: KASA YÖNETİMİ (Position Sizing)
    # ══════════════════════════════════════════════════════════════════════
    
    async def _open_short_position(self, symbol: str, entry_price: float):
        """
        SHORT pozisyon açar — Bakiyenin sabit %20'si ile.
        
        Hesaplama Mantığı:
          1. Toplam bakiye (equity) Binance'ten çekilir
          2. Margin = Equity * %20  (Örn: 5000$ → 1000$)
          3. Kaldıraç = 3x (sabit)
          4. Notional (Gerçek hacim) = Margin * Leverage  (1000 * 3 = 3000$)
          5. Miktar (Qty) = Notional / Entry Price
        
        Args:
            symbol: Açılacak coin çifti (ör: 'TRB/USDT:USDT')
            entry_price: Giriş fiyatı (son kapanış)
        
        ⚠️  DİKKAT: Bu fonksiyon SL/TSL koymaz, sadece market SHORT açar.
        """
        try:
            # 1. Hesap bakiyesini çek
            balance = await self.exchange.fetch_balance()
            equity = float(balance.get('USDT', {}).get('total', 0))
            
            if equity <= 0:
                log.warning(f"⚠️  Bakiye yetersiz: {equity} USDT")
                return
            
            # 2. Margin hesapla (Bakiyenin %20'si)
            margin = equity * (Config.MARGIN_PCT / 100.0)
            
            # 3. Kaldıraç ayarla
            await self.exchange.set_leverage(Config.LEVERAGE, symbol)
            
            # 4. Notional hesapla (Gerçek hacim)
            notional = margin * Config.LEVERAGE
            
            # 5. Miktar hesapla
            qty = notional / entry_price
            
            # Binance hassasiyet kurallarına göre yuvarla
            market_info = self.exchange.market(symbol)
            precision = market_info.get('precision', {}).get('amount', 3)
            qty = round(qty, precision)
            
            log.info(
                f"💼 POZİSYON BİLGİSİ:\n"
                f"   Equity      : {equity:.2f} USDT\n"
                f"   Margin      : {margin:.2f} USDT (%{Config.MARGIN_PCT})\n"
                f"   Kaldıraç    : {Config.LEVERAGE}x\n"
                f"   Notional    : {notional:.2f} USDT\n"
                f"   Giriş Fiyatı: {entry_price:.6f}\n"
                f"   Miktar      : {qty} adet"
            )
            
            # 6. SHORT pozisyon aç (Market Sell)
            order = await self.exchange.create_order(
                symbol=symbol,
                type='market',
                side='sell',
                amount=qty
            )
            
            log.info(
                f"✅ SHORT AÇILDI: {symbol}\n"
                f"   Emir ID     : {order.get('id')}\n"
                f"   Miktar      : {qty}\n"
                f"   Fiyat       : {entry_price:.6f}\n"
                f"   Notional    : {notional:.2f} USDT"
            )
            
        except Exception as e:
            log.error(f"❌ Pozisyon açma hatası ({symbol}): {e}")
    
    
    # ══════════════════════════════════════════════════════════════════════
    #  ANA ÇALIŞTIRICI
    # ══════════════════════════════════════════════════════════════════════
    
    async def run(self):
        """
        Bot'un ana çalıştırıcısı — iki asenkron döngüyü paralel başlatır.
        
        Döngüler:
          1. PREP Loop  : 4H kapanışına 10 dakika kala tarama yapar
          2. TRIGGER Loop: 4H kapanışından 2 saniye sonra sinyal kontrol eder
        """
        log.info("🚀 Bot başlatılıyor — Asenkron döngüler çalışacak...")
        
        await asyncio.gather(
            self._prep_scan_loop(),
            self._trigger_loop()
        )
    
    
    async def close(self):
        """Bot'u düzgün şekilde kapat — exchange bağlantısını kapat."""
        await self.exchange.close()
        log.info("👋 Bot kapatıldı — Exchange bağlantısı sonlandırıldı")


# ══════════════════════════════════════════════════════════════════════════
#  PROGRAM GİRİŞ NOKTASI
# ══════════════════════════════════════════════════════════════════════════

async def main():
    """Ana program — bot'u başlat ve çalıştır."""
    bot = PumpReversionBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        log.info("⚠️  Kullanıcı tarafından durduruldu (Ctrl+C)")
    finally:
        await bot.close()


if __name__ == "__main__":
    """
    Kullanım:
      python temelprensipler.py
    
    Çalışma Prensibi:
      1. Bot başlar ve 4H kapanış zamanlamasına senkronize olur
      2. Her 4H kapanışına 10 dakika kala pump taraması yapar (watchlist)
      3. 4H kapanışından 2 saniye sonra watchlist'teki coinlerde kırmızı mum arar
      4. Koşul sağlanırsa bakiyenin %20'si ile 3x kaldıraçlı SHORT açar
      5. SADECE GİRİŞ YAPAR — Risk yönetimi (SL/TSL/TP) YOK
    """
    asyncio.run(main())
