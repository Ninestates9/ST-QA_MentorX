from __future__ import annotations

import importlib
import json
import sys
import time
import types
from pathlib import Path

import pytest

from ai_tests.group_a.helpers_a import MODEL_NAME, append_jsonl, new_run_dir, sha256_text


class FakeConnection:
    pass


class FakeCursor:
    def __init__(self):
        self.chapter_content = ""
        self.fetchone_value = None
        self.inserts = []

    def execute(self, sql, params=None):
        normalized = " ".join(sql.lower().split())
        if normalized.startswith("select content from chapter"):
            self.fetchone_value = (self.chapter_content,)
        elif normalized.startswith("select max(session_id)"):
            self.fetchone_value = (0,)
        elif normalized.startswith("insert into exercise"):
            self.inserts.append({"sql": sql, "params": params})

    def fetchone(self):
        return self.fetchone_value


class GroupAEnvironment:
    def __init__(self, module, x1_http, cursor, evidence_path):
        self.module = module
        self.x1_http = x1_http
        self.cursor = cursor
        self.evidence_path = evidence_path
        self.calls = []

    def _real_get_answer(self, prompt):
        started = time.perf_counter()
        call = {"prompt": prompt, "prompt_sha256": sha256_text(prompt), "model": MODEL_NAME}
        try:
            response = self.x1_http.get_answer(prompt)
            call.update(
                raw_response=response,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                error_category=None,
            )
            self.calls.append(call)
            return response
        except Exception as exc:
            call.update(
                raw_response=None,
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                error_category=type(exc).__name__,
                error_message=str(exc),
            )
            self.calls.append(call)
            raise

    def chat(self, context, question):
        self.cursor.chapter_content = context
        before = len(self.calls)
        success, answer = self.module.ai_aichat(1001, 7001, question, -1)
        if not success:
            call = self.calls[-1] if len(self.calls) > before else {}
            raise RuntimeError(f"ai_aichat failed: {answer}; call={call}")
        return answer, self.calls[-1]

    def generate(self, context, question_type):
        self.cursor.chapter_content = context
        self.cursor.inserts.clear()
        before = len(self.calls)
        success = self.module.ai_generate_tasks(9001, 2, question_type)
        if not success:
            recent = self.calls[before:]
            raise RuntimeError(f"ai_generate_tasks failed; calls={recent}")
        params = self.cursor.inserts[-1]["params"]
        return params[0], params[1], self.calls[before:]

    def record(self, record):
        append_jsonl(self.evidence_path, record)


@pytest.fixture(scope="session")
def a_run_dir():
    path = new_run_dir()
    metadata = {
        "group": "A",
        "model_configured": MODEL_NAME,
        "service_model_identifier": "unavailable: X1_http.get_answer only returns message.content",
        "temperature": "service default (unknown)",
        "seed": "service default (unknown)",
    }
    (path / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@pytest.fixture()
def a_chat_env(monkeypatch, a_run_dir):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root))

    cursor = FakeCursor()
    database_stub = types.ModuleType("database_utils")
    database_stub.connectSQL = lambda: (FakeConnection(), cursor)
    database_stub.closeSQL = lambda conn, cur: None
    database_stub.commit_exercise_db = lambda *args, **kwargs: True
    database_stub.search_worst_chapter = lambda *args, **kwargs: 1
    database_stub.get_chapter_practice_history_db = lambda *args, **kwargs: []
    monkeypatch.setitem(sys.modules, "database_utils", database_stub)

    ocr_stub = types.ModuleType("ocr")
    ocr_stub.ocr = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("OCR is outside group A scope")
    )
    monkeypatch.setitem(sys.modules, "ocr", ocr_stub)

    langchain_stub = types.ModuleType("langchain")
    langchain_stub.__path__ = []
    community_stub = types.ModuleType("langchain_community")
    community_stub.__path__ = []
    vectorstores_stub = types.ModuleType("langchain.vectorstores")
    community_embeddings_stub = types.ModuleType("langchain_community.embeddings")

    class ForbiddenFAISS:
        @classmethod
        def load_local(cls, *args, **kwargs):
            return cls()

        def similarity_search(self, *args, **kwargs):
            raise AssertionError("RAG similarity_search is outside this test scope")

    class NoDownloadEmbeddings:
        def __init__(self, *args, **kwargs):
            pass

    vectorstores_stub.FAISS = ForbiddenFAISS
    community_embeddings_stub.HuggingFaceEmbeddings = NoDownloadEmbeddings
    langchain_stub.vectorstores = vectorstores_stub
    community_stub.embeddings = community_embeddings_stub
    monkeypatch.setitem(sys.modules, "langchain", langchain_stub)
    monkeypatch.setitem(sys.modules, "langchain_community", community_stub)
    monkeypatch.setitem(sys.modules, "langchain.vectorstores", vectorstores_stub)
    monkeypatch.setitem(sys.modules, "langchain_community.embeddings", community_embeddings_stub)

    sys.modules.pop("ai_model", None)
    x1_http = importlib.import_module("X1_http")
    module = importlib.import_module("ai_model")
    environment = GroupAEnvironment(module, x1_http, cursor, a_run_dir / "results.jsonl")
    monkeypatch.setattr(module, "get_answer", environment._real_get_answer)
    yield environment
    sys.modules.pop("ai_model", None)
