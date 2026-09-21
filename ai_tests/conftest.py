import os

import pytest

try:
    from dotenv import load_dotenv
except ImportError:  # collection must still work before optional AI deps are installed
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


def pytest_addoption(parser):
    parser.addoption(
        "--run-ai",
        action="store_true",
        default=False,
        help="run tests that make real, billable AI API requests",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "ai: real external AI application test")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-ai"):
        skip = pytest.mark.skip(reason="真实 AI 测试未启用；请显式传入 --run-ai")
        for item in items:
            if "ai" in item.keywords:
                item.add_marker(skip)
        return

    if not os.getenv("XFYUN_LLM_API_KEY"):
        skip = pytest.mark.skip(
            reason="缺少 XFYUN_LLM_API_KEY；请在项目 .env 或环境变量中配置"
        )
        for item in items:
            if "ai" in item.keywords:
                item.add_marker(skip)
