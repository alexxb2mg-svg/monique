"""Tests déterministes de la partie PURE de ponts.py (validation, routeur) — aucun réseau, aucun
Chrome. Le plafond quotidien (persisté via journal_ponts) est testé dans test_plafond_persistant.py.
Le reste (ouvrir/lancer/extraire_code réels) a été validé en direct ce soir (2026-08-20) et est trop
coûteux/non-déterministe pour un test automatique — cf. mémoire project_deepseek_bridge."""

import ponts


def test_nom_invalide_refuse_sans_ouvrir_chrome():
    r = ponts.lancer("x", "y", nom="chatgpt")
    assert r == {"ok": False, "texte": "", "journal": ["pont inconnu: chatgpt"], "session_id": None}


def test_choisir_pont_route_vers_le_moins_recemment_utilise():
    ponts._dernier_usage.clear()
    ponts._dernier_usage["deepseek"] = 100
    ponts._dernier_usage["gemini"] = 50
    assert ponts._choisir_pont() == "gemini"


def test_choisir_pont_respecte_un_nom_force():
    assert ponts._choisir_pont("deepseek") == "deepseek"


def test_verrou_existe_pour_chaque_pont_connu():
    assert set(ponts._verrous) == set(ponts.PONTS)
