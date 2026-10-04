"""Phase 4: `underlying` on the REST/WebSocket layer (NIFTY default, BANKNIFTY paper-only)."""
import asyncio
import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import analytics, backtest, config as config_routes, strategy, trades
from app.api.routes.session import require_auth
from app.core.engine_manager import EngineManager
from app.core.time_rules import today_ist
from app.db.database import Base, get_db
from app.models.models import DailyPnL, StrategyConfig, Trade, User

LEVELS = dict(r1=100, r2=110, r3=120, s1=90, s2=80, s3=70)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(id=1, username="trader", hashed_password="x", is_approved=True))
    db.commit()
    yield db
    db.close()


@pytest.fixture
def manager():
    """Isolated engine manager patched into the route modules."""
    m = EngineManager()
    with patch("app.core.engine_manager.engine_manager", m), \
         patch.object(config_routes, "engine_manager", m), \
         patch.object(strategy, "engine_manager", m), \
         patch("app.core.engine_manager.SessionLocal") as sl, \
         patch("app.services.kite_service.get_user_kite_service") as gk:
        sl.return_value.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        gk.return_value = MagicMock()
        yield m


@pytest.fixture
def client(db_session, manager):
    app = FastAPI()
    for r in (config_routes.router, strategy.router, trades.router, analytics.router, backtest.router):
        app.include_router(r)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[require_auth] = lambda: db_session.get(User, 1)
    return TestClient(app)


def _trade(underlying, **kw):
    base = dict(user_id=1, trade_date=today_ist(), underlying=underlying, side="CE", level="S1",
                instrument=f"{underlying}X", strike=100, expiry=today_ist(), action="BUY",
                lots=1, qty=1, avg_price=1, status="OPEN", is_paper_trade=True)
    base.update(kw)
    return Trade(**base)


class TestConfigRoutes:
    def test_invalid_underlying_rejected(self, client):
        assert client.get("/config/strategy?underlying=FINNIFTY").status_code == 400

    def test_default_is_nifty(self, client):
        r = client.get("/config/strategy")
        assert r.status_code == 200 and r.json()["underlying"] == "NIFTY"

    def test_banknifty_default_levels_scaled(self, client):
        j = client.get("/config/strategy?underlying=BANKNIFTY").json()
        assert j["underlying"] == "BANKNIFTY" and j["lot_size"] == 30
        assert j["r1"] > 50000 and j["paper_trade"] is True

    def test_banknifty_live_request_saved_as_paper(self, client):
        r = client.post("/config/strategy", json={**LEVELS, "underlying": "BANKNIFTY", "paper_trade": False})
        assert r.status_code == 200
        assert r.json()["underlying"] == "BANKNIFTY" and r.json()["paper_trade"] is True

    def test_configs_are_independent_per_instrument(self, client, db_session):
        client.post("/config/strategy", json={**LEVELS, "paper_trade": False})  # NIFTY, live
        client.post("/config/strategy", json={**LEVELS, "underlying": "BANKNIFTY"})
        active = {c.underlying: c for c in db_session.query(StrategyConfig).filter_by(is_active=True)}
        assert set(active) == {"NIFTY", "BANKNIFTY"}  # saving BANKNIFTY did not deactivate NIFTY
        assert active["NIFTY"].paper_trade is False
        # saving NIFTY again deactivates only the old NIFTY row
        client.post("/config/strategy", json={**LEVELS, "r1": 105})
        assert db_session.query(StrategyConfig).filter_by(is_active=True).count() == 2
        assert float(client.get("/config/strategy").json()["r1"]) == 105
        assert float(client.get("/config/strategy?underlying=BANKNIFTY").json()["r1"]) == 100

    def test_saving_creates_banknifty_engine(self, client, manager):
        client.post("/config/strategy", json={**LEVELS, "underlying": "BANKNIFTY"})
        assert (1, "BANKNIFTY") in manager._instrument_engines
        assert 1 not in manager._engines  # NIFTY engine untouched

    def test_history_filtered(self, client):
        client.post("/config/strategy", json=LEVELS)
        client.post("/config/strategy", json={**LEVELS, "underlying": "BANKNIFTY"})
        assert {c["underlying"] for c in client.get("/config/strategy/history").json()} == {"NIFTY"}
        assert {c["underlying"] for c in client.get("/config/strategy/history?underlying=BANKNIFTY").json()} == {"BANKNIFTY"}


class TestStrategyRoutes:
    def test_status_per_instrument(self, client):
        assert client.get("/strategy/status").json()["underlying"] == "NIFTY"
        assert client.get("/strategy/status?underlying=BANKNIFTY").json()["underlying"] == "BANKNIFTY"

    def test_start_requires_config_for_that_instrument(self, client):
        client.post("/config/strategy", json=LEVELS)  # NIFTY only
        r = client.post("/strategy/start?underlying=BANKNIFTY")
        assert r.status_code == 400 and "BANKNIFTY" in r.json()["detail"]

    def test_start_banknifty_is_paper(self, client, manager):
        client.post("/config/strategy", json={**LEVELS, "underlying": "BANKNIFTY"})
        with patch.object(strategy, "get_user_kite_service") as gk, \
             patch("app.core.safety_checks.run_safety_checks", return_value=(True, [], [])):
            gk.return_value = MagicMock(_ticker_running=True, is_authenticated=lambda: False)
            r = client.post("/strategy/start?underlying=BANKNIFTY")
        assert r.status_code == 200, r.text
        assert r.json()["underlying"] == "BANKNIFTY" and r.json()["paper_trade"] is True
        assert manager.find_engine(1, "BANKNIFTY").is_running
        assert manager.find_engine(1, "NIFTY") is None

    def test_reset_only_clears_that_instrument(self, client, db_session):
        db_session.add_all([_trade("NIFTY"), _trade("BANKNIFTY")])
        db_session.add_all([DailyPnL(user_id=1, trade_date=today_ist()),
                            DailyPnL(user_id=1, trade_date=today_ist(), underlying="BANKNIFTY")])
        db_session.commit()
        assert client.post("/strategy/reset-daily?underlying=BANKNIFTY").status_code == 200
        assert [t.underlying for t in db_session.query(Trade)] == ["NIFTY"]
        assert [p.underlying for p in db_session.query(DailyPnL)] == ["NIFTY"]


class TestTradeAndAnalyticsRoutes:
    def test_trades_filtered(self, client, db_session):
        db_session.add_all([_trade("NIFTY"), _trade("BANKNIFTY"), _trade("BANKNIFTY", level="S2")])
        db_session.commit()
        assert len(client.get("/trades/today").json()) == 1
        bn = client.get("/trades/today?underlying=BANKNIFTY").json()
        assert len(bn) == 2 and all(t["underlying"] == "BANKNIFTY" for t in bn)
        assert len(client.get("/trades/history?underlying=BANKNIFTY").json()) == 2

    def test_pnl_today_filtered(self, client, db_session):
        db_session.add_all([_trade("NIFTY", action="EXIT", pnl=100), _trade("BANKNIFTY", action="EXIT", pnl=-40)])
        db_session.commit()
        assert client.get("/trades/pnl/today").json()["gross_pnl"] == 100
        assert client.get("/trades/pnl/today?underlying=BANKNIFTY").json()["gross_pnl"] == -40

    def test_pnl_history_and_summary_filtered(self, client, db_session):
        d = date(2026, 10, 1)
        db_session.add_all([DailyPnL(user_id=1, trade_date=d, net_pnl=500, gross_pnl=500),
                            DailyPnL(user_id=1, trade_date=d, underlying="BANKNIFTY", net_pnl=-200, gross_pnl=-200)])
        db_session.commit()
        assert [p["net_pnl"] for p in client.get("/trades/pnl/history?underlying=BANKNIFTY").json()] == [-200]
        q = "start_date=2026-10-01&end_date=2026-10-01"
        assert client.get(f"/analytics/pnl-summary?{q}").json()["summary"]["total_net_pnl"] == 500
        assert client.get(f"/analytics/pnl-summary?{q}&underlying=BANKNIFTY").json()["summary"]["total_net_pnl"] == -200

    def test_export_filtered(self, client, db_session):
        db_session.add_all([_trade("NIFTY", instrument="NIFTYONLY"), _trade("BANKNIFTY", instrument="BNONLY")])
        db_session.commit()
        csv_text = client.get("/trades/export?underlying=BANKNIFTY").text
        assert "BNONLY" in csv_text and "NIFTYONLY" not in csv_text


class TestBacktest:
    def _payload(self, **extra):
        return {"start_date": "2026-06-18", "end_date": "2026-06-18",
                "config": {"r1": 55300, "r2": 55400, "r3": 55500, "s1": 54700, "s2": 54600, "s3": 54500,
                           "lot_size": 30, "target_points": 20, "sl_points": 10}, **extra}

    def test_banknifty_backtest_uses_banknifty_prices(self, client):
        from app.services.backtesting import get_nifty_data_for_day
        assert min(get_nifty_data_for_day("2026-06-18", "BANKNIFTY")) > 40000
        assert max(get_nifty_data_for_day("2026-06-18")) < 30000  # NIFTY series unchanged
        r = client.post("/backtest", json=self._payload(underlying="BANKNIFTY"))
        assert r.status_code == 200 and "primary" in r.json()

    def test_invalid_underlying(self, client):
        assert client.post("/backtest", json=self._payload(underlying="FINNIFTY")).status_code == 400


class TestEngineMessages:
    def test_status_messages_tagged_with_underlying(self):
        from app.core.strategy_engine import StrategyEngine
        e = StrategyEngine(user_id=1, underlying="BANKNIFTY")
        sent = []

        async def fake_broadcast(uid, msg):
            sent.append(msg)

        e.broadcast_fn = fake_broadcast
        with patch("app.services.kite_service.get_user_kite_service") as gk:
            gk.return_value = MagicMock(is_authenticated=lambda: False, get_status=lambda: {})
            from decimal import Decimal
            asyncio.run(e._broadcast_status(Decimal("55000")))
        assert sent and sent[0]["underlying"] == "BANKNIFTY"
        assert e.get_full_status()["underlying"] == "BANKNIFTY"


class TestDestinyBacktestInstrument:
    """dev's Destiny backtest (model-priced options) must follow the instrument."""

    def test_banknifty_destiny_backtest_uses_banknifty_contract(self):
        from app.services.backtesting import run_destiny_single_backtest
        from app.core.time_rules import TUESDAY_HOLIDAYS  # noqa: F401 - ensures module import
        prices = [55000.0] * 5 + [55110.0, 55090.0] + [54850.0] * 10  # crosses resistance 55100, then falls (PE gains)
        cfg = {"r1": 55100, "s1": 54000, "lot_size": 30, "target_points": 30, "sl_points": 30,
               "squareoff_time": "15:20", "strategy_type": "DESTINY", "underlying": "BANKNIFTY"}
        trades = run_destiny_single_backtest("2026-10-05", prices, cfg)
        assert trades, "expected a PE entry on the resistance cross"
        t = trades[0]
        assert t["symbol"].startswith("BANKNIFTY26OCT") and t["symbol"].endswith("PE")
        assert t["strike"] % 100 == 0 and t["qty"] == 30

    def test_nifty_destiny_backtest_unchanged(self):
        from app.services.backtesting import run_destiny_single_backtest
        prices = [23000.0] * 5 + [23110.0, 23090.0] + [23050.0] * 10
        cfg = {"r1": 23100, "s1": 22000, "lot_size": 65, "target_points": 30, "sl_points": 30,
               "squareoff_time": "15:20", "strategy_type": "DESTINY"}
        trades = run_destiny_single_backtest("2026-10-05", prices, cfg)
        assert trades and trades[0]["symbol"].startswith("NIFTY") and not trades[0]["symbol"].startswith("BANK")
