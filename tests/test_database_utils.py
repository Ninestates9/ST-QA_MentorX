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


def test_commit_exercise_db_01(monkeypatch):
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


def test_commit_exercise_db_02(monkeypatch):
    connection, cursor, _ = _replace_database(monkeypatch, fetchone_results=[(0,)])

    result = database_utils.commit_exercise_db(1001, 21, "修改后的答案")

    assert result is True
    assert len(cursor.executions) == 2
    assert "UPDATE practice_history" in cursor.executions[1][0]
    assert cursor.executions[1][1] == ("修改后的答案", 1001, 21)
    assert cursor.closed is True
    assert connection.closed is True


def test_commit_exercise_db_03(monkeypatch):
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


def test_get_exercise_history_db_01(monkeypatch):
    cases = [
        (None, (2, None)),
        (
            ("answer", "2026-01-01", None, None),
            (3, ("answer", "2026-01-01", None, None)),
        ),
        (
            ("answer", "2026-01-01", 0, "good"),
            (0, ("answer", "2026-01-01", 0, "good")),
        ),
    ]

    for row, expected in cases:
        connection, cursor, _ = _replace_database(
            monkeypatch, fetchone_results=[row]
        )

        result = database_utils.get_exercise_history_db(1001, 21)

        assert result == expected
        assert cursor.closed is True
        assert connection.closed is True


def test_register_db_01(monkeypatch):
    connection, cursor, _ = _replace_database(monkeypatch, fetchone_results=[None])
    password_hash = Mock(return_value="hashed-password")
    monkeypatch.setattr(database_utils, "generate_password_hash", password_hash)

    result = database_utils.register_db(
        "13800000000", "pw", "S", "Alice", "female"
    )

    assert result is True
    password_hash.assert_called_once_with("pw")
    assert "INSERT INTO user" in cursor.executions[1][0]
    assert cursor.executions[1][1] == (
        "13800000000",
        "hashed-password",
        "S",
        "Alice",
        "female",
    )
    assert cursor.closed is True
    assert connection.closed is True


def test_f_getLearningStatsByChapter_01(monkeypatch):
    connection, cursor, _ = _replace_database(
        monkeypatch, fetchone_results=[("Chapter 1",), (0,), (0,), (0,)]
    )

    result = database_utils.f_getLearningStatsByChapter(3, student_id=10)

    assert result == {
        "name": "Chapter 1",
        "AiFrequence": 0.0,
        "correctness": 0,
        "sum_exercises": 0,
        "right_exercises": 0,
    }
    assert cursor.closed is True
    assert connection.closed is True


def test_format_date_01():
    assert database_utils.format_date(datetime(2026, 9, 14, 8, 9, 10)) == (
        "2026-09-14 08:09:10"
    )
    assert database_utils.format_date(date(2026, 9, 14)) == "2026-09-14"
    assert database_utils.format_date("already-formatted") == "already-formatted"
    assert database_utils.format_date(None) is None


def test_get_system_stats_db_01(monkeypatch):
    expected_stats = tuple(range(11, 19))
    redis_client = Mock()
    redis_client.get.side_effect = RuntimeError("Redis unavailable")
    connection, cursor, connect_sql = _replace_database(
        monkeypatch, fetchone_results=[expected_stats]
    )
    monkeypatch.setattr(database_utils, "redis_client", redis_client)

    result = database_utils.get_system_stats_db()

    assert result == expected_stats
    connect_sql.assert_called_once_with()
    assert cursor.executions == [("SELECT * FROM system_stats;", None)]
    assert cursor.closed is True
    assert connection.closed is True


def test_get_system_stats_db_02(monkeypatch):
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


def test_increase_count_01(monkeypatch):
    redis_client = Mock()
    redis_client.incr.side_effect = RuntimeError("Redis unavailable")
    connection, cursor, connect_sql = _replace_database(
        monkeypatch, fetchone_results=[]
    )
    monkeypatch.setattr(database_utils, "redis_client", redis_client)

    result = database_utils.increase_count("generate_tasks")

    assert result is True
    connect_sql.assert_called_once_with()
    assert "`generate_tasks` = `generate_tasks` + 1" in cursor.executions[0][0]
    assert cursor.closed is True
    assert connection.closed is True


def test_update_info_db_01(monkeypatch):
    connection, cursor, _ = _replace_database(
        monkeypatch, fetchone_results=[("S",)]
    )
    password_hash = Mock(return_value="hashed-new-password")
    monkeypatch.setattr(database_utils, "generate_password_hash", password_hash)

    result = database_utils.update_info_db(42, "new-password", None, None)

    assert result is True
    password_hash.assert_called_once_with("new-password")
    assert cursor.executions[1][1] == ("hashed-new-password", 42)
    assert cursor.closed is True
    assert connection.closed is True
