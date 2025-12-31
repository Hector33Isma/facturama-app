from fastapi.testclient import TestClient

from app.main import app


def test_login_page_ok():
    client = TestClient(app)
    resp = client.get("/login")
    assert resp.status_code == 200
