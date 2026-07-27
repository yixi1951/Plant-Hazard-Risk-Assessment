"""Flask 路由轻量测试（无需启动独立进程）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest

pytest.importorskip("flask")

import importlib.util


@pytest.fixture
def client():
    # app.py 和 app/ 包同名，使用 importlib 显式加载文件
    spec = importlib.util.spec_from_file_location(
        "app_module", os.path.join(ROOT, "app.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.app.config["TESTING"] = True
    with mod.app.test_client() as c:
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