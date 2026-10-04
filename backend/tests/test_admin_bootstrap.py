"""Master-admin bootstrap: no built-in password outside development."""
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db.database import Base
from app.models.models import User


@pytest.fixture
def Session():
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)


def run_bootstrap(Session, **env):
    from app import main
    s = Settings(_env_file=None, **env)
    with patch("app.db.database.SessionLocal", Session), patch.object(main, "settings", s):
        main._bootstrap_master_admin()
    with Session() as db:
        return db.query(User).all()


def test_production_without_password_creates_no_admin(Session):
    assert run_bootstrap(Session, APP_ENV="production") == []


def test_production_with_password_creates_admin_with_that_password(Session):
    from app.api.routes.session import verify_password
    users = run_bootstrap(Session, APP_ENV="production", SUPER_ADMIN_PASSWORD="s3cret-for-test")
    assert [u.username for u in users] == ["santosh"] and users[0].is_admin and users[0].is_approved
    assert verify_password("s3cret-for-test", users[0].hashed_password)
    assert not verify_password("santosh123", users[0].hashed_password)


def test_development_keeps_local_default(Session):
    users = run_bootstrap(Session, APP_ENV="development")
    assert [u.username for u in users] == ["santosh"]


def test_custom_admin_username_is_used(Session):
    users = run_bootstrap(Session, APP_ENV="production", SUPER_ADMIN_USERNAME="ops", SUPER_ADMIN_PASSWORD="x-y-z-123456")
    assert [u.username for u in users] == ["ops"]
