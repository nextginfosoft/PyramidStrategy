import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import AsyncMock, patch

from app.core.destiny_engine import DestinyStrategyEngine
from app.models.models import StrategyConfig, User


from app.db.database import SessionLocal, init_db

@pytest.fixture(autouse=True)
def setup_database():
    init_db()

@pytest.fixture
def mock_user_and_config():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "destiny_user").first()
        if not user:
            user = User(username="destiny_user", hashed_password="hashed_pw", is_approved=True)
            db.add(user)
            db.commit()
            db.refresh(user)

        user_id = user.id
        from app.models.models import Trade
        db.query(Trade).filter(Trade.user_id == user_id).delete()
        db.query(StrategyConfig).filter(StrategyConfig.user_id == user_id).delete()
        db.commit()
        config = StrategyConfig(
            user_id=user_id,
            r1=24100.0,
            s1=23900.0,
            r2=24200.0,
            r3=24300.0,
            s2=23800.0,
            s3=23700.0,
            lot_size=75,
            target_points=30.0,
            sl_points=30.0,
            paper_trade=True,
            is_active=True,
            strategy_type="DESTINY"
        )
        db.add(config)
        db.commit()
        return user_id
    finally:
        db.close()


@pytest.mark.asyncio
async def test_destiny_engine_pe_entry_and_target(mock_user_and_config, monkeypatch):
    monkeypatch.setenv("MOCK_TIME", "10:00")
    user_id = mock_user_and_config
    engine = DestinyStrategyEngine(user_id=user_id)
    engine.start()

    assert engine.r_level == Decimal("24100.00")
    assert engine.s_level == Decimal("23900.00")

    # Tick below R - No trade
    await engine.on_nifty_tick(Decimal("24050.00"))
    assert engine.active_pe_trade is None

    # Tick hits R (24100) -> Triggers PE Entry
    await engine.on_nifty_tick(Decimal("24100.00"))
    assert engine.active_pe_trade is not None
    assert engine.active_pe_trade["side"] == "PE"
    assert engine.active_pe_trade["target_price"] == engine.active_pe_trade["entry_price"] + Decimal("30.00")

    # Move NIFTY lower to increase PE option value and hit target (23950 -> option price 205 >= 135)
    target_trigger_nifty = Decimal("23950.00")
    await engine.on_nifty_tick(target_trigger_nifty)

    # Trade should exit on target and mark R level completed
    assert engine.active_pe_trade is None
    assert engine.r_level_completed is True


@pytest.mark.asyncio
async def test_destiny_engine_custom_params(mock_user_and_config):
    user_id = mock_user_and_config
    engine = DestinyStrategyEngine(user_id=user_id)
    engine.load_config({
        "r1": 24500.0,
        "s1": 24000.0,
        "lot_size": 130,
        "target_points": 45.0,
        "sl_points": 20.0,
        "squareoff_time": "15:15",
        "paper_trade": True,
        "strategy_type": "DESTINY",
    })

    assert engine.lot_size == 130
    assert engine.target_pts == Decimal("45.0")
    assert engine.sl_pts == Decimal("20.0")


@pytest.mark.asyncio
async def test_destiny_engine_one_trade_per_day_limit(mock_user_and_config, monkeypatch):
    monkeypatch.setenv("MOCK_TIME", "10:00")
    user_id = mock_user_and_config
    engine = DestinyStrategyEngine(user_id=user_id)
    engine.start()

    # Hit R level (24100) -> Triggers PE Entry
    await engine.on_nifty_tick(Decimal("24050.00"))
    await engine.on_nifty_tick(Decimal("24100.00"))
    assert engine.active_pe_trade is not None

    # Exit PE trade on Target
    await engine.on_nifty_tick(Decimal("23950.00"))
    assert engine.active_pe_trade is None
    assert engine.r_level_completed is True
    assert engine.s_level_completed is True

    # Nifty now drops to S level (23900.00) -> Should NOT trigger CE trade because 1 trade limit was reached
    await engine.on_nifty_tick(Decimal("23890.00"))
    assert engine.active_ce_trade is None
    assert engine.active_pe_trade is None
    assert engine.target_pts == Decimal("30.0")
    assert engine.sl_pts == Decimal("30.0")
