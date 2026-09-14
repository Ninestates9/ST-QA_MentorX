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
