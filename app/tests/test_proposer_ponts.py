"""Vrais tests (écrits avant toute réponse du pont) pour proposer_ponts.proposer_a_alex."""

import os

import proposer_ponts


def test_ecrit_un_fichier_markdown_avec_le_resume(tmp_path):
    resultat = {
        "brique": "Comparateur de prix fournisseurs",
        "ok": True,
        "essais": 1,
        "chemin_module": r"C:\sandbox\brique_1.py",
        "chemin_test": r"C:\sandbox\test_brique_1.py",
        "dernier_test": "4 passed in 0.46s",
    }
    chemin = proposer_ponts.proposer_a_alex(resultat, str(tmp_path))

    assert os.path.exists(chemin)
    contenu = open(chemin, encoding="utf-8").read()
    assert "Comparateur de prix fournisseurs" in contenu
    assert "brique_1.py" in contenu
    assert "4 passed" in contenu


def test_nom_de_fichier_horodate_et_lisible(tmp_path):
    """Test durci après un vrai bug (2026-08-20) : le format d'horodatage avait un %Y en double
    (« 202620260820 ») — ce test trop permissif (juste .endswith('.md')) ne l'avait pas attrapé."""
    import re

    resultat = {"brique": "Test simple", "ok": False, "essais": 3, "dernier_test": "1 failed"}
    chemin = proposer_ponts.proposer_a_alex(resultat, str(tmp_path))

    nom = os.path.basename(chemin)
    assert nom.endswith(".md")
    assert "echec" in nom.lower()
    # Horodatage EXACT attendu : YYYYMMDD_HHMMSS (8 chiffres, underscore, 6 chiffres) -- pas de
    # motif dupliqué comme "202620260820".
    m = re.search(r"revue_(\d{8}_\d{6})_", nom)
    assert m, f"horodatage absent ou malformé dans {nom!r}"
    import time

    assert m.group(1).startswith(time.strftime("%Y%m%d"))


def test_dossier_absent_est_cree(tmp_path):
    dossier = str(tmp_path / "sous_dossier_inexistant")
    resultat = {"brique": "X", "ok": True, "essais": 1, "dernier_test": ""}

    chemin = proposer_ponts.proposer_a_alex(resultat, dossier)

    assert os.path.exists(chemin)
    assert os.path.exists(dossier)
