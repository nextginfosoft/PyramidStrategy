"""
Mock Market Data Feed
─────────────────────
Simulates NIFTY and option price movements for paper trading / testing.
Replaces the Kite WebSocket feed when in PAPER_TRADE mode.
User-specific: initialized with a user's StrategyEngine instance.
"""

import asyncio
from decimal import Decimal
from loguru import logger
import random


class MockDataFeed:
    """
    Generates simulated NIFTY ticks for a specific StrategyEngine.
    """

    def __init__(self, engine):
        self.engine = engine
        self.is_running = False
        self._price_sequence: list[float] = []
        self._current_index = 0
        self._tick_interval = 1.0  # seconds between ticks

    def set_price_sequence(self, prices: list[float]):
        """Load a predefined sequence of NIFTY prices for testing."""
        self._price_sequence = prices
        self._current_index = 0
        logger.info(f"User {self.engine.user_id} MockFeed: loaded {len(prices)} price points")

    def set_tick_interval(self, seconds: float):
        self._tick_interval = seconds

    async def start(self):
        self.is_running = True
        logger.info(f"User {self.engine.user_id}: MockDataFeed started")

        if self._price_sequence:
            await self._replay_sequence()
        else:
            await self._random_walk()

    def stop(self):
        self.is_running = False
        logger.info(f"User {self.engine.user_id}: MockDataFeed stopped")

    async def _replay_sequence(self):
        """Replay a fixed price sequence — used for backtesting / unit tests."""
        while self.is_running and self._current_index < len(self._price_sequence):
            price = Decimal(str(self._price_sequence[self._current_index]))
            self._current_index += 1

            await self._update_option_ltps(price)
            await self.engine.on_nifty_tick(price)
            await asyncio.sleep(self._tick_interval)

        logger.info(f"User {self.engine.user_id} MockFeed: price sequence exhausted")
        self.stop()

    async def _random_walk(self):
        """Random walk from a starting NIFTY price — for interactive paper trading."""
        price = Decimal("23200.00")  # default starting price

        while self.is_running:
            # Small random move: ±0–15 points per tick
            move = Decimal(str(random.uniform(-15, 15)))
            price = max(Decimal("15000"), price + move)  # floor at 15000

            await self._update_option_ltps(price)
            await self.engine.on_nifty_tick(price)
            await asyncio.sleep(self._tick_interval)

    async def _update_option_ltps(self, nifty_ltp: Decimal):
        """
        Simulate option LTPs based on NIFTY price.
        """
        for symbol, base_price in list(self.engine._option_ltp.items()) or []:
            new_ltp = base_price + Decimal(str(random.uniform(-2, 2)))
            self.engine.update_option_ltp(symbol, max(Decimal("0.05"), new_ltp))

        # Also initialize option LTP if a new instrument is being watched
        ce_symbol = self.engine.ce.locked_instrument
        pe_symbol = self.engine.pe.locked_instrument

        for symbol in [ce_symbol, pe_symbol]:
            if symbol and symbol not in self.engine._option_ltp:
                self.engine.update_option_ltp(symbol, Decimal("100.00"))  # Initial mock LTP
