"""TC-045 to TC-051 (selected): deterministic database and Redis logic."""

from datetime import date, datetime
from unittest.mock import Mock

import database_utils

from tests.fakes import FakeConnection, FakeCursor


def _replace_database(monkeypatch, fetchone_results):
    connection = FakeConnection()
    cursor = FakeCursor(fetchone_results=fetchone_results)
    connect_sql = Mock(return_value=(connection, cursor))
    monkeypatch.setattr(database_utils, "connectSQL", connect_sql)
    return connection, cursor, connect_sql


def test_tc045_commit_exercise_without_history_inserts_record(monkeypatch):
    connection, cursor, connect_sql = _replace_database(
        monkeypatch, fetchone_results=[None, (7,)]
    )

    result = database_utils.commit_exercise_db(1001, 21, "学生答案")

    assert result is True
    connect_sql.assert_called_once_with()
    assert len(cursor.executions) == 3
    assert cursor.executions[0][1] == (1001, 21)
    assert cursor.executions[1][1] == (21,)
    assert "INSERT INTO practice_history" in cursor.executions[2][0]
    assert cursor.executions[2][1] == (1001, 21, "学生答案", 7)
    assert cursor.closed is True
    assert connection.closed is True


def test_tc046_commit_exercise_with_check_zero_currently_updates(monkeypatch):
    connection, cursor, _ = _replace_database(
        monkeypatch, fetchone_results=[(0,)]
    )

    result = database_utils.commit_exercise_db(1001, 21, "修改后的答案")

    # check=0 means "correct", but the current truth-value branch permits UPDATE.
    assert result is True
    assert len(cursor.executions) == 2
    assert "UPDATE practice_history" in cursor.executions[1][0]
    assert cursor.executions[1][1] == ("修改后的答案", 1001, 21)
    assert cursor.closed is True
    assert connection.closed is True


def test_tc047_commit_exercise_with_check_one_or_two_is_rejected(monkeypatch):
    for check_status in (1, 2):
        connection, cursor, _ = _replace_database(
            monkeypatch, fetchone_results=[(check_status,)]
        )

        result = database_utils.commit_exercise_db(1001, 21, "修改后的答案")

        assert result is False
        assert len(cursor.executions) == 1
        assert cursor.executions[0][1] == (1001, 21)
        assert cursor.closed is True
        assert connection.closed is True


def test_tc049_format_date_boundaries():
    assert database_utils.format_date(datetime(2026, 9, 14, 8, 9, 10)) == (
        "2026-09-14 08:09:10"
    )
    assert database_utils.format_date(date(2026, 9, 14)) == "2026-09-14"
    assert database_utils.format_date("already-formatted") == "already-formatted"
    assert database_utils.format_date(None) is None


def test_tc050_get_system_stats_uses_redis_and_defaults_missing_key(monkeypatch):
    stored_values = {
        key: str(index + 1) for index, key in enumerate(database_utils.redis_keys)
    }
    stored_values[database_utils.redis_keys[1]] = None
    redis_client = Mock()
    redis_client.get.side_effect = stored_values.get
    connect_sql = Mock(side_effect=AssertionError("MySQL must not be accessed"))
    monkeypatch.setattr(database_utils, "redis_client", redis_client)
    monkeypatch.setattr(database_utils, "connectSQL", connect_sql)

    result = database_utils.get_system_stats_db()

    assert result == [1, 0, 3, 4, 5, 6, 7, 8]
    assert redis_client.get.call_count == len(database_utils.redis_keys)
    connect_sql.assert_not_called()


def test_tc051_get_system_stats_falls_back_to_mysql(monkeypatch):
    expected_stats = tuple(range(11, 19))
    redis_client = Mock()
    redis_client.get.side_effect = RuntimeError("Redis unavailable")
    connection = FakeConnection()
    cursor = FakeCursor(fetchone_results=[expected_stats])
    connect_sql = Mock(return_value=(connection, cursor))
    monkeypatch.setattr(database_utils, "redis_client", redis_client)
    monkeypatch.setattr(database_utils, "connectSQL", connect_sql)

    result = database_utils.get_system_stats_db()

    assert result == expected_stats
    connect_sql.assert_called_once_with()
    assert cursor.executions == [("SELECT * FROM system_stats;", None)]
    assert cursor.closed is True
    assert connection.closed is True
