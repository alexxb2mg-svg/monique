from fastapi.testclient import TestClient

import brief
import relances
import store
from serveur import app


def test_page_coquille(monkeypatch):
    monkeypatch.setattr(
        brief,
        "construire",
        lambda chemin=None: {
            "mails_a_traiter": 3,
            "relances": 2,
            "taches_retard": 1,
            "phrase": "Ce matin, 3...",
        },
    )
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "Aujourd" in r.text and "onglet" in r.text.lower()


def test_vue_faire(monkeypatch):
    monkeypatch.setattr(
        store,
        "lire_taches",
        lambda kind, chemin=None: [
            {"titre": "Rappeler Consuel", "echeance": "2026-08-14", "statut": "a_faire"}
        ],
    )
    r = TestClient(app).get("/vue/faire")
    assert r.status_code == 200 and "Rappeler Consuel" in r.text


def test_vue_relances(monkeypatch):
    monkeypatch.setattr(
        relances,
        "etat",
        lambda: {
            "disponible": True,
            "devis": [{"ref": "D26070009", "montant": 4120}],
            "factures": [],
            "message": "ok",
        },
    )
    r = TestClient(app).get("/vue/relances")
    assert r.status_code == 200 and "D26070009" in r.text
