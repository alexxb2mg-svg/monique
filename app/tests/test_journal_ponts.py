"""Tests déterministes de journal_ponts (enregistrer_appel/resume) — fichier temporaire, zéro
dépendance au vrai journal de l'atelier."""

import journal_ponts


def test_enregistrer_puis_resume(tmp_path):
    chemin = str(tmp_path / "journal.jsonl")
    journal_ponts.enregistrer_appel("deepseek", "developpeur", True, 100, 200, chemin=chemin)
    journal_ponts.enregistrer_appel("deepseek", "controleur", False, 50, 0, chemin=chemin)
    journal_ponts.enregistrer_appel("gemini", "developpeur", True, 300, 400, chemin=chemin)

    r = journal_ponts.resume(chemin)

    assert r["par_pont"]["deepseek"]["appels"] == 2
    assert r["par_pont"]["deepseek"]["ok"] == 1
    assert r["par_pont"]["deepseek"]["ko"] == 1
    assert r["par_pont"]["gemini"]["appels"] == 1
    assert r["total_tokens_entree"] == round(100 / 4) + round(50 / 4) + round(300 / 4)
    assert r["total_tokens_sortie"] == round(200 / 4) + 0 + round(400 / 4)


def test_resume_fichier_absent_renvoie_vide(tmp_path):
    r = journal_ponts.resume(str(tmp_path / "inexistant.jsonl"))
    assert r == {"par_pont": {}, "total_tokens_entree": 0, "total_tokens_sortie": 0}


def test_resume_ligne_corrompue_est_ignoree(tmp_path):
    chemin = tmp_path / "journal.jsonl"
    chemin.write_text('{"pont": "deepseek", "ok": true, "tokens_entree_estimes": 10, "tokens_sortie_estimes": 20}\nCECI N EST PAS DU JSON\n\n', encoding="utf-8")

    r = journal_ponts.resume(str(chemin))

    assert r["par_pont"]["deepseek"]["appels"] == 1  # la ligne corrompue n'a pas fait planter


def test_enregistrer_appel_echec_ecriture_ne_leve_pas():
    """Fail-soft : un chemin invalide (ex. dossier inexistant sans permission) ne doit jamais lever."""
    journal_ponts.enregistrer_appel("x", "y", True, 1, 1, chemin="Z:\\dossier_improbable\\j.jsonl")
    # aucune assertion : le seul contrat est "ne lève pas d'exception"
