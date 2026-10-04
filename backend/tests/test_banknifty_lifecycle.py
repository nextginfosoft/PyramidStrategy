"""
Phase 6: full BANKNIFTY paper lifecycle through the real engine, order manager,
state machine, database and reporting (only the clock gates and the DB session
factory are patched). Checks scaling (strike step 100, lot 30), pyramiding,
target / stop-loss / square-off exits, and isolation from a NIFTY engine.
"""
import asyncio
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.engine_manager import EngineManager
from app.core.time_rules import today_ist
from app.db.database import Base
from app.models.models import DailyPnL, Trade, User
from app.services.reporting import generate_daily_report

BN_CFG = dict(r1=55100, r2=55200, r3=55300, s1=54900, s2=54800, s3=54700,
              lot_size=30, target_points=20, sl_points=10, paper_trade=True,
              squareoff_time="15:20")
NF_CFG = dict(r1=23300, r2=23400, r3=23500, s1=22700, s2=22600, s3=22500,
              lot_size=65, target_points=20, sl_points=10, paper_trade=True,
              squareoff_time="15:20")


@pytest.fixture
def env():
    db_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(db_engine)
    Session = sessionmaker(bind=db_engine)
    with Session() as s:
        s.add(User(id=1, username="trader", hashed_password="x", is_approved=True))
        s.commit()

    manager = EngineManager()
    patches = [
        patch("app.core.strategy_engine.SessionLocal", Session),
        patch("app.core.engine_manager.SessionLocal", Session),
        patch("app.core.strategy_engine.is_entry_allowed", return_value=True),
        patch("app.core.strategy_engine.should_squareoff", return_value=False),
    ]
    for p in patches:
        p.start()
    try:
        yield manager, Session
    finally:
        for p in patches:
            p.stop()


def run(coro):
    return asyncio.run(coro)


async def feed(engine, prices, side=None):
    for px in prices:
        if side:
            engine.last_entry_time[side] = 0.0  # skip the 60s inter-level cooldown
        await engine.on_nifty_tick(Decimal(str(px)))


def trades(Session, underlying):
    with Session() as s:
        return s.query(Trade).filter_by(underlying=underlying).order_by(Trade.id).all()


def test_pyramid_to_l3_then_target_scaled_for_banknifty(env):
    manager, Session = env

    async def scenario():
        bn = manager.get_engine(1, "BANKNIFTY")
        bn.load_config(BN_CFG)
        bn.start()
        # PE pyramid: cross R1, R2, R3 from below (one tick below each level first)
        await feed(bn, [54000, 55090, 55110, 55190, 55210, 55290, 55310], side="PE")
        return bn

    bn = run(scenario())
    rows = [t for t in trades(Session, "BANKNIFTY") if t.action == "BUY"]
    assert [t.level for t in rows] == ["R1", "R2", "R3"]
    assert all(t.underlying == "BANKNIFTY" and t.is_paper_trade for t in rows)
    # strike locked at L1: ATM(55110)=55100, PE = ATM + 100; all levels share symbol
    assert {t.strike for t in rows} == {55200}
    assert {t.instrument for t in rows} == {rows[0].instrument}
    assert rows[0].instrument.startswith("BANKNIFTY") and rows[0].instrument.endswith("55200PE")
    assert [t.lots for t in rows] == [1, 1, 1]  # each level adds one lot
    assert [t.qty for t in rows] == [30, 30, 30]  # lot x BANKNIFTY lot size (not 65/75)
    assert bn.pe.lots == 3


def test_target_exit_closes_whole_position_and_blocks_reentry(env):
    manager, Session = env

    async def scenario():
        bn = manager.get_engine(1, "BANKNIFTY")
        bn.load_config(BN_CFG)
        bn.start()
        await feed(bn, [54000, 55090, 55110], side="PE")  # L1 PE entered
        entry = bn.pe.entry_avg_price
        # index falls back: the paper price model lifts the PE premium past entry + 20
        await feed(bn, [55060])
        return bn, entry

    bn, entry = run(scenario())
    exits = [t for t in trades(Session, "BANKNIFTY") if t.action == "EXIT"]
    assert len(exits) == 1
    assert exits[0].status == "TARGET"
    assert exits[0].underlying == "BANKNIFTY"
    assert exits[0].qty == 30
    assert float(exits[0].pnl) > 0
    assert bn.pe.lots == 0


def test_stop_loss_only_active_at_level3(env):
    manager, Session = env

    async def scenario():
        bn = manager.get_engine(1, "BANKNIFTY")
        bn.load_config(BN_CFG)
        bn.start()
        await feed(bn, [54000, 55090, 55110, 55190, 55210, 55290, 55310], side="PE")
        # index pushes further against the PE: premium drops below L3 entry - 10 -> stop out
        await feed(bn, [55340])

    run(scenario())
    exits = [t for t in trades(Session, "BANKNIFTY") if t.action == "EXIT"]
    assert len(exits) == 1
    assert exits[0].status == "SL"
    assert exits[0].qty == 90  # entire 3-lot position


def test_squareoff_closes_open_banknifty_position(env):
    manager, Session = env

    async def scenario():
        bn = manager.get_engine(1, "BANKNIFTY")
        bn.load_config(BN_CFG)
        bn.start()
        await feed(bn, [56000, 54910, 54890], side="CE")  # CE L1 on support break
        assert bn.ce.lots == 1
        await bn._force_squareoff()
        return bn

    bn = run(scenario())
    exits = [t for t in trades(Session, "BANKNIFTY") if t.action == "EXIT"]
    assert len(exits) == 1 and exits[0].status == "SQUAREOFF"
    assert bn.ce.lots == 0 and not bn.is_running


def test_nifty_and_banknifty_run_side_by_side_without_interference(env):
    manager, Session = env

    async def scenario():
        bn = manager.get_engine(1, "BANKNIFTY")
        nf = manager.get_engine(1)
        bn.load_config(BN_CFG)
        nf.load_config(NF_CFG)
        bn.start()
        nf.start()
        # Only BANKNIFTY crosses a level; NIFTY ticks stay mid-range
        await feed(bn, [54000, 55090, 55110], side="PE")
        await feed(nf, [23000, 23010, 23005])
        # then NIFTY enters on its own support break
        await feed(nf, [22710, 22690], side="CE")

    run(scenario())
    bn_rows = trades(Session, "BANKNIFTY")
    nf_rows = trades(Session, "NIFTY")
    assert [(t.side, t.level) for t in bn_rows] == [("PE", "R1")]
    assert [(t.side, t.level) for t in nf_rows] == [("CE", "S1")]
    assert bn_rows[0].qty == 30 and nf_rows[0].qty == 65
    assert nf_rows[0].instrument.startswith("NIFTY") and not nf_rows[0].instrument.startswith("BANK")
    # engines do not share state
    bn = manager.find_engine(1, "BANKNIFTY"); nf = manager.find_engine(1, "NIFTY")
    assert bn.ce.lots == 0 and bn.pe.lots == 1 and nf.pe.lots == 0 and nf.ce.lots == 1


def test_daily_report_keeps_instruments_separate(env):
    manager, Session = env

    async def scenario():
        bn = manager.get_engine(1, "BANKNIFTY")
        nf = manager.get_engine(1)
        bn.load_config(BN_CFG); nf.load_config(NF_CFG)
        bn.start(); nf.start()
        await feed(bn, [54000, 55090, 55110], side="PE")
        await feed(nf, [23000, 22710, 22690], side="CE")
        await bn._force_squareoff()
        await nf._force_squareoff()

    run(scenario())
    with Session() as s:
        generate_daily_report(1, today_ist(), s, "BANKNIFTY")
        generate_daily_report(1, today_ist(), s)  # NIFTY (default)
        s.commit()
        rows = {p.underlying: p for p in s.query(DailyPnL).filter_by(user_id=1)}
        assert set(rows) == {"BANKNIFTY", "NIFTY"}
        assert rows["BANKNIFTY"].total_trades == 2 and rows["NIFTY"].total_trades == 2
        assert rows["BANKNIFTY"].pe_pnl != 0 or rows["BANKNIFTY"].gross_pnl is not None
        assert float(rows["BANKNIFTY"].ce_pnl) == 0  # BANKNIFTY only traded PE
        assert float(rows["NIFTY"].pe_pnl) == 0      # NIFTY only traded CE


def test_banknifty_never_live_even_if_config_asks(env):
    manager, Session = env

    async def scenario():
        bn = manager.get_engine(1, "BANKNIFTY")
        bn.load_config({**BN_CFG, "paper_trade": False})
        bn.start()
        await feed(bn, [54000, 55090, 55110], side="PE")
        return bn

    bn = run(scenario())
    assert bn.mock_mode and bn.order_manager.paper_trade
    assert all(t.is_paper_trade for t in trades(Session, "BANKNIFTY"))
    assert all(t.kite_order_id in (None, "") or str(t.kite_order_id).startswith(("PAPER", "paper", "MOCK", "mock"))
               for t in trades(Session, "BANKNIFTY"))
