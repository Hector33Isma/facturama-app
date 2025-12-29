from fastapi.testclient import TestClient

from app.main import app


def test_home_ok():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
