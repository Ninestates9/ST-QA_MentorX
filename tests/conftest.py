from __future__ import annotations

import importlib
import importlib.util
import socket
import sys
import types
from pathlib import Path

import pytest
import redis
import requests
from flask_jwt_extended import create_access_token


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


if importlib.util.find_spec("pymysql") is None:
    pymysql_stub = types.ModuleType("pymysql")

    def _forbid_mysql_connection(*args, **kwargs):
        raise AssertionError("unit tests must not connect to a real MySQL server")

    pymysql_stub.connect = _forbid_mysql_connection
    sys.modules["pymysql"] = pymysql_stub

import pymysql


TEST_STUDENT_ID = 1001


def _unconfigured_ai_call(*args, **kwargs):
    raise AssertionError("AI/PPT dependency was not replaced by this test")


def _install_import_stubs():
    ai_model = types.ModuleType("ai_model")
    for name in (
        "ai_aichat",
        "ai_generate_tasks",
        "ai_generate_daily_tasks",
        "ai_check_answer",
        "ai_generate_teachcontent",
        "ai_generate_suggestion",
        "ai_img2word",
    ):
        setattr(ai_model, name, _unconfigured_ai_call)
    sys.modules["ai_model"] = ai_model

    ai_ppt = types.ModuleType("aiPPT")
    ai_ppt.ai_generate_ppt = _unconfigured_ai_call
    sys.modules["aiPPT"] = ai_ppt


_install_import_stubs()


class AuthHeaders(dict):
    def __init__(self, app, identity):
        self._app = app
        super().__init__(self._for_identity(identity))

    def _for_identity(self, identity):
        with self._app.app_context():
            token = create_access_token(identity=str(identity))
        return {"Authorization": f"Bearer {token}"}

    def __call__(self, identity="42"):
        return self._for_identity(identity)


@pytest.fixture(autouse=True)
def forbid_external_services(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("测试禁止访问公网、真实 MySQL 或真实 Redis")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(requests.sessions.Session, "request", denied)
    monkeypatch.setattr(pymysql, "connect", denied)
    monkeypatch.setattr(redis.Redis, "execute_command", denied)


@pytest.fixture(scope="session")
def app_module():
    module = importlib.import_module("main")
    module.app.config.update(
        TESTING=True,
        JWT_SECRET_KEY="mentorx-pytest-only-secret-at-least-32-bytes-long",
        PROPAGATE_EXCEPTIONS=False,
    )
    return module


@pytest.fixture()
def app(app_module):
    return app_module.app


@pytest.fixture()
def client(app_module):
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def student_id():
    return TEST_STUDENT_ID


@pytest.fixture()
def auth_headers(app_module, student_id):
    return AuthHeaders(app_module.app, student_id)
