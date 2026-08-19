from fastapi.testclient import TestClient

from serveur import app


def test_vue_missions_actives():
    r = TestClient(app).get("/vue/missions-actives")
    assert r.status_code == 200
    assert "Aucune mission en cours" in r.text
