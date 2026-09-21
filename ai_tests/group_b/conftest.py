"""乙组局部 fixture。

根 ai_tests/conftest.py 负责提供 --run-ai；本文件只提供乙组自己的模型导入、
数据库隔离和运行证据 fixture，不定义公共命令行选项。
"""

from __future__ import annotations

import importlib
import json
import sys
import types
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from .helpers_b import GradeHarness, serializable_run, verify_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _run_ai_enabled(config: pytest.Config) -> bool:
    try:
        return bool(config.getoption("--run-ai", default=False))
    except (AttributeError, ValueError):
        return False


def _import_ai_module_without_embedding_download() -> tuple[Any, dict[str, Any]]:
    """导入真实 ai_model，但阻止未覆盖的 FAISS/Embedding 初始化。"""

    module_names = (
        "langchain",
        "langchain.vectorstores",
        "langchain_community",
        "langchain_community.embeddings",
        "ai_model",
    )
    previous: dict[str, Any] = {
        name: sys.modules.get(name) for name in module_names
    }

    fake_langchain = types.ModuleType("langchain")
    fake_langchain.__path__ = []
    fake_vectorstores = types.ModuleType("langchain.vectorstores")
    fake_community = types.ModuleType("langchain_community")
    fake_community.__path__ = []
    fake_embeddings = types.ModuleType("langchain_community.embeddings")

    class DisabledFAISS:
        @classmethod
        def load_local(cls, *args: Any, **kwargs: Any) -> "DisabledFAISS":
            return cls()

        def similarity_search(self, *args: Any, **kwargs: Any) -> Any:
            raise AssertionError("乙组不应进入 FAISS 检索链路")

    class DisabledEmbeddings:
        def __init__(self, *args: Any, **kwargs: Any):
            pass

    fake_vectorstores.FAISS = DisabledFAISS
    fake_embeddings.HuggingFaceEmbeddings = DisabledEmbeddings
    sys.modules.update(
        {
            "langchain": fake_langchain,
            "langchain.vectorstores": fake_vectorstores,
            "langchain_community": fake_community,
            "langchain_community.embeddings": fake_embeddings,
        }
    )
    sys.modules.pop("ai_model", None)
    try:
        return importlib.import_module("ai_model"), previous
    except Exception:
        for name, original in previous.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        raise


@pytest.fixture(scope="session")
def ai_module(pytestconfig: pytest.Config):
    if not _run_ai_enabled(pytestconfig):
        pytest.skip("AI 测试默认关闭；请由根 ai_tests 入口传入 --run-ai")

    verify_snapshot(PROJECT_ROOT)
    module, previous = _import_ai_module_without_embedding_download()
    yield module

    sys.modules.pop("ai_model", None)
    for name, original in previous.items():
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original


@pytest.fixture()
def grade_harness(ai_module: Any, monkeypatch: pytest.MonkeyPatch) -> GradeHarness:
    return GradeHarness(ai_module, monkeypatch)


@pytest.fixture(scope="session")
def artifact_recorder(pytestconfig: pytest.Config):
    if not _run_ai_enabled(pytestconfig):
        yield lambda *args, **kwargs: None
        return

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
    artifact_dir = Path(__file__).with_name("artifacts") / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    result_path = artifact_dir / "results.jsonl"

    def record(
        case_id: str,
        variant: str,
        round_no: int,
        expected_score: str,
        run: Any,
    ) -> None:
        payload = serializable_run(
            case_id, variant, round_no, expected_score, run
        )
        payload["run_id"] = run_id
        with result_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

    yield record
