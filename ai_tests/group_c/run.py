import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="丙组 AI 测试独立入口，默认不调用服务")
    parser.add_argument("--run-ai", action="store_true")
    args, pytest_args = parser.parse_known_args()
    try:
        import pytest
    except ImportError:
        parser.error("请先安装 ai_tests/group_c/requirements-c.txt 中的依赖")
    previous = os.environ.get("GROUP_C_RUN_AI")
    os.environ["GROUP_C_RUN_AI"] = "1" if args.run_ai else "0"
    try:
        directory = str(Path(__file__).resolve().parent)
        return pytest.main(["--confcutdir", directory, directory, *pytest_args])
    finally:
        if previous is None:
            os.environ.pop("GROUP_C_RUN_AI", None)
        else:
            os.environ["GROUP_C_RUN_AI"] = previous


if __name__ == "__main__":
    raise SystemExit(main())
