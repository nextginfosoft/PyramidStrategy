import os
import pytest
import tempfile
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from app.models.models import User, Trade, DailyPnL, AISuggestion, AuditLog, ApiConfig, StrategyConfig
from app.services.reporting import (
    get_user_reporting_config,
    generate_daily_report,
    generate_weekly_report,
    send_daily_report,
    send_weekly_report
)
from app.services.pdf_generator import build_daily_report_pdf, build_weekly_report_pdf
from app.services.whatsapp import WhatsAppService, get_user_whatsapp_service


class TestReportingService:
    @pytest.fixture
    def mock_db(self):
        # Create a mock database session
        db = MagicMock(spec=Session)
        return db

    def test_get_user_reporting_config_default(self, mock_db):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        config = get_user_reporting_config(1, mock_db)
        assert config == {"format": "telegram"}

    def test_get_user_reporting_config_saved(self, mock_db):
        saved_config = ApiConfig(
            user_id=1,
            provider="reporting",
            extra_config={"format": "pdf"}
        )
        mock_db.query.return_value.filter.return_value.first.return_value = saved_config
        config = get_user_reporting_config(1, mock_db)
        assert config == {"format": "pdf"}

    def test_generate_daily_report_calculations(self, mock_db):
        target_date = date(2026, 6, 19)
        mock_user = User(id=1, username="test_trader")
        
        # Mock trades
        trade1 = Trade(
            user_id=1,
            trade_date=target_date,
            side="CE",
            action="BUY",
            lots=1,
            avg_price=Decimal("100.0"),
            created_at=datetime(2026, 6, 19, 9, 30)
        )
        trade2 = Trade(
            user_id=1,
            trade_date=target_date,
            side="CE",
            action="EXIT",
            lots=1,
            avg_price=Decimal("120.0"),
            pnl=Decimal("1500.0"),
            status="TARGET",
            created_at=datetime(2026, 6, 19, 10, 00)
        )
        trades = [trade1, trade2]
        
        # Mock audit logs
        audit_log = AuditLog(
            user_id=1,
            event_type="ORDER_PLACED",
            side="CE",
            level="L1",
            nifty_price=Decimal("23500.0"),
            details={"msg": "Placed target CE lot"},
            created_at=datetime(2026, 6, 19, 9, 30)
        )
        
        # Mock AI observation
        ai_obs = AISuggestion(
            user_id=1,
            trade_date=target_date,
            event="ENTRY",
            side="CE",
            suggestion="NIFTY CE trigger verified",
            created_at=datetime(2026, 6, 19, 9, 31)
        )

        def mock_query(model):
            q = MagicMock()
            if model == User:
                q.filter.return_value.first.return_value = mock_user
            elif model == DailyPnL:
                q.filter.return_value.first.return_value = None
            elif model == Trade:
                q.filter.return_value.order_by.return_value.all.return_value = trades
            elif model == AuditLog:
                q.filter.return_value.order_by.return_value.all.return_value = [audit_log]
            elif model == AISuggestion:
                q.filter.return_value.order_by.return_value.all.return_value = [ai_obs]
            return q
            
        mock_db.query.side_effect = mock_query

        report_msg = generate_daily_report(1, target_date, mock_db)
        
        assert "Daily EOD Report" in report_msg
        assert "Gross P&L" in report_msg
        assert "Est. Brokerage" in report_msg
        assert "Net P&L" in report_msg
        assert "Trades Log" in report_msg
        assert "Strategy Decisions & Triggers" in report_msg
        assert "AI Observations" in report_msg
        assert "NIFTY CE trigger verified" in report_msg

    def test_pdf_compilation(self, mock_db):
        target_date = date(2026, 6, 19)
        mock_user = User(id=1, username="test_trader")
        
        def mock_query(model):
            q = MagicMock()
            if model == User:
                q.filter.return_value.first.return_value = mock_user
            elif model == DailyPnL:
                q.filter.return_value.first.return_value = None
            elif model == Trade:
                q.filter.return_value.order_by.return_value.all.return_value = []
            elif model == AuditLog:
                q.filter.return_value.order_by.return_value.all.return_value = []
            elif model == AISuggestion:
                q.filter.return_value.order_by.return_value.all.return_value = []
            elif model == StrategyConfig:
                q.filter.return_value.first.return_value = None
            return q
            
        mock_db.query.side_effect = mock_query

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "test_report.pdf")
            build_daily_report_pdf(1, target_date, mock_db, pdf_path)
            
            assert os.path.exists(pdf_path)
            assert os.path.getsize(pdf_path) > 0

    def test_weekly_pdf_compilation(self, mock_db):
        monday_date = date(2026, 6, 22)
        mock_user = User(id=1, username="test_trader")
        
        def mock_query(model):
            q = MagicMock()
            if model == User:
                q.filter.return_value.first.return_value = mock_user
            elif model == DailyPnL:
                q.filter.return_value.order_by.return_value.all.return_value = []
            return q
            
        mock_db.query.side_effect = mock_query

        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, "test_weekly_report.pdf")
            build_weekly_report_pdf(1, monday_date, mock_db, pdf_path)
            
            assert os.path.exists(pdf_path)
            assert os.path.getsize(pdf_path) > 0

    def test_timezone_conversion(self):
        from app.core.time_rules import to_ist_str
        import pytz
        
        # Test case 1: None or empty datetime
        assert to_ist_str(None) == ""
        
        # Test case 2: Naive UTC datetime
        # 2026-06-19 09:30 UTC should be 2026-06-19 15:00 IST (03:00 PM)
        dt = datetime(2026, 6, 19, 9, 30)
        assert to_ist_str(dt) == "03:00 PM"
        
        # Test case 3: Timezone-aware UTC datetime
        dt_aware = datetime(2026, 6, 19, 9, 30, tzinfo=pytz.utc)
        assert to_ist_str(dt_aware) == "03:00 PM"




class TestWhatsAppService:
    def test_whatsapp_initial_state(self):
        ws = WhatsAppService(user_id=2)
        assert ws.is_enabled() is False
        assert ws._provider_type == "meta"

    def test_whatsapp_meta_configure(self):
        ws = WhatsAppService(user_id=2)
        ws.configure_meta("access-token-xyz", "12345", "+919999999999")
        assert ws.is_enabled() is True
        assert ws._provider_type == "meta"

    def test_whatsapp_twilio_configure(self):
        ws = WhatsAppService(user_id=2)
        ws.configure_twilio("twilio-sid-123", "twilio-auth-456", "+123456", "+654321")
        assert ws.is_enabled() is True
        assert ws._provider_type == "twilio"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_meta_send_message_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp
        
        ws = WhatsAppService(user_id=2)
        ws.configure_meta("access-token-xyz", "12345", "+919999999999")
        
        success = await ws.send_message("Testing WhatsApp message")
        assert success is True
        mock_post.assert_called_once()
        
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_twilio_send_message_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_post.return_value = mock_resp
        
        ws = WhatsAppService(user_id=2)
        ws.configure_twilio("twilio-sid-123", "twilio-auth-456", "+123456", "+654321")
        
        success = await ws.send_message("Testing Twilio WhatsApp")
        assert success is True
        mock_post.assert_called_once()
