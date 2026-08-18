import cerveau
import entrepot
import roles
import orchestrateur as O


def _db(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return db


def test_suggestion_au_seuil(tmp_path):
    db = _db(tmp_path)
    for _ in range(5):
        O.noter_non_route(
            "facture_fournisseur", "un mail de facture", seuil=5, chemin=db
        )
    s = O.suggerer(db)
    assert any(x["signature"] == "facture_fournisseur" for x in s)


def test_sous_le_seuil_pas_de_suggestion(tmp_path):
    db = _db(tmp_path)
    O.noter_non_route("x", seuil=5, chemin=db)
    assert O.suggerer(db) == []


def test_router_repli_incremente_suggestions(
    tmp_path, monkeypatch
):  # revue B2 : bout-en-bout
    db = _db(tmp_path)
    monkeypatch.setattr(
        roles,
        "carte_agents",
        lambda: {"secretaire": {"triggers": [], "description": "x"}},
    )
    monkeypatch.setattr(
        cerveau,
        "appeler",
        lambda *a, **k: {
            "ok": True,
            "texte": "aucun agent",
            "erreur": None,
            "usage": None,
        },
    )
    for _ in range(5):  # même motif => même signature => compteur monte
        O.router(
            {"source": "cli", "contenu": "gérer une facture fournisseur EDF"}, chemin=db
        )
    assert len(O.suggerer(db)) >= 1
