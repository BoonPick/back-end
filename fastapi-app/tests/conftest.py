import sys
import os
import pytest

# fastapi-app 디렉토리를 import 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
