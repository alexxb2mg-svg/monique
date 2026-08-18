import entrepot
import cerveau
import estop


def _db(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return db


PROF = cerveau.ProviderProfile(nom="claude", mode="claude_cli", model="sonnet")


def test_appel_claude_cli_compte_usage(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(estop, "engage", lambda: False)
    monkeypatch.setattr(
        cerveau,
        "_lancer_claude_cli",
        lambda prompt, system, prof: {
            "texte": "Bonjour",
            "input_tokens": 12,
            "output_tokens": 3,
        },
    )
    r = cerveau.appeler("secretaire", "salut", PROF, "brouillon", chemin=db)
    assert r["ok"] and r["texte"] == "Bonjour"
    con = entrepot.connexion_ecriture(db)
    try:
        c = con.execute(
            "SELECT calls, input_tokens FROM secw_model_usage WHERE agent='secretaire'"
        ).fetchone()
    finally:
        con.close()
    assert c["calls"] == 1 and c["input_tokens"] == 12


def test_estop_bloque(tmp_path, monkeypatch):
    db = _db(tmp_path)
    monkeypatch.setattr(estop, "engage", lambda: True)
    r = cerveau.appeler("secretaire", "salut", PROF, "brouillon", chemin=db)
    assert r["ok"] is False and r["erreur"] == "estop"


def test_classifier_erreur():
    assert cerveau.classifier_erreur("HTTP 429 rate limit exceeded") == "rate_limit"
    assert cerveau.classifier_erreur("overloaded_error 529") == "overloaded"
    assert cerveau.classifier_erreur("tout va bien") == "ok"


def test_spillover_tronque(tmp_path, monkeypatch):
    monkeypatch.setattr(
        cerveau, "SPILL_DIR", tmp_path / "spill"
    )  # pas de résidu dans le coffre
    gros = "x" * 20000
    # NOTE déviation plan : seuil abaissé (le plan disait 8000 tout en asseyant len<500,
    # impossible puisque spillover renvoie propre[:seuil] ; l'implémentation sécurité reste EXACTE).
    ap = cerveau.spillover(gros, seuil=200)
    assert "spillover/" in ap and len(ap) < 500
    assert (tmp_path / "spill").exists()
