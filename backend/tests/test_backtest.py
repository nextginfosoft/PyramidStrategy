import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.models.models import User
from app.api.routes.backtest import router
from app.api.routes.session import require_auth

class TestBacktestRoutes:
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
        
        # Override get_db dependency
        app.dependency_overrides[get_db] = lambda: db_session
        
        # Override require_auth dependency to return a mock user
        dummy_user = User(id=1, username="test@example.com")
        app.dependency_overrides[require_auth] = lambda: dummy_user
        
        return TestClient(app)

    def test_run_backtest_mock(self, client):
        # Execute backtest with mock Nifty generator
        payload = {
            "start_date": "2026-06-18",
            "end_date": "2026-06-18",
            "config": {
                "r1": 24100.0,
                "r2": 24200.0,
                "r3": 24300.0,
                "s1": 23900.0,
                "s2": 23800.0,
                "s3": 23700.0,
                "lot_size": 75,
                "target_points": 20.0,
                "sl_points": 10.0,
                "name": "Config A"
            },
            "compare_configs": [
                {
                    "r1": 24080.0,
                    "r2": 24180.0,
                    "r3": 24280.0,
                    "s1": 23920.0,
                    "s2": 23820.0,
                    "s3": 23720.0,
                    "lot_size": 75,
                    "target_points": 20.0,
                    "sl_points": 10.0,
                    "name": "Config B"
                }
            ]
        }

        resp = client.post("/backtest", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "primary" in data
        assert "summary" in data["primary"]
        assert "trades" in data["primary"]
        assert "comparisons" in data
        assert len(data["comparisons"]) == 1
        assert data["comparisons"][0]["name"] == "Config B"
