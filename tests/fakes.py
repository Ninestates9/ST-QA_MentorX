"""Reusable in-memory test doubles for database, Redis and HTTP tests."""


class FakeCursor:
    def __init__(self, *, fetchone_results=None, fetchall_results=None, execute_errors=None):
        self.fetchone_results = list(fetchone_results or [])
        self.fetchall_results = list(fetchall_results or [])
        self.execute_errors = dict(execute_errors or {})
        self.execute_calls = []
        self.closed = False

    def execute(self, sql, params=None):
        call_index = len(self.execute_calls)
        self.execute_calls.append((sql, params))
        error = self.execute_errors.get(call_index)
        if error is not None:
            raise error
        return 1

    def fetchone(self):
        return self.fetchone_results.pop(0) if self.fetchone_results else None

    def fetchall(self):
        return self.fetchall_results.pop(0) if self.fetchall_results else []

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor=None):
        self.fake_cursor = cursor or FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class FakeRedis:
    def __init__(self, values=None, *, error=None):
        self.values = dict(values or {})
        self.error = error
        self.get_calls = []
        self.set_calls = []
        self.incr_calls = []

    def _raise_if_needed(self):
        if self.error is not None:
            raise self.error

    def get(self, key):
        self._raise_if_needed()
        self.get_calls.append(key)
        return self.values.get(key)

    def set(self, key, value):
        self._raise_if_needed()
        self.set_calls.append((key, value))
        self.values[key] = value
        return True

    def incr(self, key):
        self._raise_if_needed()
        self.incr_calls.append(key)
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]


class FakeResponse:
    def __init__(self, *, lines=None, json_data=None, content=b"", status_code=200):
        self.lines = list(lines or [])
        self.json_data = json_data
        self.content = content
        self.status_code = status_code
        self.text = content.decode("utf-8", errors="replace")

    def iter_lines(self):
        for line in self.lines:
            yield line.encode("utf-8") if isinstance(line, str) else line

    def json(self):
        return self.json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

