"""Phase 3: per-instrument engines, manager keying, Kite feed routing, paper-only."""
import asyncio
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.core.engine_manager import EngineManager
from app.core.strategy_engine import StrategyEngine
from app.core.destiny_engine import DestinyStrategyEngine
from app.services.kite_service import KiteService


@pytest.fixture
def manager():
    m = EngineManager()
    with patch("app.core.engine_manager.SessionLocal") as sl, \
         patch("app.services.kite_service.get_user_kite_service") as gk:
        sl.return_value.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
        gk.return_value = MagicMock()
        m._kite = gk.return_value
        yield m


class TestEngineKeying:
    def test_nifty_default_unchanged(self, manager):
        e = manager.get_engine(1)
        assert e.underlying == "NIFTY"
        assert manager._engines[1] is e
        assert manager.get_engine(1, "NIFTY") is e

    def test_banknifty_is_separate_engine(self, manager):
        n, b = manager.get_engine(1), manager.get_engine(1, "BANKNIFTY")
        assert n is not b
        assert b.underlying == "BANKNIFTY"
        assert 1 in manager._engines and (1, "BANKNIFTY") in manager._instrument_engines
        assert manager.get_engine(1, "banknifty") is b
        assert set(map(id, manager.all_engines())) == {id(n), id(b)}

    def test_banknifty_registers_kite_feed(self, manager):
        b = manager.get_engine(7, "BANKNIFTY")
        manager._kite.register_instrument_feed.assert_called_once_with(
            "BANKNIFTY", b.on_nifty_tick, b.on_option_tick)

    def test_nifty_does_not_register_extra_feed(self, manager):
        manager.get_engine(1)
        manager._kite.register_instrument_feed.assert_not_called()

    def test_unknown_instrument_rejected(self, manager):
        with pytest.raises(ValueError):
            manager.get_engine(1, "FINNIFTY")

    def test_stop_all_covers_both(self, manager):
        n, b = manager.get_engine(1), manager.get_engine(1, "BANKNIFTY")
        n.is_running = b.is_running = True
        n.stop = MagicMock(); b.stop = MagicMock()
        manager.stop_all()
        n.stop.assert_called_once(); b.stop.assert_called_once()


class TestEngineBehaviour:
    def test_banknifty_engine_uses_its_instrument(self):
        e = StrategyEngine(user_id=1, underlying="BANKNIFTY")
        assert e.instrument.strike_step == 100
        assert e.order_manager.underlying == "BANKNIFTY"
        assert e.nifty_prev_close is None  # no NIFTY placeholder
        assert StrategyEngine(user_id=1).nifty_prev_close == Decimal("24175.70")

    def test_banknifty_forced_paper_even_if_config_says_live(self):
        e = StrategyEngine(user_id=1, underlying="BANKNIFTY")
        e.load_config({"r1": 1, "r2": 2, "r3": 3, "s1": 1, "s2": 2, "s3": 3, "paper_trade": False})
        assert e.mock_mode is True
        assert e.order_manager.paper_trade is True
        assert e.ce.lot_size == 30

    def test_nifty_live_mode_still_honoured(self):
        e = StrategyEngine(user_id=1)
        e.load_config({"r1": 1, "r2": 2, "r3": 3, "s1": 1, "s2": 2, "s3": 3, "paper_trade": False})
        assert e.mock_mode is False

    def test_destiny_engine_instrument(self):
        d = DestinyStrategyEngine(user_id=1, underlying="BANKNIFTY")
        assert d.instrument.name == "BANKNIFTY" and d.lot_size == 30
        assert d.order_manager.underlying == "BANKNIFTY"

    def test_spot_cache_keys_are_separate(self):
        assert StrategyEngine(1).instrument.ltp_cache_key == "nifty:ltp"
        assert StrategyEngine(1, "BANKNIFTY").instrument.ltp_cache_key == "banknifty:ltp"


class TestKiteFeedRouting:
    def test_register_rejects_nifty(self):
        with pytest.raises(ValueError):
            KiteService(user_id=1).register_instrument_feed("NIFTY", MagicMock(), MagicMock())

    def test_spot_token_lookup(self):
        ks = KiteService(user_id=1)
        spot_cb = MagicMock()
        ks.register_instrument_feed("BANKNIFTY", spot_cb, MagicMock())
        spec, cb = ks._feed_for_spot_token(260105)
        assert spec.name == "BANKNIFTY" and cb is spot_cb
        assert ks._feed_for_spot_token(256265) is None  # NIFTY stays on the default path

    def test_registered_feed_included_in_instrument_load(self):
        ks = KiteService(user_id=1)
        ks.register_instrument_feed("BANKNIFTY", MagicMock(), MagicMock())
        ks._kite = MagicMock()
        ks._access_token = "x"
        ks._kite.instruments.return_value = [
            {"name": "NIFTY", "segment": "NFO-OPT", "tradingsymbol": "NIFTY26O0623200CE", "instrument_token": 1},
            {"name": "BANKNIFTY", "segment": "NFO-OPT", "tradingsymbol": "BANKNIFTY26OCT55000CE", "instrument_token": 2},
            {"name": "FINNIFTY", "segment": "NFO-OPT", "tradingsymbol": "FINNIFTY26OCT25000CE", "instrument_token": 3},
        ]
        with patch.object(KiteService, "is_authenticated", return_value=True):
            ks.load_instruments()
        assert ks._symbol_to_token.keys() == {"NIFTY26O0623200CE", "BANKNIFTY26OCT55000CE"}
