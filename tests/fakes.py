"""Small in-memory test doubles for database unit tests."""

from collections import deque


class FakeCursor:
    def __init__(self, fetchone_results=(), execute_effects=()):
        self._fetchone_results = deque(fetchone_results)
        self._execute_effects = deque(execute_effects)
        self.executions = []
        self.closed = False

    def execute(self, sql, params=None):
        self.executions.append((sql, params))
        if self._execute_effects:
            effect = self._execute_effects.popleft()
            if isinstance(effect, BaseException):
                raise effect
        return 1

    def fetchone(self):
        if not self._fetchone_results:
            raise AssertionError("No configured fetchone result remains")
        return self._fetchone_results.popleft()

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True
