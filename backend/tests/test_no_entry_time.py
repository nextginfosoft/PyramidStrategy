"""
Tests for the user-configurable "No Entry Time" setting.

Blank keeps the legacy cutoff (15 min before square-off, never after 14:30);
when set it becomes the entry cutoff, clamped so it can never exceed square-off.
"""

import pytest
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytz
from pydantic import ValidationError

from app.core.time_rules import is_entry_allowed, get_entry_cutoff_time
from app.schemas.schemas import StrategyConfigCreate

IST = pytz.timezone("Asia/Kolkata")


def ist(hour: int, minute: int) -> datetime:
    d = date(2024, 6, 13)  # a Thursday
    return IST.localize(datetime(d.year, d.month, d.day, hour, minute, 0))


def make_config(**overrides):
    payload = dict(
        r1=24100.0, s1=23900.0, r2=24200.0, r3=24300.0, s2=23800.0, s3=23700.0,
        squareoff_time="15:20", strategy_type="DESTINY",
    )
    payload.update(overrides)
    return StrategyConfigCreate(**payload)


# ── time_rules ────────────────────────────────────────────────────────────────

class TestNoEntryTimeRules:
    def test_entry_blocked_from_the_configured_minute(self):
        assert is_entry_allowed(ist(9, 59), "15:20", "10:00") is True
        assert is_entry_allowed(ist(10, 0), "15:20", "10:00") is False

    def test_explicit_time_overrides_legacy_1430_cap(self):
        # Legacy rule blocks everything from 14:30; an explicit later time wins.
        assert is_entry_allowed(ist(14, 45), "15:20") is False
        assert is_entry_allowed(ist(14, 45), "15:20", "15:00") is True
        assert is_entry_allowed(ist(15, 0), "15:20", "15:00") is False

    def test_explicit_time_is_clamped_to_squareoff(self):
        # No-entry after square-off is meaningless — square-off wins.
        assert is_entry_allowed(ist(14, 29), "14:30", "15:20") is True
        assert is_entry_allowed(ist(14, 30), "14:30", "15:20") is False

    @pytest.mark.parametrize("blank", [None, ""])
    def test_blank_keeps_legacy_behavior(self, blank):
        assert is_entry_allowed(ist(14, 29), "15:20", blank) is True
        assert is_entry_allowed(ist(14, 30), "15:20", blank) is False
        # 15 minutes before an early squareoff still applies
        assert is_entry_allowed(ist(11, 14), "11:30", blank) is True
        assert is_entry_allowed(ist(11, 15), "11:30", blank) is False

    def test_get_entry_cutoff_time(self):
        assert get_entry_cutoff_time("15:20") == time(15, 5)
        assert get_entry_cutoff_time("15:20", "14:45") == time(14, 45)
        assert get_entry_cutoff_time("14:30", "15:20") == time(14, 30)


# ── schema validation ─────────────────────────────────────────────────────────

class TestNoEntryTimeSchema:
    def test_defaults_to_none(self):
        assert make_config().no_entry_time is None

    @pytest.mark.parametrize("blank", [None, "", "   "])
    def test_blank_becomes_none(self, blank):
        assert make_config(no_entry_time=blank).no_entry_time is None

    def test_valid_time_is_kept_and_zero_padded(self):
        assert make_config(no_entry_time="14:45").no_entry_time == "14:45"
        assert make_config(no_entry_time="9:45").no_entry_time == "09:45"

    @pytest.mark.parametrize("bad", ["08:59", "15:31", "abc", "14:61", "25:00", "1445"])
    def test_invalid_times_rejected(self, bad):
        with pytest.raises(ValidationError):
            make_config(no_entry_time=bad)

    def test_must_not_be_after_squareoff(self):
        with pytest.raises(ValidationError):
            make_config(squareoff_time="14:30", no_entry_time="14:45")

    def test_equal_to_squareoff_is_allowed(self):
        assert make_config(squareoff_time="14:30", no_entry_time="14:30").no_entry_time == "14:30"

    def test_compares_numerically_not_lexicographically(self):
        # "9:45" > "10:00" as raw strings; must still be rejected as 10:00 > 09:45
        with pytest.raises(ValidationError):
            make_config(squareoff_time="9:45", no_entry_time="10:00")


# ── route round-trip (config rows are append-only, so every writer must carry it) ─

class TestNoEntryTimeRoute:
    @pytest.fixture
    def client(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.routes.config import router
        from app.api.routes.session import router as session_router, get_password_hash
        from app.db.database import SessionLocal, init_db
        from app.models.models import User

        init_db()
        with SessionLocal() as db:
            user = db.query(User).filter(User.username == "no_entry_user").first()
            if not user:
                user = User(username="no_entry_user", hashed_password=get_password_hash("pw12345!"), is_approved=True)
                db.add(user)
            else:
                user.hashed_password = get_password_hash("pw12345!")
                user.is_approved = True
            db.commit()

        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.include_router(session_router, prefix="/api")
        return TestClient(app)

    @pytest.fixture
    def headers(self, client):
        login = client.post("/api/session/login", json={"username": "no_entry_user", "password": "pw12345!"})
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

    def test_saved_value_is_returned_and_persisted(self, client, headers):
        resp = client.post("/api/config/strategy", json=self.body(no_entry_time="14:45"), headers=headers)
        assert resp.status_code == 200
        assert resp.json()["no_entry_time"] == "14:45"

        got = client.get("/api/config/strategy?strategy_type=DESTINY", headers=headers)
        assert got.status_code == 200
        assert got.json()["no_entry_time"] == "14:45"

    def test_blank_clears_it_back_to_default(self, client, headers):
        client.post("/api/config/strategy", json=self.body(no_entry_time="14:45"), headers=headers)
        resp = client.post("/api/config/strategy", json=self.body(no_entry_time=""), headers=headers)
        assert resp.status_code == 200
        assert resp.json()["no_entry_time"] is None

    def test_rejects_time_after_squareoff(self, client, headers):
        resp = client.post(
            "/api/config/strategy",
            json=self.body(squareoff_time="14:30", no_entry_time="14:45"),
            headers=headers,
        )
        assert resp.status_code == 422

    def test_engine_receives_the_setting_on_save(self, client, headers):
        from app.core.engine_manager import engine_manager
        from app.db.database import SessionLocal
        from app.models.models import User

        client.post("/api/config/strategy", json=self.body(no_entry_time="13:15"), headers=headers)
        with SessionLocal() as db:
            uid = db.query(User).filter(User.username == "no_entry_user").first().id
        assert engine_manager.get_engine(uid).no_entry_time_str == "13:15"


# ── engine gating ─────────────────────────────────────────────────────────────

class TestDestinyEngineNoEntryTime:
    @pytest.fixture(autouse=True)
    def setup_database(self):
        from app.db.database import init_db
        init_db()

    @pytest.fixture
    def user_id(self):
        from app.db.database import SessionLocal
        from app.models.models import StrategyConfig, Trade, User

        with SessionLocal() as db:
            user = db.query(User).filter(User.username == "destiny_no_entry_user").first()
            if not user:
                user = User(username="destiny_no_entry_user", hashed_password="hashed_pw", is_approved=True)
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

    @pytest.mark.asyncio
    async def test_entry_blocked_at_or_after_no_entry_time(self, user_id, monkeypatch):
        from app.core.destiny_engine import DestinyStrategyEngine

        monkeypatch.setenv("MOCK_TIME", "10:30")
        engine = DestinyStrategyEngine(user_id=user_id)
        engine.start()
        engine.load_config({"no_entry_time": "10:00"})

        await engine.on_nifty_tick(Decimal("24050.00"))
        await engine.on_nifty_tick(Decimal("24100.00"))  # crosses R, but past the cutoff
        assert engine.active_pe_trade is None
        assert engine.r_level_completed is False

    @pytest.mark.asyncio
    async def test_entry_allowed_before_no_entry_time(self, user_id, monkeypatch):
        from app.core.destiny_engine import DestinyStrategyEngine

        monkeypatch.setenv("MOCK_TIME", "09:45")
        engine = DestinyStrategyEngine(user_id=user_id)
        engine.start()
        engine.load_config({"no_entry_time": "10:00"})

        await engine.on_nifty_tick(Decimal("24050.00"))
        await engine.on_nifty_tick(Decimal("24100.00"))
        assert engine.active_pe_trade is not None

    @pytest.mark.asyncio
    async def test_open_position_still_exits_after_cutoff(self, user_id, monkeypatch):
        """The cutoff only stops fresh entries — an open trade must still manage its exit."""
        from app.core.destiny_engine import DestinyStrategyEngine

        monkeypatch.setenv("MOCK_TIME", "09:45")
        engine = DestinyStrategyEngine(user_id=user_id)
        engine.start()
        engine.load_config({"no_entry_time": "10:00"})
        await engine.on_nifty_tick(Decimal("24050.00"))
        await engine.on_nifty_tick(Decimal("24100.00"))
        assert engine.active_pe_trade is not None

        monkeypatch.setenv("MOCK_TIME", "10:30")  # now past the no-entry time
        await engine.on_nifty_tick(Decimal("23950.00"))  # NIFTY falls -> PE hits target
        assert engine.active_pe_trade is None

    @pytest.mark.asyncio
    async def test_clearing_it_restores_default_behavior(self, user_id, monkeypatch):
        from app.core.destiny_engine import DestinyStrategyEngine

        monkeypatch.setenv("MOCK_TIME", "10:30")
        engine = DestinyStrategyEngine(user_id=user_id)
        engine.start()
        engine.load_config({"no_entry_time": "10:00"})
        engine.load_config({"no_entry_time": None})
        assert engine.no_entry_time_str is None

        await engine.on_nifty_tick(Decimal("24050.00"))
        await engine.on_nifty_tick(Decimal("24100.00"))
        assert engine.active_pe_trade is not None
