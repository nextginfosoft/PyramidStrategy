"""
Phase 3 Tests — AI Observer, Telegram Notifications, JWT Auth
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal


# ── AI Service Tests ──────────────────────────────────────────────────────────

class TestAIService:
    def setup_method(self):
        from app.services.ai_service import AIService
        self.ai = AIService()

    def test_initial_state(self):
        assert self.ai.is_enabled() is False
        assert self.ai._provider == "openai"
        assert self.ai._api_key is None

    def test_configure(self):
        self.ai.configure("anthropic", "sk-test-key", enabled=True)
        assert self.ai._provider == "anthropic"
        assert self.ai._api_key == "sk-test-key"
        assert self.ai.is_enabled() is True

    def test_configure_disabled(self):
        self.ai.configure("openai", "sk-key", enabled=False)
        assert self.ai.is_enabled() is False

    def test_no_key_means_disabled(self):
        self.ai._enabled = True
        self.ai._api_key = None
        assert self.ai.is_enabled() is False

    def test_build_prompt_contains_event(self):
        prompt = self.ai._build_prompt("ENTRY", "CE", "L1", 24000.0, {"lots": 1})
        assert "ENTRY" in prompt
        assert "CE" in prompt
        assert "L1" in prompt
        assert "24000" in prompt
        assert "Lots: 1" in prompt

    def test_build_prompt_with_pnl(self):
        prompt = self.ai._build_prompt("EXIT", "PE", "TARGET", 23800.0, {
            "pnl": 1500, "avg_price": 95.0, "reason": "TARGET"
        })
        assert "P&L" in prompt
        assert "TARGET" in prompt

    @pytest.mark.asyncio
    async def test_analyze_returns_none_when_disabled(self):
        result = await self.ai.analyze("ENTRY", "CE", "L1", 24000.0)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_calls_openai(self):
        self.ai.configure("openai", "sk-test", enabled=True)
        with patch.object(self.ai, "_call_openai", new=AsyncMock(return_value="Good entry signal")) as mock_call:
            with patch.object(self.ai, "_store_suggestion", new=AsyncMock()):
                result = await self.ai.analyze("ENTRY", "CE", "L1", 24000.0)
        assert result == "Good entry signal"
        mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_calls_anthropic(self):
        self.ai.configure("anthropic", "sk-test", enabled=True)
        with patch.object(self.ai, "_call_anthropic", new=AsyncMock(return_value="Market looks volatile")) as mock_call:
            with patch.object(self.ai, "_store_suggestion", new=AsyncMock()):
                result = await self.ai.analyze("ENTRY", "PE", "L2", 23900.0)
        assert result == "Market looks volatile"
        mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_calls_gemini(self):
        self.ai.configure("gemini", "AIza-key", enabled=True)
        with patch.object(self.ai, "_call_gemini", new=AsyncMock(return_value="Consider IV crush")) as mock_call:
            with patch.object(self.ai, "_store_suggestion", new=AsyncMock()):
                result = await self.ai.analyze("EXIT", "PE", "TARGET", 23800.0)
        assert result == "Consider IV crush"

    @pytest.mark.asyncio
    async def test_analyze_handles_exception(self):
        self.ai.configure("openai", "sk-test", enabled=True)
        with patch.object(self.ai, "_call_openai", new=AsyncMock(side_effect=Exception("API error"))):
            result = await self.ai.analyze("ENTRY", "CE", "L1", 24000.0)
        assert result is None  # Never raises

    @pytest.mark.asyncio
    async def test_test_connection_when_disabled(self):
        success, msg = await self.ai.test_connection()
        assert success is False
        assert "No API key" in msg

    @pytest.mark.asyncio
    async def test_test_connection_when_enabled(self):
        self.ai.configure("openai", "sk-key", enabled=True)
        with patch.object(self.ai, "analyze", new=AsyncMock(return_value="test response")):
            success, msg = await self.ai.test_connection()
        assert success is True
        assert "OK" in msg


# ── Notification Service Tests ────────────────────────────────────────────────

class TestNotificationService:
    def setup_method(self):
        from app.services.notification import NotificationService
        self.ns = NotificationService()

    def test_initial_state(self):
        assert self.ns.is_enabled() is False
        assert self.ns._bot_token is None
        assert self.ns._chat_id is None

    def test_configure(self):
        self.ns.configure("123456:BOT-TOKEN", "987654321")
        assert self.ns.is_enabled() is True
        assert self.ns._bot_token == "123456:BOT-TOKEN"
        assert self.ns._chat_id == "987654321"

    def test_configure_empty_token_disables(self):
        self.ns.configure("", "987654321")
        assert self.ns.is_enabled() is False

    def test_configure_empty_chat_id_disables(self):
        self.ns.configure("token", "")
        assert self.ns.is_enabled() is False

    def test_notify_entry_when_disabled_is_noop(self):
        # Should not raise
        self.ns.notify_trade_entry("CE", "L1", "NIFTY123PE", 1, Decimal("95"), Decimal("24000"))

    def test_notify_entry_message_format(self):
        self.ns.configure("token", "chatid")
        sent_msgs = []

        async def fake_send(msg):
            sent_msgs.append(msg)

        with patch.object(self.ns, "_send", side_effect=fake_send):
            import asyncio
            with patch("asyncio.create_task") as mock_ct:
                self.ns.notify_trade_entry("CE", "L1", "NIFTY27JUN2423150CE", 1,
                                           Decimal("95.50"), Decimal("24000"))
                assert mock_ct.called  # create_task was called

    def test_notify_target_hit_message(self):
        self.ns.configure("token", "chatid")
        with patch("asyncio.create_task") as mock_ct:
            self.ns.notify_target_hit("CE", "NIFTY123CE", 2, Decimal("115"), Decimal("95"), Decimal("3000"))
            assert mock_ct.called

    def test_notify_sl_hit_message(self):
        self.ns.configure("token", "chatid")
        with patch("asyncio.create_task") as mock_ct:
            self.ns.notify_sl_hit("PE", "NIFTY123PE", 3, Decimal("85"), Decimal("95"), Decimal("-2250"))
            assert mock_ct.called

    def test_notify_squareoff(self):
        self.ns.configure("token", "chatid")
        with patch("asyncio.create_task") as mock_ct:
            self.ns.notify_squareoff(Decimal("1500"), Decimal("-750"))
            assert mock_ct.called

    def test_notify_engine_started_paper(self):
        self.ns.configure("token", "chatid")
        with patch("asyncio.create_task") as mock_ct:
            self.ns.notify_engine_started(paper_trade=True)
            assert mock_ct.called

    def test_notify_engine_started_live(self):
        self.ns.configure("token", "chatid")
        with patch("asyncio.create_task") as mock_ct:
            self.ns.notify_engine_started(paper_trade=False)
            assert mock_ct.called

    def test_now_str_format(self):
        ts = self.ns._now_str()
        assert "AM" in ts or "PM" in ts
        assert "IST" in ts

    @pytest.mark.asyncio
    async def test_test_connection_when_disabled(self):
        success, msg = await self.ns.test_connection()
        assert success is False
        assert "not configured" in msg.lower()

    @pytest.mark.asyncio
    async def test_send_error_does_not_raise(self):
        self.ns.configure("bad-token", "chatid")
        # Should not raise even if HTTP call fails
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Network error")
            )
            await self.ns._send("test message")  # must not raise


# ── JWT Session Auth Tests ────────────────────────────────────────────────────

class TestSessionAuth:
    def test_create_and_verify_token(self):
        from app.api.routes.session import create_token, verify_token
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_token("admin")
        assert token  # non-empty

        # Wrap in credentials object
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        username = verify_token(creds)
        assert username == "admin"

    def test_invalid_token_returns_none(self):
        from app.api.routes.session import verify_token
        from fastapi.security import HTTPAuthorizationCredentials

        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.token.here")
        result = verify_token(creds)
        assert result is None

    def test_no_credentials_returns_none(self):
        from app.api.routes.session import verify_token
        result = verify_token(None)
        assert result is None

    def test_require_auth_raises_401(self):
        from app.api.routes.session import require_auth
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            require_auth(None)
        assert exc_info.value.status_code == 401


# ── API Route Integration Tests ───────────────────────────────────────────────

class TestAIRoutes:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from app.api.routes.ai import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_get_status(self, client):
        resp = client.get("/ai/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "enabled" in data
        assert "provider" in data

    def test_reload_endpoint(self, client):
        with patch("app.services.ai_service.ai_service.load_from_db"):
            resp = client.post("/ai/reload")
        assert resp.status_code == 200
        assert resp.json()["status"] == "reloaded"

    def test_get_suggestions_returns_list(self, client):
        with patch("app.services.ai_service.ai_service.get_today_suggestions", return_value=[]):
            resp = client.get("/ai/suggestions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestSessionRoutes:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from app.api.routes.session import router

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_login_success(self, client):
        resp = client.post("/session/login", json={"username": "admin", "password": "pyramid123"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client):
        resp = client.post("/session/login", json={"username": "admin", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_wrong_username(self, client):
        resp = client.post("/session/login", json={"username": "hacker", "password": "pyramid123"})
        assert resp.status_code == 401

    def test_logout(self, client):
        resp = client.post("/session/logout")
        assert resp.status_code == 200

    def test_check_without_token(self, client):
        resp = client.get("/session/check")
        assert resp.status_code == 200
        assert resp.json()["authenticated"] is False

    def test_check_with_valid_token(self, client):
        # Login first
        login = client.post("/session/login", json={"username": "admin", "password": "pyramid123"})
        token = login.json()["access_token"]

        resp = client.get("/session/check", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["authenticated"] is True
        assert resp.json()["username"] == "admin"

    def test_me_requires_auth(self, client):
        resp = client.get("/session/me")
        assert resp.status_code == 401

    def test_me_with_valid_token(self, client):
        login = client.post("/session/login", json={"username": "admin", "password": "pyramid123"})
        token = login.json()["access_token"]

        resp = client.get("/session/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["username"] == "admin"
        assert resp.json()["authenticated"] is True
