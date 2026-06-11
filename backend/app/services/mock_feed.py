"""
Mock Market Data Feed
─────────────────────
Simulates NIFTY and option price movements for paper trading / testing.
Replaces the Kite WebSocket feed when in PAPER_TRADE mode.
"""

import asyncio
from decimal import Decimal
from loguru import logger
from app.core.strategy_engine import engine


class MockDataFeed:
    """
    Generates simulated NIFTY ticks.
    Can be driven by:
      1. A predefined price sequence (for testing / replay)
      2. Random walk (for interactive paper trading)
    """

    def __init__(self):
        self.is_running = False
        self._price_sequence: list[float] = []
        self._current_index = 0
        self._tick_interval = 1.0  # seconds between ticks

    def set_price_sequence(self, prices: list[float]):
        """Load a predefined sequence of NIFTY prices for testing."""
        self._price_sequence = prices
        self._current_index = 0
        logger.info(f"MockFeed: loaded {len(prices)} price points")

    def set_tick_interval(self, seconds: float):
        self._tick_interval = seconds

    async def start(self):
        self.is_running = True
        logger.info("MockDataFeed started")

        if self._price_sequence:
            await self._replay_sequence()
        else:
            await self._random_walk()

    def stop(self):
        self.is_running = False
        logger.info("MockDataFeed stopped")

    async def _replay_sequence(self):
        """Replay a fixed price sequence — used for backtesting / unit tests."""
        while self.is_running and self._current_index < len(self._price_sequence):
            price = Decimal(str(self._price_sequence[self._current_index]))
            self._current_index += 1

            # Simulate option LTP (simple: option = 100 + (nifty_move × 0.5))
            await self._update_option_ltps(price)
            await engine.on_nifty_tick(price)
            await asyncio.sleep(self._tick_interval)

        logger.info("MockDataFeed: price sequence exhausted")
        self.stop()

    async def _random_walk(self):
        """Random walk from a starting NIFTY price — for interactive paper trading."""
        import random
        price = Decimal("23200.00")  # default starting price

        while self.is_running:
            # Small random move: ±0–15 points per tick
            move = Decimal(str(random.uniform(-15, 15)))
            price = max(Decimal("15000"), price + move)  # floor at 15000

            await self._update_option_ltps(price)
            await engine.on_nifty_tick(price)
            await asyncio.sleep(self._tick_interval)

    async def _update_option_ltps(self, nifty_ltp: Decimal):
        """
        Simulate option LTPs based on NIFTY price.
        Simplified: option price = base + (delta × nifty_move_from_entry).
        """
        for symbol, base_price in list(engine._option_ltp.items()) or []:
            # Simple: fluctuate ±2 pts around current
            import random
            new_ltp = base_price + Decimal(str(random.uniform(-2, 2)))
            engine.update_option_ltp(symbol, max(Decimal("0.05"), new_ltp))

        # Also initialize option LTP if a new instrument is being watched
        ce_symbol = engine.ce.locked_instrument
        pe_symbol = engine.pe.locked_instrument

        for symbol in [ce_symbol, pe_symbol]:
            if symbol and symbol not in engine._option_ltp:
                engine.update_option_ltp(symbol, Decimal("100.00"))  # Initial mock LTP


# Global singleton
mock_feed = MockDataFeed()
