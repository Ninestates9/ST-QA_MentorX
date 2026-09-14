from unittest.mock import MagicMock

import database_utils as db


def _patch_db(monkeypatch, cursor):
    connection = MagicMock()
    close = MagicMock()
    monkeypatch.setattr(db, "connectSQL", lambda: (connection, cursor))
    monkeypatch.setattr(db, "closeSQL", close)
    return connection, close


def test_commit_exercise_db_01(monkeypatch):
    cursor = MagicMock()
    cursor.fetchone.side_effect = [None, (7,)]
    connection, close = _patch_db(monkeypatch, cursor)

    assert db.commit_exercise_db(2, 9, "first answer") is True

    assert cursor.execute.call_count == 3
    insert_sql, insert_params = cursor.execute.call_args_list[2].args
    assert "INSERT INTO practice_history" in insert_sql
    assert insert_params == (2, 9, "first answer", 7)
    close.assert_called_once_with(connection, cursor)


def test_commit_exercise_db_02(monkeypatch):
    cursor = MagicMock()
    cursor.fetchone.return_value = (0,)
    connection, close = _patch_db(monkeypatch, cursor)

    assert db.commit_exercise_db(2, 9, "revised answer") is True

    update_sql, update_params = cursor.execute.call_args_list[1].args
    assert "UPDATE practice_history" in update_sql
    assert update_params == ("revised answer", 2, 9)
    close.assert_called_once_with(connection, cursor)


def test_commit_exercise_db_03(monkeypatch):
    for check_value in (1, 2):
        cursor = MagicMock()
        cursor.fetchone.return_value = (check_value,)
        connection, close = _patch_db(monkeypatch, cursor)

        assert db.commit_exercise_db(2, 9, "late answer") is False
        assert cursor.execute.call_count == 1
        close.assert_called_once_with(connection, cursor)


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
        cursor = MagicMock()
        cursor.fetchone.return_value = row
        connection, close = _patch_db(monkeypatch, cursor)

        assert db.get_exercise_history_db(3, 11) == expected
        close.assert_called_once_with(connection, cursor)


def test_register_db_01(monkeypatch):
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    connection, close = _patch_db(monkeypatch, cursor)
    password_hash = MagicMock(return_value="hashed-password")
    monkeypatch.setattr(db, "generate_password_hash", password_hash)

    assert db.register_db("13800000000", "pw", "S", "Alice", "female") is True

    password_hash.assert_called_once_with("pw")
    insert_sql, insert_params = cursor.execute.call_args_list[1].args
    assert "INSERT INTO user" in insert_sql
    assert insert_params == (
        "13800000000",
        "hashed-password",
        "S",
        "Alice",
        "female",
    )
    close.assert_called_once_with(connection, cursor)


def test_f_getLearningStatsByChapter_01(monkeypatch):
    cursor = MagicMock()
    cursor.fetchone.side_effect = [("Chapter 1",), (0,), (0,), (0,)]
    connection, close = _patch_db(monkeypatch, cursor)

    result = db.f_getLearningStatsByChapter(3, student_id=10)

    assert result == {
        "name": "Chapter 1",
        "AiFrequence": 0.0,
        "correctness": 0,
        "sum_exercises": 0,
        "right_exercises": 0,
    }
    close.assert_called_once_with(connection, cursor)


def test_get_system_stats_db_01(monkeypatch):
    fake_redis = MagicMock()
    fake_redis.get.side_effect = RuntimeError("redis unavailable")
    monkeypatch.setattr(db, "redis_client", fake_redis)
    cursor = MagicMock()
    db_row = tuple(range(8))
    cursor.fetchone.return_value = db_row
    connection, close = _patch_db(monkeypatch, cursor)

    assert db.get_system_stats_db() == db_row
    assert "SELECT * FROM system_stats" in cursor.execute.call_args.args[0]
    close.assert_called_once_with(connection, cursor)


def test_increase_count_01(monkeypatch):
    fake_redis = MagicMock()
    fake_redis.incr.side_effect = RuntimeError("redis unavailable")
    monkeypatch.setattr(db, "redis_client", fake_redis)
    cursor = MagicMock()
    connection, close = _patch_db(monkeypatch, cursor)

    assert db.increase_count("generate_tasks") is True

    assert "`generate_tasks` = `generate_tasks` + 1" in cursor.execute.call_args.args[0]
    close.assert_called_once_with(connection, cursor)
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
