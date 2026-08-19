from fastapi.testclient import TestClient

import vue_usage
from serveur import app


def test_vue_usage_affiche_les_agents(monkeypatch):
    monkeypatch.setattr(
        vue_usage,
        "contexte_usage",
        lambda chemin=None: [
            {
                "agent": "secretaire",
                "input_tokens": 120,
                "output_tokens": 60,
                "calls": 2,
                "estimated_cost_usd": 0.0006,
                "cost_status": "included",
            }
        ],
    )
    r = TestClient(app).get("/vue/usage")
    assert r.status_code == 200
    assert "secretaire" in r.text
    assert "included" in r.text


def test_vue_usage_vide(monkeypatch):
    monkeypatch.setattr(vue_usage, "contexte_usage", lambda chemin=None: [])
    r = TestClient(app).get("/vue/usage")
    assert r.status_code == 200
    assert "Aucun usage enregistré" in r.text
