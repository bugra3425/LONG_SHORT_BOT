import asyncio
import logging
import signal as sig
from datetime import datetime, timezone

from .config import SCAN_INTERVAL_SECONDS, LOG_LEVEL
from .exchange import ExchangeClient
from .scanner import MarketScanner
from .portfolio import PortfolioManager
from .trader import TradeManager
from .redis_client import redis_client
from . import notifier

# Loglama
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s | %(name)-10s | %(levelname)-5s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bot")

# Graceful shutdown
_running = True

def _shutdown(signum, frame):
    global _running
    logger.info("🛑 Kapatma sinyali alındı...")
    _running = False

async def main():
    """Ana giriş noktası (Async)"""
    global _running
    
    # Sinyal yakalayıcıları (Unix/Windows uyumlu)
    try:
        loop = asyncio.get_running_loop()
        for s in (sig.SIGINT, sig.SIGTERM):
            loop.add_signal_handler(s, lambda: asyncio.create_task(_async_shutdown()))
    except NotImplementedError:
        # Windows'ta loop.add_signal_handler yok
        sig.signal(sig.SIGINT, _shutdown)
        sig.signal(sig.SIGTERM, _shutdown)

    logger.info("=" * 60)
    logger.info("🤖 BUGRA-BOT v2.2.0 — Northflank Ready Engine")
    logger.info("=" * 60)

    # Redis bağlantısını başlat
    await redis_client.connect()

    # Modülleri başlat
    exchange = ExchangeClient()
    portfolio = PortfolioManager(exchange)
    scanner = MarketScanner(exchange)
    trade_manager = TradeManager(exchange, portfolio)

    # Bağlantı testi
    balance = portfolio.get_balance()
    if balance['total'] <= 0:
        logger.error("❌ Bakiye alınamadı veya sıfır. API key'leri kontrol edin.")
        notifier.notify_error("Bakiye alınamadı! API key kontrol edin.")
        return

    logger.info(f"💰 Bakiye: ${balance['total']:.2f} (Free: ${balance['free']:.2f})")
    notifier.send(
        f"🚀 <b>Bot Başlatıldı (Northflank Mode)</b>\n"
        f"💰 Bakiye: ${balance['total']:.2f}\n"
        f"⏱️ Tarama: her {SCAN_INTERVAL_SECONDS}s"
    )

    last_daily_report = datetime.now(timezone.utc).hour
    cycle_count = 0

    # Ana döngü
    while _running:
        try:
            cycle_count += 1
            logger.info(f"\n🔄 Döngü #{cycle_count} başlıyor...")

            # 0. Portföy Senkronizasyonu
            await portfolio.sync_positions()

            # 1. Açık pozisyonları kontrol et (TP/SL)
            await trade_manager.check_positions(scanner=scanner)

            # 2. Piyasayı tara
            signals = await scanner.scan_all()

            # 3. Sinyalleri işle
            for signal in signals:
                if not _running:
                    break

                can_open, reason = portfolio.can_open_position(signal['symbol'])
                if can_open:
                    notifier.notify_signal(signal)
                    success = await trade_manager.execute_signal(signal)
                    if success:
                        await asyncio.sleep(1)

            # 4. Günlük özet
            current_hour = datetime.now(timezone.utc).hour
            if current_hour == 0 and last_daily_report != 0:
                stats = portfolio.get_stats()
                stats['scanned'] = len(scanner.symbols)
                notifier.notify_daily_summary(stats)
                last_daily_report = 0
            elif current_hour != 0:
                last_daily_report = current_hour

            # 5. Durum logu ve Redis güncelleme
            stats = portfolio.get_stats()
            stats['balance'] = portfolio.get_balance()['total']
            await redis_client.set("bot:stats", stats)
            
            logger.info(
                f"📊 Bakiye: ${stats['balance']:.2f} | "
                f"Açık: {stats['open_positions']} | "
                f"Günlük PnL: ${stats['daily_pnl']:+.2f} | "
                f"W/L: {stats['wins']}/{stats['losses']}"
            )

            # Bekleme
            for _ in range(SCAN_INTERVAL_SECONDS):
                if not _running:
                    break
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"❌ Döngü hatası: {e}", exc_info=True)
            notifier.notify_error(str(e))
            await asyncio.sleep(30)

    # Kapatma
    logger.info("🛑 Bot kapatılıyor...")
    await redis_client.close()
    notifier.send("🛑 <b>Bot Kapatıldı</b>")
    logger.info("👋 Güle güle!")

async def _async_shutdown():
    global _running
    logger.info("🛑 Kapatma sinyali alındı...")
    _running = False

if __name__ == "__main__":
    asyncio.run(main())
