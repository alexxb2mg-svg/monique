from fastapi.testclient import TestClient
from serveur import app


def test_sante_ok():
    c = TestClient(app)
    r = c.get("/sante")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
