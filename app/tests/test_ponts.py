"""Tests déterministes de la partie PURE de ponts.py (validation, plafond, routeur) — aucun réseau,
aucun Chrome. Le reste (ouvrir/lancer/extraire_code réels) a été validé en direct ce soir (2026-08-20)
et est trop coûteux/non-déterministe pour un test automatique — cf. mémoire project_deepseek_bridge."""

import datetime

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


def test_plafond_quotidien_refuse_sans_ouvrir_chrome(monkeypatch):
    jour = datetime.date.today().isoformat()
    ponts._compteur_jour["deepseek"] = (jour, ponts._PLAFOND_JOUR)
    try:
        r = ponts.lancer("x", "y", nom="deepseek")
        assert r["ok"] is False
        assert "plafond quotidien" in r["journal"][0]
    finally:
        ponts._compteur_jour.pop("deepseek", None)


def test_plafond_se_reinitialise_un_nouveau_jour(monkeypatch):
    """Le compteur d'hier ne doit pas bloquer aujourd'hui."""
    ponts._compteur_jour["deepseek"] = ("2020-01-01", ponts._PLAFOND_JOUR)
    monkeypatch.setattr(ponts, "ouvrir", lambda nom: {"ok": False, "nom": nom, "erreur": "test_stop"})
    try:
        r = ponts.lancer("x", "y", nom="deepseek")
        # Le refus vient de `ouvrir` (mocké), PAS du plafond -> preuve que le plafond a été purgé.
        assert "cdp_down" not in str(r["journal"]) or "test_stop" in str(r["journal"])
        assert "plafond quotidien" not in r["journal"][0]
    finally:
        ponts._compteur_jour.pop("deepseek", None)


def test_verrou_existe_pour_chaque_pont_connu():
    assert set(ponts._verrous) == set(ponts.PONTS)
