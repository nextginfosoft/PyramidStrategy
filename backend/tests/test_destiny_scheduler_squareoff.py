"""
The scheduler (main.py check_time_triggers) calls ``engine._force_squareoff()`` at each
user's square-off minute as a backstop for the tick-driven square-off. Pyramid's engine
has it; Destiny's did not, so the call raised AttributeError and did nothing - leaving a
Destiny position open if NIFTY ticks had stopped arriving.
"""

import asyncio
import inspect
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def setup_database():
    from app.db.database import init_db
    init_db()


@pytest.fixture
def user_id():
    from app.db.database import SessionLocal
    from app.models.models import StrategyConfig, Trade, User

    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "destiny_sched_sq_user").first()
        if not user:
            user = User(username="destiny_sched_sq_user", hashed_password="hashed_pw", is_approved=True)
            db.add(user)
            db.commit()
            db.refresh(user)
        db.query(Trade).filter(Trade.user_id == user.id).delete()
        db.query(StrategyConfig).filter(StrategyConfig.user_id == user.id).delete()
        db.add(StrategyConfig(
            user_id=user.id, r1=24100.0, s1=23900.0, r2=24200.0, r3=24300.0,
            s2=23800.0, s3=23700.0, lot_size=75, target_points=30.0, sl_points=30.0,
            paper_trade=True, is_active=True, strategy_type="DESTINY",
        ))
        db.commit()
        return user.id


@pytest.fixture(autouse=True)
def quiet_side_effects(monkeypatch):
    """Square-off sends notifications, a gamification quote and an EOD report; none of that is under test."""
    monkeypatch.setattr("app.services.notification.get_user_notification_service", lambda uid: MagicMock())
    monkeypatch.setattr("app.gamification.hooks.fire_squareoff_quote", AsyncMock())
    monkeypatch.setattr("app.gamification.hooks.fire_engine_stop_quote", AsyncMock())
    monkeypatch.setattr("app.services.reporting.send_daily_report", AsyncMock())


def _engine(user_id, monkeypatch):
    from app.core.destiny_engine import DestinyStrategyEngine
    monkeypatch.setenv("MOCK_TIME", "10:00")
    engine = DestinyStrategyEngine(user_id=user_id)
    engine.start()
    engine._broadcast = AsyncMock()
    return engine


class TestSchedulerHookExists:
    def test_destiny_engine_has_the_coroutine_the_scheduler_awaits(self):
        from app.core.destiny_engine import DestinyStrategyEngine
        assert inspect.iscoroutinefunction(DestinyStrategyEngine._force_squareoff)

    def test_both_engine_types_satisfy_the_scheduler_contract(self):
        from app.core.destiny_engine import DestinyStrategyEngine
        from app.core.strategy_engine import StrategyEngine
        for cls in (DestinyStrategyEngine, StrategyEngine):
            assert inspect.iscoroutinefunction(cls._force_squareoff), cls.__name__


class TestForceSquareoff:
    @pytest.mark.asyncio
    async def test_closes_an_open_trade_with_no_further_tick(self, user_id, monkeypatch):
        engine = _engine(user_id, monkeypatch)
        await engine.on_nifty_tick(Decimal("24050.00"))
        await engine.on_nifty_tick(Decimal("24100.00"))  # crosses R -> PE entry
        assert engine.active_pe_trade is not None

        await engine._force_squareoff()  # the feed has dropped: no tick arrives, only the scheduler fires

        assert engine.active_pe_trade is None
        assert engine.is_running is False  # same end state as the tick-driven square-off
        from app.db.database import SessionLocal
        from app.models.models import Trade
        with SessionLocal() as db:
            statuses = {t.status for t in db.query(Trade).filter(Trade.user_id == user_id).all()}
        assert "SQUAREOFF" in statuses

    @pytest.mark.asyncio
    async def test_works_even_if_no_tick_was_ever_received(self, user_id, monkeypatch):
        engine = _engine(user_id, monkeypatch)
        assert engine.last_nifty_price is None
        await engine._force_squareoff()  # nothing open, no price known: must not raise
        assert engine.is_running is False

    @pytest.mark.asyncio
    async def test_does_nothing_when_the_engine_is_not_running(self, user_id, monkeypatch):
        engine = _engine(user_id, monkeypatch)
        engine.is_running = False
        engine._squareoff_all = AsyncMock()

        await engine._force_squareoff()

        engine._squareoff_all.assert_not_awaited()


class TestOverlapGuard:
    @pytest.mark.asyncio
    async def test_tick_path_and_scheduler_in_the_same_minute_square_off_once(self, user_id, monkeypatch):
        engine = _engine(user_id, monkeypatch)
        calls = []

        async def slow_squareoff(reason, nifty_ltp):
            calls.append(reason)
            await asyncio.sleep(0.02)  # yields, so the second caller sees the first in progress

        engine._squareoff_all = slow_squareoff

        await asyncio.gather(
            engine._run_squareoff("3:20 PM Cutoff Time Reached", Decimal("24000")),
            engine._force_squareoff(),
        )

        assert calls == ["3:20 PM Cutoff Time Reached"]

    @pytest.mark.asyncio
    async def test_the_guard_is_released_afterwards(self, user_id, monkeypatch):
        engine = _engine(user_id, monkeypatch)
        engine._squareoff_all = AsyncMock()

        await engine._run_squareoff("first", Decimal("24000"))
        await engine._run_squareoff("second", Decimal("24000"))

        assert engine._squareoff_all.await_count == 2
        assert engine._squareoff_in_progress is False

    @pytest.mark.asyncio
    async def test_the_guard_is_released_even_if_square_off_raises(self, user_id, monkeypatch):
        engine = _engine(user_id, monkeypatch)
        engine._squareoff_all = AsyncMock(side_effect=RuntimeError("broker down"))

        with pytest.raises(RuntimeError):
            await engine._run_squareoff("boom", Decimal("24000"))

        assert engine._squareoff_in_progress is False  # a retry at the next tick must still be possible
