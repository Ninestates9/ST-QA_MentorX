from __future__ import annotations

import importlib.util
import socket
import sys
import types
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


if importlib.util.find_spec("pymysql") is None:
    pymysql_stub = types.ModuleType("pymysql")

    def _forbid_mysql_connection(*args, **kwargs):
        raise AssertionError("unit tests must not connect to a real MySQL server")

    pymysql_stub.connect = _forbid_mysql_connection
    sys.modules["pymysql"] = pymysql_stub


@pytest.fixture(autouse=True)
def forbid_real_network(monkeypatch: pytest.MonkeyPatch):
    def _blocked_connect(self, address):
        raise AssertionError(f"network access is forbidden in unit tests: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)
