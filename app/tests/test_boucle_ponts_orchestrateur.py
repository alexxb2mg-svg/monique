"""Tests déterministes de planifier()/orchestrer() — ponts.lancer et implementer_et_corriger sont
mockés (ce dernier est déjà testé isolément dans test_boucle_ponts.py) : on teste ICI uniquement la
logique d'orchestration (parsing du plan, enchaînement des briques, arrêt sur échec)."""

import boucle_ponts
import ponts


def test_planifier_parse_les_briques(monkeypatch):
    texte = "BRIQUE 1: faire A\nBRIQUE 2: faire B\nBRIQUE 3: faire C"
    monkeypatch.setattr(ponts, "lancer", lambda role, *a, **k: {"ok": True, "texte": texte, "journal": []})
    assert boucle_ponts.planifier("un module") == ["faire A", "faire B", "faire C"]


def test_planifier_echec_envoi_renvoie_liste_vide(monkeypatch):
    monkeypatch.setattr(ponts, "lancer", lambda role, *a, **k: {"ok": False, "texte": "", "journal": []})
    assert boucle_ponts.planifier("un module") == []


def test_orchestrer_enchaine_toutes_les_briques_sur_succes(monkeypatch, tmp_path):
    monkeypatch.setattr(boucle_ponts, "planifier", lambda c: ["faire A", "faire B"])
    appels = []

    def faux_impl(chemin, consigne, cmd_test, max_essais):
        appels.append(consigne)
        return {"ok": True, "essais": 1, "journal": [], "dernier_code": "x", "dernier_test": ""}

    monkeypatch.setattr(boucle_ponts, "implementer_et_corriger", faux_impl)

    r = boucle_ponts.orchestrer("un module", str(tmp_path / "cible.py"), ["pytest"])

    assert r["toutes_ok"] is True
    assert len(r["resultats"]) == 2
    assert "faire A" in appels[0] and "faire B" in appels[1]


def test_orchestrer_sarrete_a_la_premiere_brique_qui_echoue(monkeypatch, tmp_path):
    monkeypatch.setattr(boucle_ponts, "planifier", lambda c: ["faire A", "faire B", "faire C"])
    appels = {"n": 0}

    def faux_impl(chemin, consigne, cmd_test, max_essais):
        appels["n"] += 1
        ok = appels["n"] != 2  # la brique 2 échoue
        return {"ok": ok, "essais": max_essais, "journal": [], "dernier_code": "x", "dernier_test": ""}

    monkeypatch.setattr(boucle_ponts, "implementer_et_corriger", faux_impl)

    r = boucle_ponts.orchestrer("un module", str(tmp_path / "cible.py"), ["pytest"])

    assert r["toutes_ok"] is False
    assert len(r["resultats"]) == 2  # arrêté après l'échec de la brique 2, pas de brique 3 tentée


def test_orchestrer_transmet_le_code_existant_a_la_brique_suivante(monkeypatch, tmp_path):
    cible = tmp_path / "cible.py"
    monkeypatch.setattr(boucle_ponts, "planifier", lambda c: ["faire A", "faire B"])
    appels = []

    def faux_impl(chemin, consigne, cmd_test, max_essais):
        appels.append(consigne)
        cible.write_text("def a(): pass" if len(appels) == 1 else cible.read_text(), encoding="utf-8")
        return {"ok": True, "essais": 1, "journal": [], "dernier_code": "x", "dernier_test": ""}

    monkeypatch.setattr(boucle_ponts, "implementer_et_corriger", faux_impl)
    boucle_ponts.orchestrer("un module", str(cible), ["pytest"])

    assert "def a(): pass" in appels[1]  # la 2e brique a bien reçu le code écrit par la 1re


def test_orchestrer_plan_vide_ne_tente_aucune_brique(monkeypatch, tmp_path):
    monkeypatch.setattr(boucle_ponts, "planifier", lambda c: [])
    r = boucle_ponts.orchestrer("un module", str(tmp_path / "cible.py"), ["pytest"])
    assert r["plan_ok"] is False
    assert r["resultats"] == []
    assert r["toutes_ok"] is False
