"""Vrais tests (avant dispatch) pour boucle_beecham.revoir_tests_deepseek — renforce le juge : les
tests de Gemini sont relus par un AUTRE modèle avant qu'on leur fasse confiance."""

import boucle_beecham
import ponts


def test_renvoie_le_verdict_texte(monkeypatch):
    monkeypatch.setattr(
        ponts, "lancer", lambda role, *a, **k: {"ok": True, "texte": "VERDICT: OK\nbonne couverture", "journal": []}
    )
    verdict = boucle_beecham.revoir_tests_deepseek("def test_x(): assert True", "une brique")
    assert "VERDICT: OK" in verdict


def test_echec_envoi_renvoie_chaine_vide(monkeypatch):
    monkeypatch.setattr(ponts, "lancer", lambda role, *a, **k: {"ok": False, "texte": "", "journal": []})
    verdict = boucle_beecham.revoir_tests_deepseek("code", "brique")
    assert verdict == ""
