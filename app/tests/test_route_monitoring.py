from fastapi.testclient import TestClient

import monitoring
from serveur import app


def _etat(tables_manquantes):
    return {
        "collecte_active": False,
        "dernier_passage": None,
        "entrees_jour": 0,
        "a_traiter": 0,
        "tables_manquantes": tables_manquantes,
    }


def test_vue_monitoring_signale_tables_manquantes(monkeypatch):
    monkeypatch.setattr(monitoring, "etat_moteur", lambda: _etat(["evenements_entrants"]))
    r = TestClient(app).get("/vue/monitoring")
    assert r.status_code == 200
    assert "evenements_entrants" in r.text
    assert "introuvable" in r.text


def test_vue_monitoring_sans_tables_manquantes_pas_dalerte(monkeypatch):
    monkeypatch.setattr(monitoring, "etat_moteur", lambda: _etat([]))
    r = TestClient(app).get("/vue/monitoring")
    assert r.status_code == 200
    assert "introuvable" not in r.text
