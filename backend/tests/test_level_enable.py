"""
Tests for the per-side "Enable Level" setting (Destiny only).

Opt-out: NULL/True keeps today's behavior unchanged (both Resistance and Support
active). Only an explicit False on r_level_enabled/s_level_enabled stops that side
from ever triggering an entry, letting a user run with just one level configured.
At least one side must stay enabled - both False is rejected.
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

class TestLevelEnableSchema:
    def test_defaults_to_none_meaning_enabled(self):
        cfg = make_config()
        assert cfg.r_level_enabled is None
        assert cfg.s_level_enabled is None

    def test_one_side_disabled_is_accepted(self):
        cfg = make_config(r_level_enabled=False)
        assert cfg.r_level_enabled is False
        assert cfg.s_level_enabled is None

    def test_both_disabled_is_rejected_for_destiny(self):
        with pytest.raises(ValidationError, match="At least one"):
            make_config(r_level_enabled=False, s_level_enabled=False)

    def test_both_disabled_is_allowed_for_pyramid(self):
        """The guard is Destiny-only; Pyramid doesn't use these fields at all."""
        cfg = make_config(strategy_type="PYRAMID", r_level_enabled=False, s_level_enabled=False)
        assert cfg.r_level_enabled is False
        assert cfg.s_level_enabled is False

    def test_explicit_true_is_kept(self):
        cfg = make_config(r_level_enabled=True, s_level_enabled=False)
        assert cfg.r_level_enabled is True
        assert cfg.s_level_enabled is False


# ── route round-trip (config rows are append-only, so every writer must carry it) ─

class TestLevelEnableRoute:
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
            for username, is_admin in (("level_user", False), ("level_admin", True)):
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
        headers = self._headers(client, "level_user")
        resp = client.post("/api/config/strategy", json=self.body(r_level_enabled=False), headers=headers)
        assert resp.status_code == 200
        assert resp.json()["r_level_enabled"] is False
        assert resp.json()["s_level_enabled"] is None

        got = client.get("/api/config/strategy?strategy_type=DESTINY", headers=headers)
        assert got.json()["r_level_enabled"] is False

    def test_both_disabled_is_rejected_by_the_route(self, client):
        headers = self._headers(client, "level_user")
        resp = client.post(
            "/api/config/strategy",
            json=self.body(r_level_enabled=False, s_level_enabled=False),
            headers=headers,
        )
        assert resp.status_code == 422

    def test_admin_sync_levels_preserves_each_users_disabled_side(self, client):
        user_headers = self._headers(client, "level_user")
        admin_headers = self._headers(client, "level_admin")

        client.post("/api/config/strategy", json=self.body(r_level_enabled=False), headers=user_headers)

        resp = client.post(
            "/api/admin/strategy/sync-levels",
            json={"r1": 24150.0, "r2": 24250.0, "r3": 24350.0,
                  "s1": 23950.0, "s2": 23850.0, "s3": 23750.0,
                  "strategy_type": "DESTINY"},
            headers=admin_headers,
        )
        assert resp.status_code == 200

        got = client.get("/api/config/strategy?strategy_type=DESTINY", headers=user_headers)
        body = got.json()
        assert body["r_level_enabled"] is False  # the user's own disable survives the sync
        assert body["s_level_enabled"] is None
        assert body["r1"] == 24150.0  # the sync itself did apply the new levels


# ── engine gating ─────────────────────────────────────────────────────────────

class TestDestinyEngineLevelEnable:
    @pytest.fixture(autouse=True)
    def setup_database(self):
        from app.db.database import init_db
        init_db()

    @pytest.fixture
    def user_id(self):
        from app.db.database import SessionLocal
        from app.models.models import StrategyConfig, Trade, User

        with SessionLocal() as db:
            user = db.query(User).filter(User.username == "destiny_level_user").first()
            if not user:
                user = User(username="destiny_level_user", hashed_password="hashed_pw", is_approved=True)
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
    def _engine(user_id, monkeypatch, mock_time="10:00", **config_overrides):
        from app.core.destiny_engine import DestinyStrategyEngine
        monkeypatch.setenv("MOCK_TIME", mock_time)
        engine = DestinyStrategyEngine(user_id=user_id)
        engine.start()
        if config_overrides:
            engine.load_config(config_overrides)
        engine._broadcast = AsyncMock()
        return engine

    @pytest.mark.asyncio
    async def test_default_both_sides_enabled_matches_today(self, user_id, monkeypatch):
        engine = self._engine(user_id, monkeypatch)
        assert engine.r_level_enabled is True
        assert engine.s_level_enabled is True

        await engine.on_nifty_tick(Decimal("24050.00"))
        await engine.on_nifty_tick(Decimal("24100.00"))  # crosses R -> PE entry
        assert engine.active_pe_trade is not None

    @pytest.mark.asyncio
    async def test_disabled_resistance_never_enters_pe(self, user_id, monkeypatch):
        engine = self._engine(user_id, monkeypatch, r_level_enabled=False)
        assert engine.r_level_enabled is False

        await engine.on_nifty_tick(Decimal("24050.00"))
        await engine.on_nifty_tick(Decimal("24100.00"))  # would cross R, but R is disabled
        assert engine.active_pe_trade is None
        assert engine.r_level_completed is False

    @pytest.mark.asyncio
    async def test_disabled_support_never_enters_ce_but_resistance_still_works(self, user_id, monkeypatch):
        engine = self._engine(user_id, monkeypatch, s_level_enabled=False)
        assert engine.s_level_enabled is False

        await engine.on_nifty_tick(Decimal("23950.00"))
        await engine.on_nifty_tick(Decimal("23900.00"))  # would cross S, but S is disabled
        assert engine.active_ce_trade is None

        # The other side is untouched by disabling this one.
        await engine.on_nifty_tick(Decimal("24050.00"))
        await engine.on_nifty_tick(Decimal("24100.00"))
        assert engine.active_pe_trade is not None

    def test_load_config_accepts_only_explicit_false_as_disable(self, user_id, monkeypatch):
        from app.core.destiny_engine import DestinyStrategyEngine
        engine = DestinyStrategyEngine(user_id=user_id)

        engine.load_config({"r_level_enabled": None})
        assert engine.r_level_enabled is True
        engine.load_config({"r_level_enabled": True})
        assert engine.r_level_enabled is True
        engine.load_config({"r_level_enabled": False})
        assert engine.r_level_enabled is False


# ── backtest gating ───────────────────────────────────────────────────────────

class TestDestinyBacktestLevelEnable:
    BASE_CFG = dict(r1=24100, s1=23900, target_points=30, sl_points=30, lot_size=75, squareoff_time="15:20")

    def test_default_both_sides_enabled(self):
        prices = [24050, 24100, 24030]  # entry @24100 (opt=100), then opt=135 >= target(130)
        trades = run_destiny_single_backtest("2026-01-05", prices, self.BASE_CFG)
        assert len(trades) == 1
        assert trades[0]["side"] == "PE"

    def test_disabled_resistance_skips_pe_entry(self):
        prices = [24050, 24100, 24030]
        trades = run_destiny_single_backtest(
            "2026-01-05", prices, {**self.BASE_CFG, "r_level_enabled": False}
        )
        assert trades == []

    def test_disabled_support_skips_ce_but_not_pe(self):
        prices = [23950, 23900, 23970]  # would cross S at idx1
        trades = run_destiny_single_backtest(
            "2026-01-05", prices, {**self.BASE_CFG, "s_level_enabled": False}
        )
        assert trades == []

        prices_pe = [24050, 24100, 24030]
        trades_pe = run_destiny_single_backtest(
            "2026-01-05", prices_pe, {**self.BASE_CFG, "s_level_enabled": False}
        )
        assert len(trades_pe) == 1
        assert trades_pe[0]["side"] == "PE"
