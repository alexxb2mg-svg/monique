"""Tests déterministes de ecrire_tests_pour_brique / planifier(Beecham) / choisir_brique — ponts.lancer
et ponts.extraire_code mockés. Cible en particulier le bug réel vécu le 20/08/2026 : un test généré
par Gemini avec une erreur de syntaxe (littéral bytes non-ASCII) bloquait toute la boucle en aval."""

import boucle_beecham
import ponts


def test_ecrire_tests_syntaxe_valide_du_premier_coup(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ponts, "lancer", lambda role, *a, **k: {"ok": True, "texte": "ok", "journal": []}
    )
    monkeypatch.setattr(ponts, "extraire_code", lambda nom: "def test_x():\n    assert True\n")
    cible = tmp_path / "test_x.py"

    ok = boucle_beecham.ecrire_tests_pour_brique("une brique", "x", str(cible))

    assert ok is True
    assert "def test_x" in cible.read_text(encoding="utf-8")


def test_ecrire_tests_syntaxe_invalide_puis_corrigee(tmp_path, monkeypatch):
    """Reproduit le bug réel : bytes littéral avec accent -> SyntaxError -> retente -> corrigé."""
    monkeypatch.setattr(
        ponts, "lancer", lambda role, *a, **k: {"ok": True, "texte": "ok", "journal": []}
    )
    reponses = iter(['b"Référence"', "b'Reference'"])  # 1ère cassée (non-ASCII), 2e valide
    monkeypatch.setattr(ponts, "extraire_code", lambda nom: next(reponses))
    cible = tmp_path / "test_x.py"

    ok = boucle_beecham.ecrire_tests_pour_brique("une brique", "x", str(cible))

    assert ok is True
    assert "Reference" in cible.read_text(encoding="utf-8")


def test_ecrire_tests_toujours_invalide_apres_retente_echoue_proprement(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ponts, "lancer", lambda role, *a, **k: {"ok": True, "texte": "ok", "journal": []}
    )
    monkeypatch.setattr(ponts, "extraire_code", lambda nom: "def f(:\n")  # toujours cassé
    cible = tmp_path / "test_x.py"

    ok = boucle_beecham.ecrire_tests_pour_brique("une brique", "x", str(cible))

    assert ok is False
    assert not cible.exists()  # jamais écrit un test cassé sur disque


def test_ecrire_tests_extraction_vide_echoue_sans_planter(tmp_path, monkeypatch):
    """ast.parse("") ne lève PAS SyntaxError (module vide = syntaxiquement valide) : le garde
    `not code_test.strip()` doit intercepter ce cas avant, sinon on écrirait un test vide inutile."""
    monkeypatch.setattr(
        ponts, "lancer", lambda role, *a, **k: {"ok": True, "texte": "ok", "journal": []}
    )
    monkeypatch.setattr(ponts, "extraire_code", lambda nom: "")
    cible = tmp_path / "test_x.py"

    ok = boucle_beecham.ecrire_tests_pour_brique("une brique", "x", str(cible))

    assert ok is False
    assert not cible.exists()


def test_planifier_beecham_parse_les_propositions(monkeypatch):
    """proposer_candidats est maintenant un chaînage à 3 temps (branches -> approfondissement par
    branche -> synthèse experte), cf. boucle_ponts.deepseek_exploration_puis_expert."""
    monkeypatch.setattr(ponts, "nouvelle_conversation", lambda nom: None)

    def faux_lancer(role, prompt, nom=None, mode=None):
        if mode == "expert":
            return {"ok": True, "texte": "PROPOSITION 1: faire A\nPROPOSITION 2: faire B", "journal": []}
        return {"ok": True, "texte": "BRANCHE 1: sujet A\nBRANCHE 2: sujet B", "journal": []}

    monkeypatch.setattr(ponts, "lancer", faux_lancer)
    assert boucle_beecham.proposer_candidats("contexte") == ["faire A", "faire B"]


def test_choisir_brique_parse_le_choix(monkeypatch):
    monkeypatch.setattr(
        ponts,
        "lancer",
        lambda role, *a, **k: {"ok": True, "texte": "CHOIX: 2\njustification", "journal": []},
    )
    idx, justif = boucle_beecham.choisir_brique(["A", "B", "C"])
    assert idx == 1
    assert "justification" in justif


def test_choisir_brique_index_hors_bornes_renvoie_none(monkeypatch):
    monkeypatch.setattr(
        ponts, "lancer", lambda role, *a, **k: {"ok": True, "texte": "CHOIX: 99", "journal": []}
    )
    idx, _ = boucle_beecham.choisir_brique(["A", "B"])
    assert idx is None
