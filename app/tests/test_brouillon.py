import cerveau
import entrepot
import overlays
import secretaire_actions as SA


def _db(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return db


def test_amorcer_stocke_brouillon(tmp_path, monkeypatch):
    db = _db(tmp_path)
    faux = (
        '{"brouillon":"Bonjour, bien reçu.","attendu":["valider"],"hors":["le prix"]}'
    )
    monkeypatch.setattr(
        cerveau,
        "appeler",
        lambda *a, **k: {"ok": True, "texte": faux, "erreur": None, "usage": None},
    )
    r = SA.amorcer_brouillon(7, "Question sur le devis", "gmail", db)
    assert r["brouillon"].startswith("Bonjour")
    b = overlays.lire_brouillon(7, db)
    assert b and b["attendu"] == ["valider"] and b["hors"] == ["le prix"]


def test_amorcer_cerveau_ko(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(
        cerveau,
        "appeler",
        lambda *a, **k: {"ok": False, "texte": "", "erreur": "estop", "usage": None},
    )
    r = SA.amorcer_brouillon(8, "x", "gmail", db)
    assert r["ok"] is False
