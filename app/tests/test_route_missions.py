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


def test_missions_actives_filtre_en_cours(monkeypatch):
    monkeypatch.setattr(
        beecham,
        "lister_missions",
        lambda chemin=None, limit=20: [
            _mission("m1", "en_cours"),
            _mission("m2", "valide"),
            _mission("m3", "en_cours"),
        ],
    )
    r = TestClient(app).get("/missions/actives")
    assert r.status_code == 200
    data = r.json()
    ids = [m["id"] for m in data]
    assert ids == ["m1", "m3"]
    assert all(m["statut"] == "en_cours" for m in data)
    assert "journal_liste" in data[0]
