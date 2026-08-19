from fastapi.testclient import TestClient

import beecham
from serveur import app


def _mission(mid, statut):
    return {
        "id": mid,
        "consigne": f"mission {mid}",
        "statut": statut,
        "journal": '["developpeur \\u00b7 Write x.py"]',
        "cree_le": "2026-08-19T10:00:00",
        "maj_le": "2026-08-19T10:05:00",
    }


def test_vue_missions_actives_affiche_seulement_en_cours(monkeypatch):
    monkeypatch.setattr(
        beecham,
        "lister_missions",
        lambda chemin=None, limit=20: [
            _mission("m1", "en_cours"),
            _mission("m2", "valide"),
            _mission("m3", "rejete"),
        ],
    )
    r = TestClient(app).get("/vue/missions/actives")
    assert r.status_code == 200
    assert "m1" in r.text
    assert "mission m1" in r.text
    assert "m2" not in r.text
    assert "m3" not in r.text
