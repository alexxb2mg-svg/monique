import entrepot
import overlays
import secretaire_actions as SA


def _db(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return db


def test_envoyer_staging_n_envoie_rien(tmp_path, monkeypatch):
    db = _db(tmp_path)
    overlays.enregistrer_brouillon(9, "gmail", "ctx", "Bonjour", [], [], db)
    r = SA.envoyer_staging(9, db)
    assert r["ok"] and r["envoye_reellement"] is False
    con = entrepot.connexion_ecriture(db)
    try:
        row = con.execute(
            "SELECT statut FROM secw_delivery_obligations WHERE id='d9'"
        ).fetchone()
    finally:
        con.close()
    assert row["statut"] == "pending"


def test_envoyer_sans_brouillon(tmp_path):
    db = _db(tmp_path)
    r = SA.envoyer_staging(42, db)
    assert r["ok"] is False and r["erreur"] == "aucun_brouillon"


def test_dispo_envoi_false_en_test(monkeypatch):
    monkeypatch.delenv("SECRETAIRE_MODE", raising=False)  # test par défaut
    assert SA.dispo_envoi() is False


def test_dispo_envoi_true_en_prod(monkeypatch):
    monkeypatch.setenv("SECRETAIRE_MODE", "prod")
    assert SA.dispo_envoi() is True


def test_action_envoyer_utilise_dispo_envoi_comme_check_fn(monkeypatch):
    # auto-contenu (indépendant de l'ordre d'exécution des autres tests / de l'état
    # du registre global) : revérifie le câblage réel copier/envoyer(check_fn=dispo_envoi).
    import actions

    monkeypatch.delenv("SECRETAIRE_MODE", raising=False)
    actions.registre.clear()
    actions.enregistrer(
        actions.Action("copier", "Copier le texte", handler=lambda **k: None)
    )
    actions.enregistrer(
        actions.Action(
            "envoyer", "Envoyer", handler=SA.envoyer_staging, check_fn=SA.dispo_envoi
        )
    )
    noms = [a.nom for a in actions.disponibles()]
    assert "copier" in noms and "envoyer" not in noms  # masqué en test

    monkeypatch.setenv("SECRETAIRE_MODE", "prod")
    noms_prod = [a.nom for a in actions.disponibles()]
    assert "envoyer" in noms_prod  # visible en prod
