from fastapi.testclient import TestClient

from serveur import app


def test_vue_fournisseurs_materiel():
    r = TestClient(app).get("/vue/fournisseurs-materiel")
    assert r.status_code == 200
    assert "Aucun fournisseur enregistré" in r.text
