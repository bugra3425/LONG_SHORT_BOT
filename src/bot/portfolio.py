"""
💼 Portföy & Risk Yönetimi
Dinamik marjin, pozisyon takibi, günlük kayıp limiti
"""
import logging
from datetime import datetime, timezone
from .config import (
    POSITION_SIZE_PCT, LEVERAGE, MAX_RISK_PCT,
    MAX_CONCURRENT_POSITIONS, DAILY_LOSS_LIMIT_PCT,
    COIN_BLACKLIST_AFTER, COIN_BLACKLIST_CANDLES,
    COOLDOWN_CANDLES, HARD_STOP_LOSS_PCT,
    TP1_CLOSE_PCT, TP2_CLOSE_PCT, TP3_CLOSE_PCT,
)

from .redis_client import redis_client
import json

logger = logging.getLogger("portfolio")


class Position:
    """Tek bir açık pozisyon"""
    def __init__(self, symbol: str, side: str, entry_price: float,
                 amount: float, margin: float, sl: float,
                 tp1: float, tp2: float, tp3: float, reasons: list,
                 entry_score: int = 0, opened_at: str = None):
        self.symbol = symbol
        self.side = side
        self.entry_price = float(entry_price)
        self.amount = float(amount)
        self.initial_amount = float(amount)
        self.margin = float(margin)
        self.sl = float(sl)
        self.tp1 = float(tp1)
        self.tp2 = float(tp2)
        self.tp3 = float(tp3)
        self.reasons = reasons
        self.entry_score = int(entry_score)
        self.tp1_hit = False
        self.tp2_hit = False
        self.opened_at = opened_at or datetime.now(timezone.utc).isoformat()
        self.sl_order_id = None
        self.tp_order_ids = []

    def to_dict(self) -> dict:
        """JSON için serileştir"""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'amount': self.amount,
            'initial_amount': self.initial_amount,
            'margin': self.margin,
            'sl': self.sl,
            'tp1': self.tp1,
            'tp2': self.tp2,
            'tp3': self.tp3,
            'reasons': self.reasons,
            'entry_score': self.entry_score,
            'tp1_hit': self.tp1_hit,
            'tp2_hit': self.tp2_hit,
            'opened_at': self.opened_at
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Sözlükten nesne oluştur"""
        pos = cls(
            symbol=data['symbol'], side=data['side'], entry_price=data['entry_price'],
            amount=data['amount'], margin=data['margin'], sl=data['sl'],
            tp1=data['tp1'], tp2=data['tp2'], tp3=data['tp3'],
            reasons=data['reasons'], entry_score=data.get('entry_score', 0),
            opened_at=data.get('opened_at')
        )
        pos.initial_amount = float(data.get('initial_amount', data['amount']))
        pos.tp1_hit = data.get('tp1_hit', False)
        pos.tp2_hit = data.get('tp2_hit', False)
        return pos

    @property
    def remaining_pct(self) -> float:
        if self.tp2_hit:
            return TP3_CLOSE_PCT
        if self.tp1_hit:
            return 1.0 - TP1_CLOSE_PCT
        return 1.0

    def __repr__(self):
        return f"<Position {self.symbol} {self.side} @ {self.entry_price} | Remaining: {self.remaining_pct:.0%}>"


class PortfolioManager:
    """Portföy ve risk yönetim motoru"""

    def __init__(self, exchange_client):
        self.exchange = exchange_client
        self.positions: dict[str, Position] = {}
        self.daily_pnl = 0.0
        self.daily_trades = {'wins': 0, 'losses': 0}
        self.daily_reset_date = datetime.now(timezone.utc).date()
        self.coin_cooldowns: dict[str, datetime] = {}
        self.coin_consecutive_losses: dict[str, int] = {}
        
    async def sync_positions(self):
        """
        🔄 PORTFÖY SENKRONİZASYONU (Reconciliation)
        Botun hafızasındaki pozisyonlar ile borsadaki gerçek pozisyonları eşleştirir.
        Borsada kapanmış ama botta açık görünen 'hayalet' pozisyonları temizler.
        """
        try:
            # 1. Redis'ten pozisyonları yükle (Eğer hafıza boşsa)
            if not self.positions:
                cached_positions = await redis_client.hgetall("bot:positions")
                if cached_positions:
                    self.positions = {s: Position.from_dict(d) for s, d in cached_positions.items()}
                    logger.info(f"📥 Redis'ten {len(self.positions)} pozisyon içe aktarıldı.")

            # 2. Borsadaki gerçek açık pozisyonları çek
            exchange_positions = self.exchange.get_positions() # Liste döner [{'symbol': 'BTCUSDT', ...}]
            
            # SEMBOL NORMALİZASYONU
            exchange_symbols = set()
            for p in exchange_positions:
                if float(p.get('contracts', 0)) == 0:
                    continue
                sym = p['info'].get('symbol') or p['symbol'].replace('/', '').split(':')[0]
                exchange_symbols.add(sym)
            
            # 3. Botun hafızasındaki pozisyonları kontrol et
            local_symbols = list(self.positions.keys())
            
            for symbol in local_symbols:
                if symbol not in exchange_symbols:
                    logger.warning(f"👻 Hayalet pozisyon tespit edildi ve temizleniyor: {symbol}")
                    try:
                        self.exchange.cancel_all_orders(symbol)
                    except Exception as e:
                        logger.error(f"❌ {symbol} emir temizleme hatası: {e}")
                    
                    del self.positions[symbol]
                    await redis_client.hdel("bot:positions", symbol)
            
            # 4. Borsada olup botta olmayanları ekle
            for pos_data in exchange_positions:
                symbol = pos_data['info'].get('symbol') or pos_data['symbol'].replace('/', '').split(':')[0]
                if float(pos_data.get('contracts', 0)) == 0: continue
                    
                if symbol not in self.positions:
                    logger.info(f"🆕 Borsada tespit edilen mevcut pozisyon içe aktarılıyor: {symbol}")
                    raw_amt = float(pos_data['info'].get('positionAmt', 0))
                    side = 'SHORT' if raw_amt < 0 else 'LONG'

                    new_pos = Position(
                        symbol=symbol, side=side, 
                        entry_price=float(pos_data.get('entryPrice', 0)),
                        amount=float(pos_data.get('contracts', 0)),
                        margin=0.0, sl=float('inf') if side == 'SHORT' else 0.0,
                        tp1=0.0, tp2=0.0, tp3=0.0, reasons=['Recovered']
                    )
                    self.positions[symbol] = new_pos
                    await redis_client.hset("bot:positions", symbol, new_pos.to_dict())
            
            # 5. Yetim Emir Temizliği
            active_syms = set(self.positions.keys()) | exchange_symbols
            self.exchange.cleanup_orphan_orders(active_syms)

            # 6. Global stats güncelle (API için)
            stats = self._get_sync_stats()
            await redis_client.set("bot:stats", stats)

        except Exception as e:
            logger.error(f"❌ Portföy senkronizasyonu hatası: {e}")

    def _get_sync_stats(self) -> dict:
        """Dashboard API için özet veri"""
        return {
            'balance': 0, # main.py'de güncellenecek
            'open_positions': len(self.positions),
            'daily_pnl': self.daily_pnl,
            'wins': self.daily_trades['wins'],
            'losses': self.daily_trades['losses'],
            'last_update': datetime.now(timezone.utc).isoformat()
        }


    def _reset_daily_if_needed(self):
        """Gün değiştiyse günlük sayaçları sıfırla"""
        today = datetime.now(timezone.utc).date()
        if today != self.daily_reset_date:
            logger.info(f"📅 Yeni gün: {today} — Günlük sayaçlar sıfırlandı")
            self.daily_pnl = 0.0
            self.daily_trades = {'wins': 0, 'losses': 0}
            self.daily_reset_date = today

    def get_balance(self) -> dict:
        """Canlı bakiye bilgisi"""
        return self.exchange.get_balance()

    def can_open_position(self, symbol: str) -> tuple[bool, str]:
        """Yeni pozisyon açılabilir mi? → (ok, reason)"""
        self._reset_daily_if_needed()

        # Zaten hafızada açık mı?
        if symbol in self.positions:
            return False, f"{symbol} zaten açık (hafızada)"

        # Restart durumu: Borsada zaten açık mı?
        exchange_positions = self.exchange.get_positions()
        active_symbols = [p['symbol'] for p in exchange_positions]
        if symbol in active_symbols:
            return False, f"{symbol} zaten açık (borsada)"

        # Max eş zamanlı pozisyon
        if len(self.positions) >= MAX_CONCURRENT_POSITIONS:
            return False, f"Max pozisyon limiti: {MAX_CONCURRENT_POSITIONS}"

        # Günlük kayıp limiti
        balance = self.get_balance()
        total = balance['total']
        if total > 0 and abs(self.daily_pnl) / total * 100 >= DAILY_LOSS_LIMIT_PCT:
            return False, f"Günlük kayıp limiti aşıldı: ${self.daily_pnl:.2f}"

        # Max risk kontrolü
        used_margin = sum(p.margin for p in self.positions.values())
        if total > 0 and used_margin / total * 100 >= MAX_RISK_PCT:
            return False, f"Max risk limiti: kasanın %{MAX_RISK_PCT}'i kullanımda"

        # Coin cooldown
        if symbol in self.coin_cooldowns:
            if datetime.now(timezone.utc) < self.coin_cooldowns[symbol]:
                return False, f"{symbol} blacklist'te (cooldown)"

        return True, "OK"

    def calculate_position_size(self, symbol: str, price: float, reduction_factor: float = 1.0) -> tuple[float, float]:
        """Pozisyon büyüklüğü hesapla → (amount, margin)"""
        balance = self.get_balance()
        free = balance['free']
        margin = free * (POSITION_SIZE_PCT / 100) * reduction_factor

        if margin < 5:
            return 0, 0

        notional = margin * LEVERAGE
        amount = notional / price

        # Binance limitlerini uygula (Min/Max/Precision)
        amount = self.exchange.sanitize_amount(symbol, amount)
        
        # Miktar sıfırlandıysa veya çok azsa işlemi iptal et
        if amount <= 0:
            return 0.0, 0.0

        # Gerçek kullanılan marjini yeniden hesapla (Limitlerden dolayı düşmüş olabilir)
        real_notional = amount * price
        margin = real_notional / LEVERAGE

        return amount, round(margin, 2)

    async def register_position(self, signal: dict, amount: float, margin: float) -> Position:
        """Yeni pozisyonu kaydet"""
        pos = Position(
            symbol=signal['symbol'],
            side=signal['side'],
            entry_price=signal['entry_price'],
            amount=amount,
            margin=margin,
            sl=signal['sl'],
            tp1=signal['tp1'],
            tp2=signal['tp2'],
            tp3=signal['tp3'],
            reasons=[signal['reason']] if 'reason' in signal else signal.get('reasons', []),
        )
        self.positions[signal['symbol']] = pos
        await redis_client.hset("bot:positions", signal['symbol'], pos.to_dict())
        logger.info(f"📋 Pozisyon kayıtlı: {pos.symbol} {pos.side} @ {pos.entry_price}")
        return pos

    async def close_position(self, symbol: str, result: str, pnl_usd: float):
        """Pozisyonu kapat ve istatistik güncelle"""
        if symbol not in self.positions:
            logger.warning(f"⚠️ Kapatılmaya çalışılan pozisyon hafızada yok: {symbol}")
            return

        self._reset_daily_if_needed()
        self.daily_pnl += pnl_usd

        if pnl_usd >= 0:
            self.daily_trades['wins'] += 1
            self.coin_consecutive_losses[symbol] = 0
        else:
            self.daily_trades['losses'] += 1
            losses = self.coin_consecutive_losses.get(symbol, 0) + 1
            self.coin_consecutive_losses[symbol] = losses

            if losses >= COIN_BLACKLIST_AFTER:
                from datetime import timedelta
                # 1m periyodunda Blacklist süresini direkt dakika olarak alıyoruz
                cooldown_minutes = COIN_BLACKLIST_CANDLES 
                self.coin_cooldowns[symbol] = datetime.now(timezone.utc) + timedelta(minutes=cooldown_minutes)
                self.coin_consecutive_losses[symbol] = 0
                logger.warning(f"🚫 {symbol} blacklist'e alındı ({cooldown_minutes} dk)")

        del self.positions[symbol]
        await redis_client.hdel("bot:positions", symbol)
        
        # Stats güncelle
        stats = self._get_sync_stats()
        await redis_client.set("bot:stats", stats)
        
        logger.info(f"🗑️ Pozisyon silindi: {symbol} | {result} | PnL: ${pnl_usd:+.2f}")

    def get_stats(self) -> dict:
        """Günlük istatistikler"""
        self._reset_daily_if_needed()
        balance = self.get_balance()
        return {
            'balance': balance['total'],
            'free': balance['free'],
            'daily_pnl': self.daily_pnl,
            'open_positions': len(self.positions),
            'wins': self.daily_trades['wins'],
            'losses': self.daily_trades['losses'],
        }
