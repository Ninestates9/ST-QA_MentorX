from unittest.mock import MagicMock

import sync_utils


def test_sync_redis_to_db_01(monkeypatch):
    values = {
        key: (None if index in {0, 5} else str(index))
        for index, key in enumerate(sync_utils.redis_keys)
    }
    fake_redis = MagicMock()
    fake_redis.get.side_effect = values.get
    monkeypatch.setattr(sync_utils, "redis_client", fake_redis)

    connection = MagicMock()
    cursor = MagicMock()
    close = MagicMock()
    monkeypatch.setattr(sync_utils, "connectSQL", lambda: (connection, cursor))
    monkeypatch.setattr(sync_utils, "closeSQL", close)

    sync_utils.sync_redis_to_db()

    sql, params = cursor.execute.call_args.args
    assert "UPDATE system_stats" in sql
    assert params == [0, 1, 2, 3, 4, 0, 6, 7]
    close.assert_called_once_with(connection, cursor)
