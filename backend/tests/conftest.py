import os
import pathlib
import tempfile
import uuid

TEST_DB = pathlib.Path(tempfile.gettempdir()) / f"ivi-test-{uuid.uuid4().hex[:8]}.db"

# 必须在导入 app 之前设好，config 是模块级单例
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["SEED_ON_STARTUP"] = "true"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["AUTOMATION_TOKEN"] = "test-token"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    # 会话级：整个测试跑在同一个临时库上，种子只灌一次
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin_token(client) -> str:
    r = client.post("/api/v1/auth/login", json={"email": "admin@ivi-test.com", "password": "Admin@12345"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def qa_token(client) -> str:
    r = client.post("/api/v1/auth/login", json={"email": "qa@ivi-test.com", "password": "Qa@12345"})
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def viewer_token(client) -> str:
    r = client.post("/api/v1/auth/login", json={"email": "viewer@ivi-test.com", "password": "Viewer@12345"})
    return r.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
