import sys
import types

import pymysql
import pytest
import redis
import requests
from flask_jwt_extended import create_access_token


# main.py imports ai_model with a wildcard.  A lightweight module prevents
# model downloads and FAISS access while route/controller behavior is tested.
sys.modules.setdefault("ai_model", types.ModuleType("ai_model"))

import main as mentorx_main


@pytest.fixture(autouse=True)
def forbid_external_services(monkeypatch):
    """Fail immediately if a test accidentally reaches a real external service."""

    def denied(*args, **kwargs):
        raise AssertionError("测试禁止访问公网、真实 MySQL 或真实 Redis")

    monkeypatch.setattr(requests.sessions.Session, "request", denied)
    monkeypatch.setattr(pymysql, "connect", denied)
    monkeypatch.setattr(redis.Redis, "execute_command", denied)


@pytest.fixture
def app():
    mentorx_main.app.config.update(
        TESTING=True,
        JWT_SECRET_KEY="pytest-only-secret-key-at-least-32-bytes-long",
    )
    return mentorx_main.app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(app):
    def make_headers(identity="42"):
        with app.app_context():
            token = create_access_token(identity=str(identity))
        return {"Authorization": f"Bearer {token}"}

    return make_headers
