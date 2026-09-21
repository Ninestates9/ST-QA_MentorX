"""乙组专用测试替身、批改执行器和结果检查工具。

这里不替换模型输出。真实运行时，GradeHarness 会调用 ai_model 中导入的
真实 get_answer，并只记录 prompt 和原始返回值；数据库则使用内存 Fake。
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


DATA_PATH = Path(__file__).with_name("data") / "q09_snapshot.json"
CASE_DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))
QUESTION = CASE_DATA["question"]
REFERENCE_ANSWER = CASE_DATA["reference_answer"]
STUDENT_ANSWERS = CASE_DATA["student_answers"]

STUDENT_ID = 9001
EXERCISE_ID = 9009


class FakeCursor:
    """提供 ai_check_answer 所需的两次查询，并记录最终 UPDATE。"""

    def __init__(self, student_answer: str):
        self.student_answer = student_answer
        self._fetchone_results = deque(
            [(QUESTION, REFERENCE_ANSWER), (student_answer,)]
        )
        self.executions: list[tuple[str, Any]] = []
        self.closed = False

    def execute(self, sql: str, params: Any = None) -> int:
        self.executions.append((sql, params))
        return 1

    def fetchone(self) -> Any:
        if not self._fetchone_results:
            raise AssertionError("FakeCursor 没有预设更多 fetchone 结果")
        return self._fetchone_results.popleft()

    def close(self) -> None:
        self.closed = True

    @property
    def update_executions(self) -> list[tuple[str, Any]]:
        return [
            (sql, params)
            for sql, params in self.executions
            if "UPDATE practice_history" in sql
        ]


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeDatabase:
    def __init__(self, student_answer: str):
        self.cursor = FakeCursor(student_answer)
        self.connection = FakeConnection()
        self.connect_calls = 0

    def connect(self) -> tuple[FakeConnection, FakeCursor]:
        self.connect_calls += 1
        return self.connection, self.cursor


class RecordingModel:
    """记录真实模型调用，不改变模型返回值。"""

    def __init__(self, real_get_answer: Callable[[str], Any]):
        self._real_get_answer = real_get_answer
        self.prompts: list[str] = []
        self.outputs: list[Any] = []
        self.latencies_ms: list[float] = []
        self.errors: list[str] = []

    def __call__(self, prompt: str) -> Any:
        self.prompts.append(prompt)
        started = time.perf_counter()
        try:
            output = self._real_get_answer(prompt)
            self.outputs.append(output)
            return output
        except Exception as exc:
            self.errors.append(f"{type(exc).__name__}: {exc}")
            raise
        finally:
            self.latencies_ms.append((time.perf_counter() - started) * 1000)


@dataclass
class GradeRun:
    result: tuple[bool, Any]
    database: FakeDatabase
    model: RecordingModel
    started_at: str
    elapsed_ms: float

    @property
    def raw_score(self) -> Any:
        return self.model.outputs[0] if self.model.outputs else None

    @property
    def analysis(self) -> Any:
        return self.model.outputs[1] if len(self.model.outputs) > 1 else None


class GradeHarness:
    """每次调用建立全新的 Fake DB 和模型记录器，防止样本互相污染。"""

    def __init__(self, ai_module: Any, monkeypatch: Any):
        self.ai_module = ai_module
        self.monkeypatch = monkeypatch
        self.real_get_answer = ai_module.get_answer

    def run(self, student_answer: str) -> GradeRun:
        database = FakeDatabase(student_answer)
        model = RecordingModel(self.real_get_answer)
        self.monkeypatch.setattr(self.ai_module, "connectSQL", database.connect)
        self.monkeypatch.setattr(self.ai_module, "get_answer", model)
        started_at = datetime.now(timezone.utc).isoformat()
        started = time.perf_counter()
        result = self.ai_module.ai_check_answer(EXERCISE_ID, STUDENT_ID)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return GradeRun(
            result=result,
            database=database,
            model=model,
            started_at=started_at,
            elapsed_ms=elapsed_ms,
        )


def normalize_score(raw_score: Any) -> str | None:
    """只接受完整的单字符标签；保留 raw_score 供证据记录。"""

    if not isinstance(raw_score, str):
        return None
    return raw_score if re.fullmatch(r"[012]", raw_score) else None


def assert_prompt_contract(run: GradeRun, student_answer: str) -> None:
    assert len(run.model.prompts) == 2, "批改必须先评分，再生成分析"
    for prompt in run.model.prompts:
        assert QUESTION in prompt
        assert REFERENCE_ANSWER in prompt
        assert student_answer in prompt


def assert_database_write(run: GradeRun) -> None:
    assert run.database.connect_calls == 1
    assert len(run.database.cursor.update_executions) == 1
    _, params = run.database.cursor.update_executions[0]
    assert params == (run.analysis, run.raw_score, STUDENT_ID, EXERCISE_ID)
    assert run.database.cursor.closed is True
    assert run.database.connection.closed is True


def assert_analysis_contains_groups(
    analysis: Any, required_groups: tuple[tuple[str, ...], ...]
) -> None:
    assert isinstance(analysis, str)
    normalized = analysis.casefold()
    for alternatives in required_groups:
        assert any(term.casefold() in normalized for term in alternatives), (
            f"批改分析未覆盖预期纠错点之一：{alternatives!r}"
        )


def _redact(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    value = re.sub(r"Bearer\s+[A-Za-z0-9._:-]+", "Bearer [REDACTED]", value)
    return re.sub(
        r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+", r"\1[REDACTED]", value
    )


def _git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            check=True,
            text=True,
        )
        return completed.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _model_config(real_get_answer: Callable[[str], Any]) -> dict[str, Any]:
    config: dict[str, Any] = {
        "callable_module": getattr(real_get_answer, "__module__", None),
        "temperature": "service default (unknown)",
        "seed": "unsupported/unknown",
    }
    module = inspect.getmodule(real_get_answer)
    if module is not None:
        config["endpoint"] = getattr(module, "URL", getattr(module, "url", None))
    try:
        source = inspect.getsource(real_get_answer)
        match = re.search(
            r'''["']model["']\s*:\s*["']([^"']+)''', source
        )
        config["model"] = match.group(1) if match else "unknown"
    except (OSError, TypeError):
        config["model"] = "unknown"
    config["service_model_identifier"] = (
        "unavailable: current get_answer wrapper returns content only"
    )
    return config


def serializable_run(
    case_id: str,
    variant: str,
    round_no: int,
    expected_score: str,
    run: GradeRun,
) -> dict[str, Any]:
    """生成不包含认证头的运行证据，供 group_b artifacts 使用。"""

    return {
        "group": "B",
        "case_id": case_id,
        "variant": variant,
        "round": round_no,
        "source_file": CASE_DATA["source_file"],
        "source_sha256": CASE_DATA["source_sha256"],
        "paragraph_range": CASE_DATA["paragraph_range"],
        "excerpt_sha256": CASE_DATA["excerpt_sha256"],
        "student_answer": run.database.cursor.student_answer,
        "result": list(run.result),
        "prompts": [_redact(prompt) for prompt in run.model.prompts],
        "prompt_sha256": [
            hashlib.sha256(prompt.encode("utf-8")).hexdigest().upper()
            for prompt in run.model.prompts
        ],
        "raw_responses": [_redact(output) for output in run.model.outputs],
        "raw_score": _redact(run.raw_score),
        "normalized_score": normalize_score(run.raw_score),
        "expected_score": expected_score,
        "rule_score": normalize_score(run.raw_score) == expected_score,
        "analysis": _redact(run.analysis),
        "analysis_rule_flags": {
            "mentions_out": isinstance(run.analysis, str)
            and "out" in run.analysis.casefold(),
            "mentions_low_level": isinstance(run.analysis, str)
            and (
                "low" in run.analysis.casefold()
                or "低电平" in run.analysis
            ),
        },
        "automatic_status": (
            "ERROR"
            if run.model.errors or run.result[0] is not True
            else "PASS"
            if normalize_score(run.raw_score) == expected_score
            and isinstance(run.analysis, str)
            and bool(run.analysis.strip())
            else "FAIL"
        ),
        "human_status": "REVIEW",
        "human_reason": "待人工复核分析是否正确、矛盾或带有偏见",
        "started_at": run.started_at,
        "elapsed_ms": round(run.elapsed_ms, 3),
        "model_call_latencies_ms": [
            round(value, 3) for value in run.model.latencies_ms
        ],
        "error_category": (
            "MODEL_OR_TRANSPORT_ERROR"
            if run.model.errors
            else "APPLICATION_ERROR"
            if run.result[0] is not True
            else None
        ),
        "errors": [_redact(error) for error in run.model.errors],
        "model_config": _model_config(run.model._real_get_answer),
        "code_commit": _git_commit(),
        "executions": [
            {"sql": sql, "params": params}
            for sql, params in run.database.cursor.executions
        ],
    }


def verify_snapshot(project_root: Path) -> None:
    source_path = project_root / CASE_DATA["source_file"]
    actual_source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest().upper()
    assert actual_source_hash == CASE_DATA["source_sha256"], (
        "cp09.docx 已变化，请重新核对 P473-P486 后更新乙组快照"
    )
    actual_excerpt_hash = hashlib.sha256(
        CASE_DATA["excerpt"].encode("utf-8")
    ).hexdigest().upper()
    assert actual_excerpt_hash == CASE_DATA["excerpt_sha256"], (
        "乙组测试片段已变化，请重新进行人工审核"
    )
