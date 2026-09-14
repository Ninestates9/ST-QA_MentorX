"""Shared fixtures that keep route tests independent of local AI services."""

import importlib
import sys
import types
from pathlib import Path

import pytest
from flask_jwt_extended import create_access_token


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TEST_STUDENT_ID = 1001


def _unconfigured_ai_call(*args, **kwargs):
    raise AssertionError("AI/PPT dependency was not replaced by this test")


def _install_import_stubs():
    ai_model = types.ModuleType("ai_model")
    for name in (
        "ai_aichat",
        "ai_generate_tasks",
        "ai_generate_daily_tasks",
        "ai_check_answer",
        "ai_generate_teachcontent",
        "ai_generate_suggestion",
        "ai_img2word",
    ):
        setattr(ai_model, name, _unconfigured_ai_call)
    sys.modules["ai_model"] = ai_model

    ai_ppt = types.ModuleType("aiPPT")
    ai_ppt.ai_generate_ppt = _unconfigured_ai_call
    sys.modules["aiPPT"] = ai_ppt


_install_import_stubs()


@pytest.fixture(scope="session")
def app_module():
    module = importlib.import_module("main")
    module.app.config.update(
        TESTING=True,
        JWT_SECRET_KEY="mentorx-test-only-secret",
        PROPAGATE_EXCEPTIONS=False,
    )
    return module


@pytest.fixture()
def client(app_module):
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def student_id():
    return TEST_STUDENT_ID


@pytest.fixture()
def auth_headers(app_module, student_id):
    with app_module.app.app_context():
        token = create_access_token(identity=str(student_id))
    return {"Authorization": f"Bearer {token}"}
