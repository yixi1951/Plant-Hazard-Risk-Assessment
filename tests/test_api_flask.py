"""Flask 路由轻量测试（无需启动独立进程）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest

pytest.importorskip("flask")

from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


def test_api_diseases_json(client):
    r = client.get("/api/diseases")
    assert r.status_code == 200
    data = r.get_json()
    assert data is not None
    assert "diseases" in data or isinstance(data, list) or "total" in str(data).lower()


def test_about_page(client):
    r = client.get("/about")
    assert r.status_code == 200
    assert "关于" in r.get_data(as_text=True)