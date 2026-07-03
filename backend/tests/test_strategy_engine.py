import pytest
import time
from decimal import Decimal
from datetime import date
from unittest.mock import MagicMock, patch
from app.core.strategy_engine import StrategyEngine
from app.core.state_machine import State

@pytest.fixture
def engine():
    with patch("app.core.strategy_engine.SessionLocal") as mock_session_local, \
         patch("app.core.strategy_engine.should_squareoff", return_value=False), \
         patch("app.core.strategy_engine.is_entry_allowed", return_value=True):
        mock_db = MagicMock()
        mock_session_local.return_value.__enter__.return_value = mock_db

        engine = StrategyEngine(user_id=1)
        engine.order_manager = MagicMock()
        engine.order_manager.place_buy_order.return_value = {
            "order_id": "MOCK-123",
            "fill_price": Decimal("100.00"),
            "qty": 75,
            "status": "COMPLETE",
        }
        engine.order_manager.place_exit_order.return_value = {
            "order_id": "MOCK-EXIT-123",
            "exit_price": Decimal("120.00"),
            "pnl_points": Decimal("20.00"),
            "pnl_rupees": Decimal("1500.00"),
        }

        # Mock option selection
        with patch("app.core.strategy_engine.get_option_details") as mock_opt:
            mock_opt.return_value = {
                "symbol": "NIFTY27JUN2423100CE",
                "strike": 23100,
                "expiry": date.today(),
            }
            engine.load_config({
                "r1": 23200, "r2": 23250, "r3": 23300,
                "s1": 23100, "s2": 23050, "s3": 23000,
                "lot_size": 75,
                "target_points": 20,
                "sl_points": 10,
                "paper_trade": True,
            })
            engine.is_running = True
            yield engine

@pytest.mark.asyncio
async def test_startup_no_trigger_on_first_tick(engine):
    """
    On the very first tick (last_nifty_price is None), 
    it should not trigger an entry even if we are past the level.
    """
    # Nifty starts at 23000, which is below S1 (23100), but first tick shouldn't trigger L1
    await engine.on_nifty_tick(Decimal("23000"))
    assert engine.ce.state == State.IDLE
    assert engine.last_nifty_price == Decimal("23000")

@pytest.mark.asyncio
async def test_crossover_triggers_l1(engine):
    """
    It should trigger Level 1 only when price crosses the S1 level from above.
    """
    # 1. First tick to establish last_nifty_price = 23120 (above S1)
    await engine.on_nifty_tick(Decimal("23120"))
    assert engine.ce.state == State.IDLE

    # 2. Second tick crosses below S1 (23100) -> should trigger CE L1
    await engine.on_nifty_tick(Decimal("23090"))
    assert engine.ce.state == State.L1_ENTERED
    assert engine.ce.lots == 1

@pytest.mark.asyncio
async def test_cooldown_blocks_immediate_l2_entry(engine):
    """
    After entering L1, a subsequent tick crossing S2 within 60s cooldown 
    should NOT trigger L2.
    """
    # 1. Establish baseline
    await engine.on_nifty_tick(Decimal("23120"))
    
    # 2. Trigger L1 at time T = 0
    t0 = 1000.0
    with patch("time.time", return_value=t0):
        await engine.on_nifty_tick(Decimal("23090"))
    assert engine.ce.state == State.L1_ENTERED

    # 3. Next tick crossing S2 (23050) at T = 1005 (5 seconds later) -> should block
    with patch("time.time", return_value=t0 + 5.0):
        await engine.on_nifty_tick(Decimal("23040"))
    # Still at L1_ENTERED due to cooldown
    assert engine.ce.state == State.L1_ENTERED

    # 3.5. Price moves back above S2 at T = 1030
    await engine.on_nifty_tick(Decimal("23060"))

    # 4. Next tick crossing S2 at T = 1065 (65 seconds later) -> should trigger L2
    with patch("time.time", return_value=t0 + 65.0):
        await engine.on_nifty_tick(Decimal("23040"))
    assert engine.ce.state == State.L2_ENTERED
    assert engine.ce.lots == 2

@pytest.mark.asyncio
async def test_concurrent_ticks_ignored(engine):
    """
    If a tick is already being processed, subsequent ticks should be ignored 
    to prevent concurrency race conditions.
    """
    import asyncio
    
    # We will patch engine._process_side to sleep for a bit to simulate processing time
    original_process_side = engine._process_side
    
    async def mock_process_side(side, nifty_ltp, prev_nifty):
        await asyncio.sleep(0.05)  # Simulate slow processing/DB write
        await original_process_side(side, nifty_ltp, prev_nifty)
        
    engine._process_side = mock_process_side
    
    # Trigger level crossing: establish baseline 23120, then drop to 23090 (cross S1)
    await engine.on_nifty_tick(Decimal("23120"))
    
    # Fire first tick (starts processing, will sleep for 0.05s)
    task1 = asyncio.create_task(engine.on_nifty_tick(Decimal("23090")))
    
    # Wait a small amount of time to let task1 start and enter mock_process_side
    await asyncio.sleep(0.01)
    assert engine._is_processing_tick is True
    
    # Fire second tick (should be ignored immediately because self._is_processing_tick is True)
    await engine.on_nifty_tick(Decimal("23090"))
    
    # Wait for the first tick to finish
    await task1
    assert engine._is_processing_tick is False
    
    # Verify the first tick was processed (state is now L1_ENTERED)
    assert engine.ce.state == State.L1_ENTERED
