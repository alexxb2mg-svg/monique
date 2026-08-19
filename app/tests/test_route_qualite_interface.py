from fastapi.testclient import TestClient

from serveur import app


def test_vue_qualite():
    r = TestClient(app).get("/vue/qualite")
    assert r.status_code == 200
    assert "Qualité" in r.text


def test_vue_interface():
    r = TestClient(app).get("/vue/interface")
    assert r.status_code == 200
    assert "Interface" in r.text
