"""Phase 2: `underlying` column + per-instrument DailyPnL uniqueness."""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.core.instruments import get_instrument
from app.models.models import DailyPnL, StrategyConfig, Trade, User


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(username="u1"))
    session.commit()
    yield session
    session.close()


def test_defaults_to_nifty(db):
    cfg = StrategyConfig(user_id=1, r1=1, r2=2, r3=3, s1=1, s2=2, s3=3)
    db.add(cfg); db.commit()
    assert cfg.underlying == "NIFTY"
    assert cfg.lot_size == get_instrument("NIFTY").lot_size


def test_trade_defaults_to_nifty(db):
    t = Trade(user_id=1, trade_date=date(2026, 10, 1), side="CE", level="S1",
              instrument="NIFTY26O0623200CE", strike=23200, expiry=date(2026, 10, 6),
              action="BUY", lots=1, qty=65)
    db.add(t); db.commit()
    assert t.underlying == "NIFTY"


def test_daily_pnl_one_row_per_underlying_per_day(db):
    d = date(2026, 10, 1)
    db.add_all([DailyPnL(user_id=1, trade_date=d),
                DailyPnL(user_id=1, trade_date=d, underlying="BANKNIFTY")])
    db.commit()  # both allowed
    db.add(DailyPnL(user_id=1, trade_date=d, underlying="BANKNIFTY"))
    with pytest.raises(IntegrityError):
        db.commit()
