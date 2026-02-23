"""
📲 Telegram Bildirim Servisi
"""
import asyncio
import logging
import os
import httpx

logger = logging.getLogger("notifier")

# .env'den direkt oku (18.02.2026.py ile uyumlu)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")  # Virgülle ayrılmış: "123456,789012"

_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Çoklu chat ID desteği
def _get_chat_ids():
    """Virgülle ayrılmış chat ID'leri listeye çevir"""
    if not TELEGRAM_CHAT_ID:
        return []
    return [cid.strip() for cid in TELEGRAM_CHAT_ID.split(",") if cid.strip()]


async def _send_async(text: str, parse_mode: str = "HTML"):
    """Async Telegram mesajı gönder - Çoklu chat ID desteği"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("⚠️ Telegram ayarları eksik, bildirim gönderilmedi")
        return

    chat_ids = _get_chat_ids()
    if not chat_ids:
        logger.warning("⚠️ Geçerli chat ID bulunamadı")
        return

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Her chat ID'ye ayrı ayrı gönder
            for chat_id in chat_ids:
                try:
                    await client.post(
                        f"{_BASE_URL}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": text,
                            "parse_mode": parse_mode,
                            "disable_web_page_preview": True,
                        },
                    )
                except Exception as e:
                    logger.debug(f"📵 Chat ID {chat_id} gönderilemedi: {type(e).__name__}")
    except Exception as e:
        # Timeout ve bağlantı hatalarını sessizce geç, sadece kritik hataları logla
        error_str = str(e)
        if "timeout" in error_str.lower() or "ConnectTimeout" in error_str:
            logger.debug(f"📵 Telegram timeout (görmezden gelindi): {type(e).__name__}")
        elif "Cannot connect to host" in error_str or "getaddrinfo failed" in error_str:
            logger.debug(f"📵 Telegram bağlantı hatası (görmezden gelindi): {type(e).__name__}")
        else:
            logger.error(f"❌ Telegram hatası: {e}")


def send(text: str):
    """Senkron wrapper — herhangi bir yerden çağrılabilir"""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_send_async(text))
    except RuntimeError:
        asyncio.run(_send_async(text))


def notify_signal(signal: dict):
    """Sinyal bulunduğunda bildirim - 18.02.2026.py uyumlu"""
    side_icon = "📉" if signal['side'] == 'SHORT' else "📈"
    reason = signal.get('reason', 'Pump & Dump Reversion')
    
    # 18.02.2026.py'de sadece SL var, TP yok (BB hedefleriyle dinamik çıkış)
    text = (
        f"{side_icon} <b>YENİ SİNYAL</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"🪙 <b>{signal['symbol']}</b>\n"
        f"📋 {reason}\n"
        f"💵 Giriş: <code>{signal['entry_price']:.6f}</code>\n"
        f"🛑 SL: <code>{signal['sl']:.6f}</code> (Entry × 1.15)\n"
        f"🎯 Çıkış: SL/BE/TSL ile dinamik\n"
        f"━━━━━━━━━━━━━━━━"
    )
    send(text)


def notify_trade_open(symbol: str, side: str, amount: float, price: float, margin: float):
    """Pozisyon açıldığında bildirim"""
    icon = "📉" if side == 'SHORT' else "📈"
    text = (
        f"{icon} <b>POZİSYON AÇILDI</b>\n"
        f"🪙 {symbol} | {side}\n"
        f"💵 Fiyat: <code>{price:.6f}</code>\n"
        f"📦 Miktar: {amount}\n"
        f"💰 Marjin: ${margin:.2f}"
    )
    send(text)


def notify_trade_close(symbol: str, result: str, pnl_pct: float, pnl_usd: float):
    """Pozisyon kapandığında bildirim"""
    icon = "✅" if pnl_usd >= 0 else "❌"
    text = (
        f"{icon} <b>İŞLEM KAPANDI</b>\n"
        f"🪙 {symbol} | {result}\n"
        f"{'📈' if pnl_usd >= 0 else '📉'} PnL: {pnl_pct:+.2f}% (${pnl_usd:+.2f})"
    )
    send(text)


def notify_daily_summary(stats: dict):
    """Günlük özet bildirim"""
    text = (
        f"📊 <b>GÜNLÜK ÖZET</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"💰 Bakiye: ${stats.get('balance', 0):.2f}\n"
        f"📈 Bugünkü PnL: ${stats.get('daily_pnl', 0):+.2f}\n"
        f"🎯 Açık Pozisyon: {stats.get('open_positions', 0)}\n"
        f"✅ Kazanan: {stats.get('wins', 0)} | ❌ Kaybeden: {stats.get('losses', 0)}\n"
        f"🔍 Taranan Coin: {stats.get('scanned', 0)}"
    )
    send(text)


def notify_error(error: str):
    """Hata bildirimi"""
    send(f"🚨 <b>HATA</b>\n{error}")


def notify_risk_limit(reason: str):
    """Risk limiti aşıldığında bildirim"""
    send(f"🛡️ <b>RİSK LİMİTİ</b>\n{reason}")
