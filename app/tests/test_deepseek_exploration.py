"""Tests déterministes de boucle_ponts.deepseek_explore_gemini_synthetise — DeepSeek EXPLORE
(branches + approfondissement par branche, Instant, seul accès web du système), Gemini SYNTHÉTISE
(sa fenêtre de contexte énorme tient tout le matériel SANS troncature — corrige un bug réel où
DeepSeek Expert étouffait sur un prompt de 36 000+ caractères)."""

import boucle_ponts
import ponts


def test_chaine_complete_deepseek_explore_gemini_synthetise(monkeypatch):
    appels_conv = []
    monkeypatch.setattr(ponts, "nouvelle_conversation", lambda nom: appels_conv.append(nom))

    appels_lancer = []

    def faux_lancer(role, prompt, nom=None, mode=None):
        appels_lancer.append({"prompt": prompt, "nom": nom, "mode": mode})
        if nom == "gemini":
            return {"ok": True, "texte": "PROPOSITION 1: synthese finale", "journal": []}
        if len(appels_lancer) == 1:  # 1er appel DeepSeek = identification des branches
            return {"ok": True, "texte": "BRANCHE 1: sujet A\nBRANCHE 2: sujet B", "journal": []}
        return {"ok": True, "texte": f"recherche detaillee ({len(appels_lancer)})", "journal": []}

    monkeypatch.setattr(ponts, "lancer", faux_lancer)

    res = boucle_ponts.deepseek_explore_gemini_synthetise(
        "identifie des branches", lambda b: f"approfondis : {b}", lambda materiel: f"synthetise : {materiel}"
    )

    assert res["ok"] is True
    assert res["branches"] == ["sujet A", "sujet B"]
    assert len(res["recherches"]) == 2
    assert res["synthese"] == "PROPOSITION 1: synthese finale"
    # nouvelle_conversation : 1 pour les branches + 1 par branche (2) = 3 (PAS pour Gemini, sa
    # conversation est gérée par ponts.lancer lui-même comme pour tout appel).
    assert appels_conv == ["deepseek"] * 3
    assert appels_lancer[-1]["nom"] == "gemini"  # la synthèse va bien à Gemini
    prompt_synthese = appels_lancer[-1]["prompt"]
    assert "sujet A" in prompt_synthese or "recherche detaillee" in prompt_synthese


def test_materiel_non_tronque_avant_gemini(monkeypatch):
    """Contrairement à l'ancienne version (DeepSeek Expert), Gemini n'a PAS besoin de troncature :
    bug réel corrigé (20/08/2026) — 36 289 caractères faisaient échouer DeepSeek Expert."""
    monkeypatch.setattr(ponts, "nouvelle_conversation", lambda nom: None)
    appels_lancer = []

    def faux_lancer(role, prompt, nom=None, mode=None):
        appels_lancer.append(prompt)
        if nom == "gemini":
            return {"ok": True, "texte": "PROPOSITION 1: x", "journal": []}
        if len(appels_lancer) == 1:
            return {"ok": True, "texte": "BRANCHE 1: A\nBRANCHE 2: B", "journal": []}
        return {"ok": True, "texte": "x" * 9000, "journal": []}  # grosse recherche réelle

    monkeypatch.setattr(ponts, "lancer", faux_lancer)
    boucle_ponts.deepseek_explore_gemini_synthetise("q", lambda b: b, lambda m: m)

    prompt_gemini = appels_lancer[-1]
    assert len(prompt_gemini) > 15000  # PAS tronqué : 2 branches x 9000 caractères réels tiennent


def test_echec_identification_branches_arrete_tout(monkeypatch):
    monkeypatch.setattr(ponts, "nouvelle_conversation", lambda nom: None)
    monkeypatch.setattr(ponts, "lancer", lambda role, prompt, nom=None, mode=None: {"ok": False, "texte": "", "journal": []})

    res = boucle_ponts.deepseek_explore_gemini_synthetise("q", lambda b: b, lambda m: m)

    assert res["ok"] is False
    assert res["branches"] == []


def test_aucune_branche_parsee_arrete_tout(monkeypatch):
    monkeypatch.setattr(ponts, "nouvelle_conversation", lambda nom: None)
    monkeypatch.setattr(
        ponts, "lancer", lambda role, prompt, nom=None, mode=None: {"ok": True, "texte": "pas de format attendu", "journal": []}
    )

    res = boucle_ponts.deepseek_explore_gemini_synthetise("q", lambda b: b, lambda m: m)

    assert res["ok"] is False


def test_echec_dune_branche_nempeche_pas_les_autres(monkeypatch):
    monkeypatch.setattr(ponts, "nouvelle_conversation", lambda nom: None)
    appels = {"n": 0}

    def faux_lancer(role, prompt, nom=None, mode=None):
        appels["n"] += 1
        if nom == "gemini":
            return {"ok": True, "texte": "PROPOSITION 1: x", "journal": []}
        if appels["n"] == 1:
            return {"ok": True, "texte": "BRANCHE 1: A\nBRANCHE 2: B", "journal": []}
        if appels["n"] == 2:  # la 1re branche echoue
            return {"ok": False, "texte": "", "journal": []}
        return {"ok": True, "texte": "recherche B", "journal": []}

    monkeypatch.setattr(ponts, "lancer", faux_lancer)

    res = boucle_ponts.deepseek_explore_gemini_synthetise("q", lambda b: b, lambda m: m)

    assert res["ok"] is True  # l'echec d'UNE branche ne bloque pas la synthese finale
    assert len(res["recherches"]) == 2
    assert "échec" in res["recherches"][0]
