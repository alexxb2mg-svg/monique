from fastapi.testclient import TestClient

import cerveau
import entrepot
import overlays
import secretaire_actions as SA
import serveur


def _db(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return db


def test_reprendre_met_a_jour(tmp_path, monkeypatch):
    db = _db(tmp_path)
    overlays.enregistrer_brouillon(5, "gmail", "ctx", "Version 1", [], [], db)
    monkeypatch.setattr(
        cerveau,
        "appeler",
        lambda *a, **k: {
            "ok": True,
            "erreur": None,
            "usage": None,
            "texte": '{"brouillon":"Version 2 plus ferme","attendu":[],"hors":[]}',
        },
    )
    r = SA.reprendre_brouillon(5, "sois plus ferme", db)
    assert r["ok"] and "Version 2" in overlays.lire_brouillon(5, db)["brouillon"]


def test_reprendre_sans_brouillon_existant(tmp_path):
    db = _db(tmp_path)
    r = SA.reprendre_brouillon(999, "sois plus ferme", db)
    assert r["ok"] is False and r["erreur"] == "aucun_brouillon"


def test_reprendre_cerveau_ko(tmp_path, monkeypatch):
    db = _db(tmp_path)
    overlays.enregistrer_brouillon(6, "gmail", "ctx", "Version 1", [], [], db)
    monkeypatch.setattr(
        cerveau,
        "appeler",
        lambda *a, **k: {"ok": False, "texte": "", "erreur": "estop", "usage": None},
    )
    r = SA.reprendre_brouillon(6, "sois plus ferme", db)
    assert r["ok"] is False and r["erreur"] == "estop"


def test_route_parler_met_a_jour_le_fragment(monkeypatch):
    monkeypatch.setattr(
        SA, "reprendre_brouillon", lambda eid, consigne, chemin=None: {"ok": True}
    )
    import boite
    import overlays as ov

    monkeypatch.setattr(
        boite,
        "lire_boite",
        lambda **k: [
            {
                "id": 5,
                "source": "gmail",
                "apercu": "x",
                "timestamp": "…",
                "traite": False,
            }
        ],
    )
    monkeypatch.setattr(
        ov,
        "lire_brouillon",
        lambda eid, chemin=None: {
            "id": "b5",
            "brouillon": "Version 2 plus ferme",
            "contexte": "ctx",
            "attendu": [],
            "hors": [],
            "statut": "propose",
        },
    )
    r = TestClient(serveur.app).post(
        "/boite/5/parler", data={"consigne": "sois plus ferme"}
    )
    assert r.status_code == 200 and "Version 2" in r.text
