"""
Phase 4 Tests — Live Order Execution, Safety Checks, Production Hardening
"""

import pytest
import time
from decimal import Decimal
from unittest.mock import MagicMock, patch


# ── OrderManager Tests ────────────────────────────────────────────────────────

class TestOrderManagerPaperTrade:
    """Test OrderManager in paper trade mode."""

    @pytest.fixture
    def db(self):
        """In-memory SQLite DB for testing."""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models.models import Base
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        yield db
        db.close()

    @pytest.fixture
    def om(self):
        from app.core.order_manager import OrderManager
        with patch("app.core.order_manager.settings") as s:
            s.PAPER_TRADE = True
            om = OrderManager(kite_service=None)
            om.paper_trade = True
        return om

    def test_paper_buy_order(self, om, db):
        from datetime import date
        result = om.place_buy_order(
            db=db,
            side="CE",
            level="L1",
            instrument="NIFTY27JUN2423150CE",
            strike=23150,
            expiry=date.today(),
            lots=1,
            lot_size=75,
            trigger_nifty=Decimal("23100"),
            mock_ltp=Decimal("95.50"),
        )
        assert result["order_id"].startswith("PAPER-CE-L1")
        assert result["fill_price"] == Decimal("95.50")
        assert result["qty"] == 75
        assert result["status"] == "COMPLETE"

    def test_paper_exit_order(self, om, db):
        from datetime import date, datetime
        from app.models.models import Trade

        # First place a buy
        buy = om.place_buy_order(
            db=db, side="CE", level="L1",
            instrument="NIFTY27JUN2423150CE", strike=23150,
            expiry=date.today(), lots=1, lot_size=75,
            trigger_nifty=Decimal("23100"), mock_ltp=Decimal("95"),
        )

        result = om.place_exit_order(
            db=db,
            side="CE",
            instrument="NIFTY27JUN2423150CE",
            strike=23150,
            qty=75,
            reason="TARGET",
            entry_avg_price=Decimal("95"),
            mock_ltp=Decimal("115"),
            lot_size=75,
        )
        assert result["order_id"].startswith("PAPER-EXIT-CE")
        assert result["exit_price"] == Decimal("115")
        assert result["pnl_points"] == Decimal("20")  # 115 - 95
        assert result["pnl_rupees"] == Decimal("1500")  # 20 * 75

    def test_paper_exit_sl(self, om, db):
        from datetime import date
        om.place_buy_order(
            db=db, side="PE", level="L3",
            instrument="NIFTY27JUN2423150PE", strike=23150,
            expiry=date.today(), lots=3, lot_size=75,
            trigger_nifty=Decimal("23300"), mock_ltp=Decimal("95"),
        )
        result = om.place_exit_order(
            db=db, side="PE", instrument="NIFTY27JUN2423150PE",
            strike=23150, qty=225, reason="SL",
            entry_avg_price=Decimal("95"), mock_ltp=Decimal("85"),
            lot_size=75,
        )
        assert result["pnl_points"] == Decimal("-10")
        assert result["pnl_rupees"] == Decimal("-2250")

    def test_audit_log_created(self, om, db):
        from datetime import date
        from app.models.models import AuditLog
        om.place_buy_order(
            db=db, side="CE", level="L1",
            instrument="NIFTY123CE", strike=23000, expiry=date.today(),
            lots=1, lot_size=75, trigger_nifty=Decimal("23000"),
        )
        logs = db.query(AuditLog).all()
        assert len(logs) >= 1
        assert logs[0].event_type == "ORDER_PLACED"

    def test_paper_order_uses_mock_ltp_fallback(self, om, db):
        from datetime import date
        result = om.place_buy_order(
            db=db, side="PE", level="L1",
            instrument="NIFTY123PE", strike=23000, expiry=date.today(),
            lots=1, lot_size=75, trigger_nifty=Decimal("23100"),
            mock_ltp=None,  # No mock LTP provided
        )
        assert result["fill_price"] == Decimal("100.00")  # fallback price


class TestOrderManagerLiveMode:
    """Test OrderManager in live mode with mocked Kite."""

    @pytest.fixture
    def db(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.models.models import Base
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        yield db
        db.close()

    @pytest.fixture
    def mock_kite_svc(self):
        """Mock KiteService for live order tests."""
        kite_svc = MagicMock()
        kite_svc.kite = MagicMock()
        kite_svc.kite.place_order.return_value = "KITE-ORDER-12345"
        kite_svc.kite.orders.return_value = [
            {
                "order_id": "KITE-ORDER-12345",
                "status": "COMPLETE",
                "average_price": 98.75,
                "tradingsymbol": "NIFTY27JUN2423150CE",
                "transaction_type": "BUY",
                "quantity": 75,
            }
        ]
        return kite_svc

    @pytest.fixture
    def om_live(self, mock_kite_svc):
        from app.core.order_manager import OrderManager
        with patch("app.core.order_manager.settings") as s:
            s.PAPER_TRADE = False
            om = OrderManager(kite_service=mock_kite_svc)
            om.paper_trade = False
        return om, mock_kite_svc

    def test_live_buy_order_success(self, om_live, db):
        from datetime import date
        om, mock_kite = om_live
        with patch("time.sleep"):  # Speed up poll loop
            result = om.place_buy_order(
                db=db, side="CE", level="L1",
                instrument="NIFTY27JUN2423150CE", strike=23150,
                expiry=date.today(), lots=1, lot_size=75,
                trigger_nifty=Decimal("23100"),
            )
        assert result["order_id"] == "KITE-ORDER-12345"
        assert result["fill_price"] == Decimal("98.75")
        assert result["status"] == "COMPLETE"

    def test_live_order_rejected_raises(self, db):
        from datetime import date
        from app.core.order_manager import OrderManager, OrderError

        mock_kite_svc = MagicMock()
        mock_kite_svc.kite.place_order.return_value = "ORDER-99"
        mock_kite_svc.kite.orders.return_value = [
            {
                "order_id": "ORDER-99",
                "status": "REJECTED",
                "status_message": "Insufficient margin",
                "tradingsymbol": "NIFTY123CE",
                "transaction_type": "BUY",
                "quantity": 75,
            }
        ]

        with patch("app.core.order_manager.settings") as s:
            s.PAPER_TRADE = False
            om = OrderManager(kite_service=mock_kite_svc)
            om.paper_trade = False

        with patch("time.sleep"):
            with pytest.raises(OrderError, match="REJECTED"):
                om.place_buy_order(
                    db=db, side="CE", level="L1",
                    instrument="NIFTY123CE", strike=23000,
                    expiry=__import__("datetime").date.today(),
                    lots=1, lot_size=75, trigger_nifty=Decimal("23000"),
                )

    def test_live_order_timeout_raises(self, db):
        from datetime import date
        from app.core.order_manager import OrderManager, OrderError

        mock_kite_svc = MagicMock()
        mock_kite_svc.kite.place_order.return_value = "ORDER-TIMEOUT"
        mock_kite_svc.kite.orders.return_value = [
            {
                "order_id": "ORDER-TIMEOUT",
                "status": "OPEN",  # Never completes
                "tradingsymbol": "NIFTY123CE",
                "transaction_type": "BUY",
                "quantity": 75,
            }
        ]

        with patch("app.core.order_manager.settings") as s:
            s.PAPER_TRADE = False
            om = OrderManager(kite_service=mock_kite_svc)
            om.paper_trade = False
            om._FILL_POLL_SECS = 2  # Short timeout for test speed

        with patch("time.sleep"):
            with patch("app.core.order_manager._FILL_POLL_SECS", 2):
                with pytest.raises((OrderError, TimeoutError)):
                    om.place_buy_order(
                        db=db, side="CE", level="L1",
                        instrument="NIFTY123CE", strike=23000,
                        expiry=date.today(), lots=1, lot_size=75,
                        trigger_nifty=Decimal("23000"),
                    )

    def test_no_kite_raises_on_live(self, db):
        from datetime import date
        from app.core.order_manager import OrderManager, OrderError

        with patch("app.core.order_manager.settings") as s:
            s.PAPER_TRADE = False
            om = OrderManager(kite_service=None)  # No kite
            om.paper_trade = False

        with pytest.raises(OrderError, match="not initialized"):
            om.place_buy_order(
                db=db, side="CE", level="L1",
                instrument="NIFTY123CE", strike=23000,
                expiry=date.today(), lots=1, lot_size=75,
                trigger_nifty=Decimal("23000"),
            )


# ── Safety Checks Tests ───────────────────────────────────────────────────────

class TestSafetyChecks:
    @pytest.fixture
    def valid_config(self):
        return {
            "r1": 23200, "r2": 23250, "r3": 23300,
            "s1": 23100, "s2": 23050, "s3": 23000,
            "lot_size": 75, "target_points": 20, "sl_points": 10,
        }

    @pytest.fixture
    def mock_kite(self):
        kite = MagicMock()
        kite.is_authenticated.return_value = True
        kite.validate_token.return_value = True
        kite._instruments_loaded = True
        kite._is_connected = True
        kite.kite.margins.return_value = {
            "equity": {"available": {"live_balance": 100000}}
        }
        kite.kite.positions.return_value = {"day": []}
        return kite

    def test_paper_trade_passes_with_valid_config(self, valid_config, mock_kite):
        from app.core.safety_checks import run_safety_checks
        with patch("app.core.safety_checks.now_ist") as mock_now:
            mock_now.return_value = MagicMock(time=lambda: __import__("datetime").time(10, 0))
            passed, errors, warnings = run_safety_checks(
                paper_trade=True, kite_service=mock_kite, strategy_config=valid_config
            )
        assert passed is True
        assert errors == []

    def test_paper_trade_fails_without_config(self, mock_kite):
        from app.core.safety_checks import run_safety_checks
        with patch("app.core.safety_checks.now_ist") as mock_now:
            mock_now.return_value = MagicMock(time=lambda: __import__("datetime").time(10, 0))
            passed, errors, warnings = run_safety_checks(
                paper_trade=True, kite_service=mock_kite, strategy_config=None
            )
        assert passed is False
        assert any("config" in e.lower() for e in errors)

    def test_paper_trade_fails_after_1115(self, valid_config, mock_kite):
        from app.core.safety_checks import run_safety_checks
        with patch("app.core.safety_checks.now_ist") as mock_now:
            mock_now.return_value = MagicMock(time=lambda: __import__("datetime").time(11, 20))
            passed, errors, warnings = run_safety_checks(
                paper_trade=True, kite_service=mock_kite, strategy_config=valid_config
            )
        assert passed is False
        assert any("11:15" in e for e in errors)

    def test_paper_trade_warns_before_market_open(self, valid_config, mock_kite):
        from app.core.safety_checks import run_safety_checks
        with patch("app.core.safety_checks.now_ist") as mock_now:
            mock_now.return_value = MagicMock(time=lambda: __import__("datetime").time(9, 0))
            passed, errors, warnings = run_safety_checks(
                paper_trade=True, kite_service=mock_kite, strategy_config=valid_config
            )
        assert passed is True
        assert any("9:15" in w for w in warnings)

    def test_live_fails_without_kite_auth(self, valid_config):
        from app.core.safety_checks import run_safety_checks
        mock_kite = MagicMock()
        mock_kite.is_authenticated.return_value = False
        with patch("app.core.safety_checks.now_ist") as mock_now:
            mock_now.return_value = MagicMock(time=lambda: __import__("datetime").time(10, 0))
            passed, errors, warnings = run_safety_checks(
                paper_trade=False, kite_service=mock_kite, strategy_config=valid_config
            )
        assert passed is False
        assert any("authenticated" in e.lower() for e in errors)

    def test_live_fails_with_expired_token(self, valid_config):
        from app.core.safety_checks import run_safety_checks
        mock_kite = MagicMock()
        mock_kite.is_authenticated.return_value = True
        mock_kite.validate_token.return_value = False
        mock_kite._instruments_loaded = True
        mock_kite._is_connected = True
        with patch("app.core.safety_checks.now_ist") as mock_now:
            mock_now.return_value = MagicMock(time=lambda: __import__("datetime").time(10, 0))
            passed, errors, warnings = run_safety_checks(
                paper_trade=False, kite_service=mock_kite, strategy_config=valid_config
            )
        assert passed is False
        assert any("expired" in e.lower() for e in errors)

    def test_live_fails_without_instruments(self, valid_config):
        from app.core.safety_checks import run_safety_checks
        mock_kite = MagicMock()
        mock_kite.is_authenticated.return_value = True
        mock_kite.validate_token.return_value = True
        mock_kite._instruments_loaded = False
        mock_kite._is_connected = True
        with patch("app.core.safety_checks.now_ist") as mock_now:
            mock_now.return_value = MagicMock(time=lambda: __import__("datetime").time(10, 0))
            passed, errors, warnings = run_safety_checks(
                paper_trade=False, kite_service=mock_kite, strategy_config=valid_config
            )
        assert passed is False
        assert any("instruments" in e.lower() for e in errors)

    def test_live_passes_with_all_valid(self, valid_config, mock_kite):
        from app.core.safety_checks import run_safety_checks
        with patch("app.core.safety_checks.now_ist") as mock_now:
            mock_now.return_value = MagicMock(time=lambda: __import__("datetime").time(10, 0))
            passed, errors, warnings = run_safety_checks(
                paper_trade=False, kite_service=mock_kite, strategy_config=valid_config
            )
        assert passed is True
        assert errors == []

    def test_live_warns_insufficient_margin(self, valid_config):
        from app.core.safety_checks import run_safety_checks
        mock_kite = MagicMock()
        mock_kite.is_authenticated.return_value = True
        mock_kite.validate_token.return_value = True
        mock_kite._instruments_loaded = True
        mock_kite._is_connected = True
        mock_kite.kite.margins.return_value = {
            "equity": {"available": {"live_balance": 10000}}  # Too low
        }
        mock_kite.kite.positions.return_value = {"day": []}

        with patch("app.core.safety_checks.now_ist") as mock_now:
            mock_now.return_value = MagicMock(time=lambda: __import__("datetime").time(10, 0))
            passed, errors, warnings = run_safety_checks(
                paper_trade=False, kite_service=mock_kite, strategy_config=valid_config
            )
        assert passed is False
        assert any("margin" in e.lower() or "insufficient" in e.lower() for e in errors)

    def test_live_warns_existing_positions(self, valid_config):
        from app.core.safety_checks import run_safety_checks
        mock_kite = MagicMock()
        mock_kite.is_authenticated.return_value = True
        mock_kite.validate_token.return_value = True
        mock_kite._instruments_loaded = True
        mock_kite._is_connected = True
        mock_kite.kite.margins.return_value = {
            "equity": {"available": {"live_balance": 200000}}
        }
        mock_kite.kite.positions.return_value = {
            "day": [{"exchange": "NFO", "tradingsymbol": "NIFTY123PE", "quantity": 75}]
        }

        with patch("app.core.safety_checks.now_ist") as mock_now:
            mock_now.return_value = MagicMock(time=lambda: __import__("datetime").time(10, 0))
            passed, errors, warnings = run_safety_checks(
                paper_trade=False, kite_service=mock_kite, strategy_config=valid_config
            )
        assert any("position" in w.lower() for w in warnings)
