"""
Tests for the user-configurable "Ratchet Step" setting (Destiny only).

Opt-in: NULL/unset keeps today's flat target exit unchanged. Once set, hitting
target_points locks that price as a floor instead of exiting, climbs the floor by
ratchet_step_points on every further milestone, and only closes once price drops
back below the current floor. SL remains a fixed, unconditional floor throughout.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock

from pydantic import ValidationError

from app.schemas.schemas import StrategyConfigCreate
from app.services.backtesting import run_destiny_single_backtest


def make_config(**overrides):
    payload = dict(
        r1=24100.0, s1=23900.0, r2=24200.0, r3=24300.0, s2=23800.0, s3=23700.0,
        squareoff_time="15:20", strategy_type="DESTINY",
    )
    payload.update(overrides)
    return StrategyConfigCreate(**payload)


# ── schema validation ─────────────────────────────────────────────────────────

class TestRatchetStepSchema:
    def test_defaults_to_none(self):
        assert make_config().ratchet_step_points is None

    @pytest.mark.parametrize("blank", [None, "", "   "])
    def test_blank_becomes_none(self, blank):
        assert make_config(ratchet_step_points=blank).ratchet_step_points is None

    @pytest.mark.parametrize("zero", [0, 0.0, "0", "0.0", "  0  "])
    def test_zero_means_off_too(self, zero):
        assert make_config(ratchet_step_points=zero).ratchet_step_points is None

    def test_valid_value_is_kept(self):
        assert make_config(ratchet_step_points=10).ratchet_step_points == 10.0
        assert make_config(ratchet_step_points="15.5").ratchet_step_points == 15.5

    @pytest.mark.parametrize("bad", [-5, "-5", -0.01])
    def test_negative_rejected(self, bad):
        with pytest.raises(ValidationError):
            make_config(ratchet_step_points=bad)

    def test_non_numeric_string_rejected(self):
        with pytest.raises(ValidationError):
            make_config(ratchet_step_points="abc")


# ── route round-trip (config rows are append-only, so every writer must carry it) ─

class TestRatchetStepRoute:
    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.routes.config import router
        from app.api.routes.admin import router as admin_router
        from app.api.routes.session import router as session_router, get_password_hash
        from app.db.database import SessionLocal, init_db
        from app.models.models import User

        init_db()
        with SessionLocal() as db:
            for username, is_admin in (("ratchet_user", False), ("ratchet_admin", True)):
                user = db.query(User).filter(User.username == username).first()
                if not user:
                    user = User(username=username, hashed_password=get_password_hash("pw12345!"),
                                is_approved=True, is_admin=is_admin)
                    db.add(user)
                else:
                    user.hashed_password = get_password_hash("pw12345!")
                    user.is_approved = True
                    user.is_admin = is_admin
            db.commit()

        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.include_router(admin_router, prefix="/api")  # admin_router already has its own "/admin" prefix
        app.include_router(session_router, prefix="/api")
        return TestClient(app)

    def _headers(self, client, username):
        login = client.post("/api/session/login", json={"username": username, "password": "pw12345!"})
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    @staticmethod
    def body(**overrides):
        payload = dict(
            r1=24100.0, s1=23900.0, r2=24200.0, r3=24300.0, s2=23800.0, s3=23700.0,
            lot_size=65, target_points=30, sl_points=30, paper_trade=True,
            squareoff_time="15:20", strategy_type="DESTINY",
        )
        payload.update(overrides)
        return payload

    def test_saved_value_is_returned_and_persisted(self, client):
        headers = self._headers(client, "ratchet_user")
        resp = client.post("/api/config/strategy", json=self.body(ratchet_step_points=10), headers=headers)
        assert resp.status_code == 200
        assert resp.json()["ratchet_step_points"] == 10.0

        got = client.get("/api/config/strategy?strategy_type=DESTINY", headers=headers)
        assert got.status_code == 200
        assert got.json()["ratchet_step_points"] == 10.0

    def test_blank_clears_it_back_to_off(self, client):
        headers = self._headers(client, "ratchet_user")
        client.post("/api/config/strategy", json=self.body(ratchet_step_points=10), headers=headers)
        resp = client.post("/api/config/strategy", json=self.body(ratchet_step_points=""), headers=headers)
        assert resp.status_code == 200
        assert resp.json()["ratchet_step_points"] is None

    def test_rejects_non_positive(self, client):
        headers = self._headers(client, "ratchet_user")
        resp = client.post("/api/config/strategy", json=self.body(ratchet_step_points=-1), headers=headers)
        assert resp.status_code == 422

    def test_engine_receives_the_setting_on_save(self, client):
        from app.core.engine_manager import engine_manager
        from app.db.database import SessionLocal
        from app.models.models import User

        headers = self._headers(client, "ratchet_user")
        client.post("/api/config/strategy", json=self.body(ratchet_step_points=12), headers=headers)
        with SessionLocal() as db:
            uid = db.query(User).filter(User.username == "ratchet_user").first().id
        assert engine_manager.get_engine(uid).ratchet_step_pts == Decimal("12")

    def test_admin_sync_levels_preserves_each_users_own_ratchet_value(self, client):
        """Global level sync must not silently reset a user's opted-in ratchet setting."""
        user_headers = self._headers(client, "ratchet_user")
        admin_headers = self._headers(client, "ratchet_admin")

        client.post("/api/config/strategy", json=self.body(ratchet_step_points=20), headers=user_headers)

        resp = client.post(
            "/api/admin/strategy/sync-levels",
            json={"r1": 24150.0, "r2": 24250.0, "r3": 24350.0,
                  "s1": 23950.0, "s2": 23850.0, "s3": 23750.0,
                  "strategy_type": "DESTINY"},
            headers=admin_headers,
        )
        assert resp.status_code == 200

        got = client.get("/api/config/strategy?strategy_type=DESTINY", headers=user_headers)
        assert got.json()["ratchet_step_points"] == 20.0
        assert got.json()["r1"] == 24150.0  # the sync itself did apply


# ── engine gating ─────────────────────────────────────────────────────────────

class TestDestinyEngineRatchet:
    @pytest.fixture(autouse=True)
    def setup_database(self):
        from app.db.database import init_db
        init_db()

    @pytest.fixture
    def user_id(self):
        from app.db.database import SessionLocal
        from app.models.models import StrategyConfig, Trade, User

        with SessionLocal() as db:
            user = db.query(User).filter(User.username == "destiny_ratchet_user").first()
            if not user:
                user = User(username="destiny_ratchet_user", hashed_password="hashed_pw", is_approved=True)
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

    @staticmethod
    def _engine(user_id, monkeypatch, mock_time="10:00", ratchet_step=None):
        from app.core.destiny_engine import DestinyStrategyEngine
        monkeypatch.setenv("MOCK_TIME", mock_time)
        engine = DestinyStrategyEngine(user_id=user_id)
        engine.start()
        if ratchet_step is not None:
            engine.load_config({"ratchet_step_points": ratchet_step})
        engine._broadcast = AsyncMock()
        return engine

    @pytest.mark.asyncio
    async def test_default_off_keeps_exact_legacy_behavior(self, user_id, monkeypatch):
        """Regression guard: with no ratchet configured, target still exits flat at +30."""
        engine = self._engine(user_id, monkeypatch)
        assert engine.ratchet_step_pts is None

        await engine.on_nifty_tick(Decimal("24050.00"))
        await engine.on_nifty_tick(Decimal("24100.00"))  # crosses R -> PE entry
        assert engine.active_pe_trade is not None
        entry_price = engine.active_pe_trade["entry_price"]
        target_price = engine.active_pe_trade["target_price"]
        assert target_price == entry_price + Decimal("30.00")

        # NIFTY falls -> PE option value rises; touching target exits immediately, flat.
        await engine.on_nifty_tick(Decimal("23950.00"))
        assert engine.active_pe_trade is None
        assert engine.r_level_completed is True

    @pytest.mark.asyncio
    async def test_arm_climb_and_exit_below_floor(self, user_id, monkeypatch):
        """Drive _check_active_trade_exits directly via get_option_ltp patching for exact control."""
        engine = self._engine(user_id, monkeypatch, ratchet_step=10)
        await engine.on_nifty_tick(Decimal("24050.00"))
        await engine.on_nifty_tick(Decimal("24100.00"))
        trade = engine.active_pe_trade
        assert trade is not None
        entry = trade["entry_price"]
        target_price = trade["target_price"]
        assert target_price == entry + Decimal("30.00")

        # get_option_ltp prioritizes re-deriving the price from nifty_ltp via
        # estimate_option_price over the cached _option_ltp value, so patch the
        # method itself to isolate the ratchet decision logic from option pricing.
        current_price = {"v": None}
        monkeypatch.setattr(engine, "get_option_ltp", lambda symbol, nifty_ltp=None: current_price["v"])

        # 1) Reach target exactly -> arms, does not exit
        current_price["v"] = target_price
        await engine._check_active_trade_exits(engine.last_nifty_price)
        assert engine.active_pe_trade is not None
        assert engine.active_pe_trade["locked_floor"] == target_price

        # 2) Climb past the next milestone -> floor ratchets up, still open
        current_price["v"] = target_price + Decimal("15")  # one full step (10) beyond floor
        await engine._check_active_trade_exits(engine.last_nifty_price)
        assert engine.active_pe_trade is not None
        assert engine.active_pe_trade["locked_floor"] == target_price + Decimal("10")

        # 3) Give back to just below the current floor -> exits TARGET
        current_price["v"] = target_price + Decimal("10") - Decimal("1")
        await engine._check_active_trade_exits(engine.last_nifty_price)
        assert engine.active_pe_trade is None
        assert engine.r_level_completed is True

    @pytest.mark.asyncio
    async def test_sl_wins_even_on_an_armed_trade(self, user_id, monkeypatch):
        engine = self._engine(user_id, monkeypatch, ratchet_step=10)
        await engine.on_nifty_tick(Decimal("24050.00"))
        await engine.on_nifty_tick(Decimal("24100.00"))
        trade = engine.active_pe_trade
        sl_price = trade["sl_price"]
        target_price = trade["target_price"]

        current_price = {"v": None}
        monkeypatch.setattr(engine, "get_option_ltp", lambda symbol, nifty_ltp=None: current_price["v"])

        # Arm it first
        current_price["v"] = target_price
        await engine._check_active_trade_exits(engine.last_nifty_price)
        assert engine.active_pe_trade["locked_floor"] == target_price

        # Then crash straight through SL in one tick (SL must still win)
        current_price["v"] = sl_price - Decimal("1")
        await engine._check_active_trade_exits(engine.last_nifty_price)
        assert engine.active_pe_trade is None

    @pytest.mark.asyncio
    async def test_disabling_mid_day_reverts_to_flat_exit_for_new_entries(self, user_id, monkeypatch):
        engine = self._engine(user_id, monkeypatch, ratchet_step=10)
        engine.load_config({"ratchet_step_points": None})
        assert engine.ratchet_step_pts is None

        await engine.on_nifty_tick(Decimal("24050.00"))
        await engine.on_nifty_tick(Decimal("24100.00"))
        await engine.on_nifty_tick(Decimal("23950.00"))
        assert engine.active_pe_trade is None  # flat exit, same as default-off test

    def test_load_config_accepts_zero_as_disable(self, user_id, monkeypatch):
        engine = self._engine(user_id, monkeypatch, ratchet_step=10)
        assert engine.ratchet_step_pts == Decimal("10")
        engine.load_config({"ratchet_step_points": 0})
        assert engine.ratchet_step_pts is None

    def test_db_backed_load_config_round_trip(self, user_id, monkeypatch):
        from app.core.destiny_engine import DestinyStrategyEngine
        from app.db.database import SessionLocal
        from app.models.models import StrategyConfig

        with SessionLocal() as db:
            cfg = db.query(StrategyConfig).filter(
                StrategyConfig.user_id == user_id, StrategyConfig.is_active == True
            ).first()
            cfg.ratchet_step_points = Decimal("25")
            db.commit()

        engine = DestinyStrategyEngine(user_id=user_id)
        engine._load_config()
        assert engine.ratchet_step_pts == Decimal("25")

    @pytest.mark.asyncio
    async def test_restart_restores_trade_unarmed(self, user_id, monkeypatch):
        """Documented tradeoff: in-flight ratchet state isn't persisted, so a mid-day
        restart restores an open trade unarmed (base target), even if it was already
        ratcheting before the restart. SL is unaffected."""
        engine = self._engine(user_id, monkeypatch, ratchet_step=10)
        await engine.on_nifty_tick(Decimal("24050.00"))
        await engine.on_nifty_tick(Decimal("24100.00"))
        assert engine.active_pe_trade is not None

        fresh = type(engine)(user_id=user_id)
        fresh.ratchet_step_pts = Decimal("10")
        fresh.target_pts = engine.target_pts
        fresh.sl_pts = engine.sl_pts
        fresh.lot_size = engine.lot_size
        fresh.load_existing_trades()
        assert fresh.active_pe_trade is not None
        assert fresh.active_pe_trade["locked_floor"] is None


# ── backtest replay ────────────────────────────────────────────────────────────

class TestDestinyBacktestRatchet:
    BASE_CFG = dict(r1=24100, s1=23900, target_points=30, sl_points=30, lot_size=75, squareoff_time="15:20")

    @staticmethod
    def opt(nifty, entry_nifty=24100, entry_price=100, side="PE"):
        diff = nifty - entry_nifty
        return entry_price - 0.5 * diff if side == "PE" else entry_price + 0.5 * diff

    def test_legacy_behavior_is_byte_identical_when_unset(self):
        """Regression guard: omitting ratchet_step_points must replay exactly as before."""
        prices = [24050, 24100, 24030]  # entry @24100 (opt=100), then opt=135 >= target(130)
        trades = run_destiny_single_backtest("2026-01-05", prices, self.BASE_CFG)
        assert len(trades) == 1
        assert trades[0]["exit_reason"] == "TARGET"
        assert trades[0]["exit_price"] == 130.0  # exact flat-target fill, unchanged
        assert trades[0]["locked_floor"] is None

    @pytest.mark.parametrize("ratchet_value", [None, 0, "", "0"])
    def test_falsy_ratchet_values_all_mean_off(self, ratchet_value):
        prices = [24050, 24100, 24030]
        trades = run_destiny_single_backtest(
            "2026-01-05", prices, {**self.BASE_CFG, "ratchet_step_points": ratchet_value}
        )
        assert trades[0]["exit_reason"] == "TARGET"
        assert trades[0]["exit_price"] == 130.0

    def test_arms_and_rides_further_than_flat_target(self):
        # entry @24100 (opt=100) -> 24010 (opt=145, arms at 130 then climbs within the same
        # bar to 140) -> 24036 (opt=132, exits below the climbed floor of 140, not the
        # original 130)
        prices = [24050, 24100, 24010, 24036]
        trades = run_destiny_single_backtest(
            "2026-01-05", prices, {**self.BASE_CFG, "ratchet_step_points": 10}
        )
        assert len(trades) == 1
        t = trades[0]
        assert t["exit_reason"] == "TARGET"
        assert t["locked_floor"] == 140.0
        assert t["exit_price"] == 132.0
        assert t["pnl"] > (130.0 - 100.0) * 75  # strictly more than the flat-exit would have banked

    def test_climbs_multiple_steps_within_a_single_bar(self):
        # One bar jumps straight from pre-arm to opt=180 (way past several 10pt milestones)
        prices = [24050, 24100, 23940]  # opt = 100 - 0.5*(23940-24100) = 180
        trades = run_destiny_single_backtest(
            "2026-01-05", prices, {**self.BASE_CFG, "ratchet_step_points": 10}
        )
        assert trades == []  # still open, not yet exited - inspect via a longer series instead

    def test_multi_step_climb_then_exit_reports_correct_floor(self):
        # opt=180 in one bar climbs the floor all the way to 180 (130 -> 140 -> ... -> 180,
        # the highest 10pt milestone at or below the observed price), then the next bar
        # drops to opt=73, well below that climbed floor -> exits
        prices = [24050, 24100, 23940, 24154]
        trades = run_destiny_single_backtest(
            "2026-01-05", prices, {**self.BASE_CFG, "ratchet_step_points": 10}
        )
        assert len(trades) == 1
        assert trades[0]["locked_floor"] == 180.0
        assert trades[0]["exit_reason"] == "TARGET"

    def test_sl_wins_over_an_armed_floor_in_backtest_too(self):
        prices = [24050, 24100, 24030, 24300]  # arm at opt=135, then crash to opt=0 (way below SL=70)
        trades = run_destiny_single_backtest(
            "2026-01-05", prices, {**self.BASE_CFG, "ratchet_step_points": 10}
        )
        assert len(trades) == 1
        assert trades[0]["exit_reason"] == "SL"

    def test_squareoff_reports_locked_floor_when_armed(self):
        # Entry at 09:16 (24100); 24030 @09:17 arms the floor at 130; the 09:19 bar forces
        # squareoff while still armed and unexited
        prices = [24050, 24100, 24030, 24030, 24030]
        trades = run_destiny_single_backtest(
            "2026-01-05", prices, {**self.BASE_CFG, "ratchet_step_points": 10, "squareoff_time": "09:19"}
        )
        assert len(trades) == 1
        assert trades[0]["exit_reason"] == "SQUAREOFF"
        assert trades[0]["locked_floor"] == 130.0

