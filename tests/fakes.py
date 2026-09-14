"""Reusable in-memory test doubles for database, Redis and HTTP tests."""

from collections import deque


class FakeCursor:
    def __init__(
        self,
        fetchone_results=(),
        execute_effects=(),
        *,
        fetchall_results=(),
        execute_errors=None,
    ):
        self._fetchone_results = deque(fetchone_results)
        self._fetchall_results = deque(fetchall_results)
        self._execute_effects = deque(execute_effects)
        self._execute_errors = dict(execute_errors or {})
        self.executions = []
        self.execute_calls = self.executions
        self.closed = False

    def execute(self, sql, params=None):
        call_index = len(self.executions)
        self.executions.append((sql, params))
        if call_index in self._execute_errors:
            raise self._execute_errors[call_index]
        if self._execute_effects:
            effect = self._execute_effects.popleft()
            if isinstance(effect, BaseException):
                raise effect
        return 1

    def fetchone(self):
        if not self._fetchone_results:
            raise AssertionError("No configured fetchone result remains")
        return self._fetchone_results.popleft()

    def fetchall(self):
        return self._fetchall_results.popleft() if self._fetchall_results else []

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

