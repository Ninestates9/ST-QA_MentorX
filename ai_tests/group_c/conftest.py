import os

import pytest

from .helpers_c import (
    PROJECT_ROOT,
    Harness,
    InfrastructureError,
    Recorder,
    create_images,
    isolated_modules,
    load_materials,
)


def pytest_configure(config):
    config.addinivalue_line("markers", "ai: explicitly enabled real AI service tests")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    recorder = getattr(config, "_group_c_recorder", None)
    if recorder is not None:
        terminalreporter.write_sep("=", "Group C AI evidence")
        terminalreporter.write_line(str(recorder.directory))
        for result in recorder.summaries:
            terminalreporter.write_line(f"{result['case_id']}: {result['status']}")
        terminalreporter.write_line("REVIEW means executed but awaiting human review, not a final PASS.")


@pytest.fixture(scope="session")
def c_enabled(pytestconfig):
    enabled = pytestconfig.getoption("--run-ai", default=False) or os.getenv("GROUP_C_RUN_AI") == "1"
    if not enabled:
        pytest.skip("未启用真实 AI 调用；使用 python -m ai_tests.group_c.run --run-ai -v")
    return True


@pytest.fixture(scope="session")
def c_session(c_enabled, pytestconfig):
    try:
        from dotenv import dotenv_values
    except ImportError as exc:
        raise InfrastructureError("请先安装 ai_tests/group_c/requirements-c.txt") from exc
    data, sources = load_materials()
    values = dotenv_values(PROJECT_ROOT / ".env")
    keys = {
        name: os.environ.get(name) or values.get(name) or ""
        for name in ("XFYUN_LLM_API_KEY", "XFYUN_OCR_API_KEY")
    }
    secrets = [value for value in keys.values() if value]
    secrets += [value.removeprefix("Bearer ") for value in secrets]
    recorder = Recorder(data, sources, secrets)
    pytestconfig._group_c_recorder = recorder
    return data, sources, keys, recorder


@pytest.fixture
def c_harness(c_session, monkeypatch):
    import requests

    data, sources, keys, recorder = c_session
    with monkeypatch.context() as patch:
        for name, value in keys.items():
            if value:
                patch.setenv(name, value)
        app, llm, ocr_module = isolated_modules(patch)
        harness = Harness(patch, app, llm, ocr_module, data, sources, recorder)
        real_request = requests.sessions.Session.request

        def request(session, method, url, **kwargs):
            return harness.request(real_request, session, method, url, **kwargs)

        patch.setattr(requests.sessions.Session, "request", request)
        patch.setattr(app, "get_answer", harness.get_answer)
        yield harness


@pytest.fixture
def c_llm(c_harness):
    if not os.getenv("XFYUN_LLM_API_KEY"):
        raise InfrastructureError("缺少 XFYUN_LLM_API_KEY；请在本机 .env 或环境变量中配置")
    return c_harness


@pytest.fixture
def c_ocr(c_harness):
    if not os.getenv("XFYUN_OCR_API_KEY"):
        raise InfrastructureError("缺少 XFYUN_OCR_API_KEY；请在本机 .env 或环境变量中配置")
    return c_harness


@pytest.fixture(scope="session")
def c_images(c_session):
    data, sources, keys, recorder = c_session
    paths, metadata = create_images(recorder.directory / "images", data)
    recorder.write("images.json", metadata)
    return paths
