"""
Phase 2 Tests — KiteService
Tests cover: configuration, token management, instrument cache,
option subscription, LTP retrieval, and ticker lifecycle.
All Kite SDK calls are mocked — no real API connection required.
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def kite_svc():
    """Fresh KiteService instance per test (not the global singleton)."""
    from app.services.kite_service import KiteService
    return KiteService()


@pytest.fixture
def configured_svc():
    """KiteService with mocked KiteConnect configured."""
    from app.services.kite_service import KiteService
    svc = KiteService()
    mock_kite = MagicMock()
    mock_kite.login_url.return_value = "https://kite.zerodha.com/connect/login?api_key=testkey"
    svc._kite = mock_kite
    svc._api_key = "testkey123"
    svc._api_secret = "testsecret123"
    return svc


@pytest.fixture
def authenticated_svc(configured_svc):
    """KiteService with access token set."""
    configured_svc._access_token = "test_access_token_abc"
    configured_svc._kite.set_access_token = MagicMock()
    return configured_svc


# ── Configuration Tests ───────────────────────────────────────────────────────

class TestConfiguration:
    def test_initial_state_unauthenticated(self, kite_svc):
        assert kite_svc.is_authenticated() is False
        assert kite_svc._api_key is None
        assert kite_svc._access_token is None

    def test_configure_sets_credentials(self, kite_svc):
        mock_kc_module = MagicMock()
        mock_kc_module.KiteConnect.return_value = MagicMock()
        with patch.dict("sys.modules", {"kiteconnect": mock_kc_module}):
            kite_svc.configure("myapikey", "myapisecret")
        assert kite_svc._api_key == "myapikey"
        assert kite_svc._api_secret == "myapisecret"
        assert kite_svc._kite is not None

    def test_not_authenticated_without_token(self, configured_svc):
        assert configured_svc.is_authenticated() is False

    def test_authenticated_with_token(self, authenticated_svc):
        assert authenticated_svc.is_authenticated() is True

    def test_get_login_url(self, configured_svc):
        url = configured_svc.get_login_url()
        assert "kite.zerodha.com" in url
        assert "api_key" in url

    def test_get_login_url_fails_without_configure(self, kite_svc):
        with pytest.raises(RuntimeError, match="not configured"):
            kite_svc.get_login_url()


# ── Token Exchange Tests ──────────────────────────────────────────────────────

class TestTokenManagement:
    def test_exchange_token_success(self, configured_svc):
        configured_svc._kite.generate_session.return_value = {
            "access_token": "live_access_token_xyz"
        }
        token = configured_svc.exchange_token("request_token_abc")
        assert token == "live_access_token_xyz"
        assert configured_svc._access_token == "live_access_token_xyz"
        configured_svc._kite.set_access_token.assert_called_once_with("live_access_token_xyz")

    def test_exchange_token_fails_without_config(self, kite_svc):
        with pytest.raises(RuntimeError, match="not configured"):
            kite_svc.exchange_token("some_token")

    def test_set_access_token_restores_auth(self, configured_svc):
        configured_svc.set_access_token("restored_token")
        assert configured_svc._access_token == "restored_token"
        assert configured_svc.is_authenticated() is True

    def test_validate_token_success(self, authenticated_svc):
        authenticated_svc._kite.profile.return_value = {"user_id": "ZY1234"}
        assert authenticated_svc.validate_token() is True

    def test_validate_token_expired(self, authenticated_svc):
        authenticated_svc._kite.profile.side_effect = Exception("Token expired")
        result = authenticated_svc.validate_token()
        assert result is False
        # Access token should be cleared after failed validation
        assert authenticated_svc._access_token is None

    def test_validate_token_unauthenticated(self, kite_svc):
        assert kite_svc.validate_token() is False

    def test_clear_credentials(self, authenticated_svc):
        authenticated_svc.clear_credentials()
        assert authenticated_svc._access_token is None

    def test_exchange_token_without_secret_raises(self, kite_svc):
        # _kite set but _api_secret still None — should raise
        kite_svc._kite = MagicMock()
        with pytest.raises(RuntimeError):
            kite_svc.exchange_token("some_token")


# ── Instrument Cache Tests ────────────────────────────────────────────────────

class TestInstrumentCache:
    def test_load_instruments_filters_nifty_options(self, authenticated_svc):
        fake_instruments = [
            {"name": "NIFTY", "segment": "NFO-OPT", "tradingsymbol": "NIFTY27JUN2423150PE", "instrument_token": 12345},
            {"name": "NIFTY", "segment": "NFO-OPT", "tradingsymbol": "NIFTY27JUN2423200CE", "instrument_token": 12346},
            {"name": "BANKNIFTY", "segment": "NFO-OPT", "tradingsymbol": "BANKNIFTY27JUN2448000PE", "instrument_token": 99999},
            {"name": "NIFTY", "segment": "NFO-FUT", "tradingsymbol": "NIFTYJUL24FUT", "instrument_token": 11111},
        ]
        authenticated_svc._kite.instruments.return_value = fake_instruments

        with patch("app.services.kite_service.get_redis_client") as mock_redis:
            mock_redis.return_value = MagicMock()
            authenticated_svc.load_instruments()

        assert "NIFTY27JUN2423150PE" in authenticated_svc._symbol_to_token
        assert "NIFTY27JUN2423200CE" in authenticated_svc._symbol_to_token
        # BANKNIFTY and FUT should NOT be cached
        assert "BANKNIFTY27JUN2448000PE" not in authenticated_svc._symbol_to_token
        assert "NIFTYJUL24FUT" not in authenticated_svc._symbol_to_token
        assert authenticated_svc._instruments_loaded is True

    def test_get_instrument_token_from_memory(self, authenticated_svc):
        authenticated_svc._symbol_to_token["NIFTY27JUN2423150PE"] = 12345
        token = authenticated_svc.get_instrument_token("NIFTY27JUN2423150PE")
        assert token == 12345

    def test_get_instrument_token_from_redis(self, authenticated_svc):
        with patch("app.services.kite_service.get_redis_client") as mock_redis:
            mock_redis.return_value.get.return_value = b"12345"
            token = authenticated_svc.get_instrument_token("NIFTY27JUN2423150PE")
        assert token == 12345

    def test_get_instrument_token_not_found(self, authenticated_svc):
        with patch("app.services.kite_service.get_redis_client") as mock_redis:
            mock_redis.return_value.get.return_value = None
            token = authenticated_svc.get_instrument_token("NOTEXIST27JUN2400000PE")
        assert token is None

    def test_load_instruments_without_auth(self, kite_svc):
        """Should skip without error when not authenticated."""
        kite_svc.load_instruments()  # should not raise
        assert kite_svc._instruments_loaded is False


# ── Option Subscription Tests ────────────────────────────────────────────────

class TestOptionSubscription:
    def test_subscribe_option_queues_when_not_connected(self, authenticated_svc):
        authenticated_svc._symbol_to_token["NIFTY27JUN2423150PE"] = 12345
        authenticated_svc._token_to_symbol[12345] = "NIFTY27JUN2423150PE"
        authenticated_svc._is_connected = False  # not yet connected

        authenticated_svc.subscribe_option("NIFTY27JUN2423150PE")

        assert 12345 in authenticated_svc._subscribed_option_tokens

    def test_subscribe_option_calls_ticker_when_connected(self, authenticated_svc):
        authenticated_svc._symbol_to_token["NIFTY27JUN2423150PE"] = 12345
        authenticated_svc._token_to_symbol[12345] = "NIFTY27JUN2423150PE"
        authenticated_svc._is_connected = True
        mock_ticker = MagicMock()
        authenticated_svc._ticker = mock_ticker

        authenticated_svc.subscribe_option("NIFTY27JUN2423150PE")

        mock_ticker.subscribe.assert_called_once_with([12345])

    def test_unsubscribe_option(self, authenticated_svc):
        authenticated_svc._symbol_to_token["NIFTY27JUN2423150PE"] = 12345
        authenticated_svc._token_to_symbol[12345] = "NIFTY27JUN2423150PE"
        authenticated_svc._subscribed_option_tokens.add(12345)
        authenticated_svc._is_connected = True
        mock_ticker = MagicMock()
        authenticated_svc._ticker = mock_ticker

        authenticated_svc.unsubscribe_option("NIFTY27JUN2423150PE")

        assert 12345 not in authenticated_svc._subscribed_option_tokens
        mock_ticker.unsubscribe.assert_called_once_with([12345])

    def test_subscribe_option_skipped_if_token_not_found(self, authenticated_svc):
        """Should not crash if instrument token is unknown."""
        with patch("app.services.kite_service.get_redis_client") as mock_redis:
            mock_redis.return_value.get.return_value = None
            authenticated_svc.subscribe_option("UNKNOWNSYMBOL")
        assert len(authenticated_svc._subscribed_option_tokens) == 0


# ── LTP Retrieval Tests ──────────────────────────────────────────────────────

class TestLTPRetrieval:
    def test_get_option_ltp_from_redis(self, authenticated_svc):
        with patch("app.services.kite_service.get_redis_client") as mock_redis:
            mock_redis.return_value.get.return_value = b"125.50"
            ltp = authenticated_svc.get_option_ltp("NIFTY27JUN2423150PE")
        assert ltp == Decimal("125.50")

    def test_get_ltp_rest_success(self, authenticated_svc):
        authenticated_svc._kite.ltp.return_value = {
            "NFO:NIFTY27JUN2423150PE": {"last_price": 130.75}
        }
        ltp = authenticated_svc.get_ltp_rest("NIFTY27JUN2423150PE")
        assert ltp == Decimal("130.75")

    def test_get_ltp_rest_fails_gracefully(self, authenticated_svc):
        authenticated_svc._kite.ltp.side_effect = Exception("Network error")
        ltp = authenticated_svc.get_ltp_rest("NIFTY27JUN2423150PE")
        assert ltp is None

    def test_get_ltp_rest_without_auth(self, kite_svc):
        ltp = kite_svc.get_ltp_rest("NIFTY27JUN2423150PE")
        assert ltp is None

    def test_get_ltp_rest_throttled(self, authenticated_svc):
        authenticated_svc._kite.ltp.return_value = {
            "NFO:NIFTY27JUN2423150PE": {"last_price": 130.75}
        }

        # First call should hit the API
        ltp1 = authenticated_svc.get_ltp_rest("NIFTY27JUN2423150PE")
        assert ltp1 == Decimal("130.75")
        assert authenticated_svc._kite.ltp.call_count == 1

        # Second call immediately after should return cached value without hitting the API
        ltp2 = authenticated_svc.get_ltp_rest("NIFTY27JUN2423150PE")
        assert ltp2 == Decimal("130.75")
        assert authenticated_svc._kite.ltp.call_count == 1  # call_count remains 1

        # Mock time forward by 3 seconds
        import time
        current_time = time.time()
        with patch("time.time", return_value=current_time + 3.0):
            ltp3 = authenticated_svc.get_ltp_rest("NIFTY27JUN2423150PE")
            assert ltp3 == Decimal("130.75")
            assert authenticated_svc._kite.ltp.call_count == 2  # increments to 2


# ── Status Tests ─────────────────────────────────────────────────────────────

class TestStatus:
    def test_status_unauthenticated(self, kite_svc):
        status = kite_svc.get_status()
        assert status["authenticated"] is False
        assert status["ticker_connected"] is False
        assert status["api_key_masked"] is None

    def test_status_authenticated(self, authenticated_svc):
        status = authenticated_svc.get_status()
        assert status["authenticated"] is True
        # api_key should be masked (not full key)
        assert status["api_key_masked"] is not None
        assert "testkey123" not in status.get("api_key_masked", "")

    def test_stop_ticker_when_not_running(self, kite_svc):
        """Should not raise even when ticker was never started."""
        kite_svc.stop_ticker()  # no exception
        assert kite_svc._ticker_running is False
