import pytest
import os
import csv
from io import StringIO
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.models.models import User, Trade, DailyPnL
from app.api.routes.trades import router
from app.api.routes.session import require_auth
from app.core.time_rules import today_ist

class TestTradesRoutes:
    @pytest.fixture
    def db_session(self):
        """In-memory SQLite DB for testing."""
        from sqlalchemy.pool import StaticPool
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        yield db
        db.close()

    @pytest.fixture
    def client(self, db_session):
        app = FastAPI()
        app.include_router(router)
        
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        # Mock dependencies
        dummy_user = User(id=1, username="admin")
        app.dependency_overrides[require_auth] = lambda: dummy_user
        app.dependency_overrides[get_db] = override_get_db
        
        return TestClient(app)

    def test_get_today_trades_empty(self, client):
        resp = client.get("/trades/today")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_today_trades(self, client, db_session):
        # Seed user and trades
        user = User(id=1, username="admin", hashed_password="xxx")
        db_session.add(user)
        db_session.commit()

        t1 = Trade(
            user_id=1,
            trade_date=today_ist(),
            side="CE",
            level="R1",
            instrument="NIFTY27JUN2423100CE",
            strike=23100,
            expiry=today_ist(),
            action="BUY",
            lots=1,
            qty=75,
            avg_price=Decimal("100.50"),
            trigger_nifty_level=Decimal("23050.00"),
            kite_order_id="12345",
            status="OPEN",
            is_paper_trade=True,
            created_at=datetime.utcnow()
        )
        db_session.add(t1)
        db_session.commit()

        resp = client.get("/trades/today")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["instrument"] == "NIFTY27JUN2423100CE"
        assert data[0]["side"] == "CE"

    def test_get_trade_history(self, client, db_session):
        user = User(id=1, username="admin", hashed_password="xxx")
        db_session.add(user)
        db_session.commit()

        yesterday = today_ist() - timedelta(days=1)
        t_history = Trade(
            user_id=1,
            trade_date=yesterday,
            side="PE",
            level="S1",
            instrument="NIFTY27JUN2423000PE",
            strike=23000,
            expiry=yesterday,
            action="EXIT",
            lots=1,
            qty=75,
            avg_price=Decimal("110.00"),
            trigger_nifty_level=Decimal("23020.00"),
            kite_order_id="54321",
            status="TARGET",
            pnl=Decimal("750.00"),
            is_paper_trade=True,
            created_at=datetime.utcnow() - timedelta(days=1)
        )
        db_session.add(t_history)
        db_session.commit()

        resp = client.get("/trades/history", params={"from_date": yesterday.isoformat()})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["side"] == "PE"

    def test_get_today_pnl(self, client, db_session):
        user = User(id=1, username="admin", hashed_password="xxx")
        db_session.add(user)
        db_session.commit()

        t_exit = Trade(
            user_id=1,
            trade_date=today_ist(),
            side="CE",
            level="R1",
            instrument="NIFTY27JUN2423100CE",
            strike=23100,
            expiry=today_ist(),
            action="EXIT",
            lots=1,
            qty=75,
            avg_price=Decimal("120.00"),
            trigger_nifty_level=Decimal("23050.00"),
            kite_order_id="12345",
            status="TARGET",
            pnl=Decimal("1500.00"),
            is_paper_trade=True,
            created_at=datetime.utcnow()
        )
        db_session.add(t_exit)
        db_session.commit()

        resp = client.get("/trades/pnl/today")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gross_pnl"] == 1500.0
        assert data["total_exits"] == 1
        assert data["winning_trades"] == 1

    def test_get_pnl_history(self, client, db_session):
        user = User(id=1, username="admin", hashed_password="xxx")
        db_session.add(user)
        db_session.commit()

        pnl = DailyPnL(
            user_id=1,
            trade_date=today_ist() - timedelta(days=1),
            gross_pnl=Decimal("2500.00"),
            brokerage=Decimal("40.00"),
            net_pnl=Decimal("2460.00"),
            total_trades=2,
            winning_trades=1,
            ce_pnl=Decimal("2500.00"),
            pe_pnl=Decimal("0.00"),
            created_at=datetime.utcnow() - timedelta(days=1)
        )
        db_session.add(pnl)
        db_session.commit()

        resp = client.get("/trades/pnl/history")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["gross_pnl"] == 2500.0
        assert data[0]["net_pnl"] == 2460.0

    def test_export_trades_csv(self, client, db_session):
        user = User(id=1, username="admin", hashed_password="xxx")
        db_session.add(user)
        db_session.commit()

        t1 = Trade(
            user_id=1,
            trade_date=today_ist(),
            side="CE",
            level="L1",
            instrument="NIFTY27JUN2423100CE",
            strike=23100,
            expiry=today_ist(),
            action="BUY",
            lots=1,
            qty=75,
            avg_price=Decimal("100.50"),
            trigger_nifty_level=Decimal("23050.00"),
            kite_order_id="12345",
            status="OPEN",
            is_paper_trade=True,
            created_at=datetime.utcnow()
        )
        db_session.add(t1)
        db_session.commit()

        resp = client.get("/trades/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment; filename=pyramid_trades.csv" in resp.headers["content-disposition"]
        
        # Parse CSV content
        csv_content = resp.text
        f = StringIO(csv_content)
        reader = csv.reader(f)
        rows = list(reader)
        
        assert len(rows) == 2  # Header + 1 trade
        assert rows[0][0] == "Trade ID"
        assert rows[1][1] == "S1"  # CE + L1 maps to S1
        assert rows[1][2] == "NIFTY27JUN2423100CE"

    @patch("os.path.exists", return_value=False)
    def test_get_logs_empty(self, mock_exists, client):
        resp = client.get("/trades/logs")
        assert resp.status_code == 200
        assert resp.json() == {"logs": []}

    @patch("os.path.exists", return_value=True)
    def test_get_logs_filtered(self, mock_exists, client):
        dummy_log_content = (
            "2026-06-18 08:30:00 | INFO | app.core: Early log\n"
            "2026-06-18 09:30:00 | INFO | app.core: Log 1 inside\n"
            "2026-06-18 11:15:00 | INFO | app.core: Log 2 inside\n"
            "2026-06-18 12:45:00 | INFO | app.core: Late log\n"
        )
        from unittest.mock import mock_open
        with patch("builtins.open", mock_open(read_data=dummy_log_content)):
            resp = client.get("/trades/logs?start_time=09:00&end_time=12:30")
            assert resp.status_code == 200
            data = resp.json()["logs"]
            assert len(data) == 2
            assert "Log 1 inside" in data[0]
            assert "Log 2 inside" in data[1]

    @patch("os.path.exists", return_value=True)
    def test_get_logs_trade_only_filter(self, mock_exists, client):
        dummy_log_content = (
            "2026-06-18 09:30:00 | INFO | app.core: Place BUY order\n"
            "2026-06-18 09:35:00 | INFO | app.services.kite: connection heartbeats\n"
            "2026-06-18 10:00:00 | INFO | app.core: Target achieved\n"
        )
        from unittest.mock import mock_open
        with patch("builtins.open", mock_open(read_data=dummy_log_content)):
            # With trade_only=True (default)
            resp = client.get("/trades/logs?start_time=09:00&end_time=11:00")
            assert resp.status_code == 200
            data = resp.json()["logs"]
            assert len(data) == 2
            assert "Place BUY order" in data[0]
            assert "Target achieved" in data[1]

            # With trade_only=False
            resp = client.get("/trades/logs?start_time=09:00&end_time=11:00&trade_only=false")
            assert resp.status_code == 200
            data_all = resp.json()["logs"]
            assert len(data_all) == 3
            assert "connection heartbeats" in data_all[1]

    @patch("os.path.exists", return_value=False)
    def test_export_logs_not_found(self, mock_exists, client):
        resp = client.get("/trades/logs/export")
        assert resp.status_code == 404
        assert "Log file not found" in resp.json()["detail"]

    @patch("os.path.exists", return_value=True)
    @patch("fastapi.responses.FileResponse")
    def test_export_logs_success(self, mock_file_response, mock_exists, client):
        from fastapi.responses import Response
        mock_file_response.return_value = Response(
            content="Log line 1\nLog line 2\n",
            media_type="text/plain",
            headers={"content-disposition": 'attachment; filename="trade_engine.log"'}
        )
        resp = client.get("/trades/logs/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/plain; charset=utf-8"
        assert 'filename="trade_engine.log"' in resp.headers["content-disposition"]
        assert resp.text.replace("\r\n", "\n") == "Log line 1\nLog line 2\n"

    @patch("os.path.exists", return_value=True)
    def test_get_logs_dynamic_default(self, mock_exists, client, db_session):
        from app.models.models import StrategyConfig
        # Create strategy config for test user (user.id = 1)
        cfg = StrategyConfig(
            user_id=1,
            r1=23170, r2=23220, r3=23250,
            s1=23070, s2=23025, s3=22950,
            lot_size=75,
            target_points=20,
            sl_points=10,
            paper_trade=True,
            squareoff_time="14:30",
            is_active=True
        )
        db_session.add(cfg)
        db_session.commit()

        dummy_log_content = (
            "2026-06-18 09:30:00 | INFO | app.core: Log 1 inside\n"
            "2026-06-18 15:15:00 | INFO | app.core: Log 2 inside\n"
            "2026-06-18 15:45:00 | INFO | app.core: Late log\n"
        )
        from unittest.mock import mock_open
        with patch("builtins.open", mock_open(read_data=dummy_log_content)):
            resp = client.get("/trades/logs?start_time=09:00")
            assert resp.status_code == 200
            data = resp.json()["logs"]
            assert len(data) == 2
            assert "Log 1 inside" in data[0]
            assert "Log 2 inside" in data[1]
