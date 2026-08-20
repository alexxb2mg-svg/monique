"""Tests déterministes de boucle_ponts.deepseek_exploration_puis_expert — 3 temps : branches
(Instant) -> approfondissement PAR branche (Instant, une conv fraîche chacune) -> synthèse
(Expert, sur TOUT le matériel accumulé, pas juste les titres)."""

import boucle_ponts
import ponts


def test_chaine_complete_3_temps(monkeypatch):
    appels_conv = []
    monkeypatch.setattr(ponts, "nouvelle_conversation", lambda nom: appels_conv.append(nom))

    appels_lancer = []

    def faux_lancer(role, prompt, nom=None, mode=None):
        appels_lancer.append({"prompt": prompt, "mode": mode})
        if mode == "expert":
            return {"ok": True, "texte": "PROPOSITION 1: synthese finale", "journal": []}
        if len(appels_lancer) == 1:  # 1er appel = identification des branches
            return {"ok": True, "texte": "BRANCHE 1: sujet A\nBRANCHE 2: sujet B", "journal": []}
        return {"ok": True, "texte": f"recherche detaillee ({len(appels_lancer)})", "journal": []}

    monkeypatch.setattr(ponts, "lancer", faux_lancer)

    res = boucle_ponts.deepseek_exploration_puis_expert(
        "identifie des branches", lambda b: f"approfondis : {b}", lambda materiel: f"synthetise : {materiel}"
    )

    assert res["ok"] is True
    assert res["branches"] == ["sujet A", "sujet B"]
    assert len(res["recherches"]) == 2
    assert res["expert"] == "PROPOSITION 1: synthese finale"
    # 1 conv pour les branches + 1 par branche (2) + 1 avant l'expert = 4
    assert appels_conv == ["deepseek"] * 4
    # Le prompt de synthèse doit contenir TOUT le matériel des 2 branches, pas juste les titres.
    prompt_expert = appels_lancer[-1]["prompt"]
    assert "sujet A" in prompt_expert or "recherche detaillee" in prompt_expert


def test_echec_identification_branches_arrete_tout(monkeypatch):
    monkeypatch.setattr(ponts, "nouvelle_conversation", lambda nom: None)
    monkeypatch.setattr(ponts, "lancer", lambda role, prompt, nom=None, mode=None: {"ok": False, "texte": "", "journal": []})

    res = boucle_ponts.deepseek_exploration_puis_expert("q", lambda b: b, lambda m: m)

    assert res["ok"] is False
    assert res["branches"] == []


def test_aucune_branche_parsee_arrete_tout(monkeypatch):
    monkeypatch.setattr(ponts, "nouvelle_conversation", lambda nom: None)
    monkeypatch.setattr(
        ponts, "lancer", lambda role, prompt, nom=None, mode=None: {"ok": True, "texte": "pas de format attendu", "journal": []}
    )

    res = boucle_ponts.deepseek_exploration_puis_expert("q", lambda b: b, lambda m: m)

    assert res["ok"] is False


def test_materiel_tronque_par_branche_avant_synthese(monkeypatch):
    """Bug réel (20/08/2026) : sans troncature, 5 branches x ~9000 car. de vraie recherche ont
    produit un prompt de 36 289 caractères -> l'appel expert a ÉCHOUÉ, tout le matériel accumulé
    a été perdu silencieusement (repli sur les seuls titres de branches, pauvre)."""
    monkeypatch.setattr(ponts, "nouvelle_conversation", lambda nom: None)
    appels_lancer = []

    def faux_lancer(role, prompt, nom=None, mode=None):
        appels_lancer.append(prompt)
        if mode == "expert":
            return {"ok": True, "texte": "PROPOSITION 1: x", "journal": []}
        if len(appels_lancer) == 1:
            return {"ok": True, "texte": "BRANCHE 1: A\nBRANCHE 2: B", "journal": []}
        return {"ok": True, "texte": "x" * 9000, "journal": []}  # grosse recherche réelle

    monkeypatch.setattr(ponts, "lancer", faux_lancer)
    boucle_ponts.deepseek_exploration_puis_expert("q", lambda b: b, lambda m: m)

    prompt_expert = appels_lancer[-1]
    assert len(prompt_expert) < 10000  # 2 branches x 2500 tronqués, pas 2 x 9000


def test_echec_dune_branche_nempeche_pas_les_autres(monkeypatch):
    monkeypatch.setattr(ponts, "nouvelle_conversation", lambda nom: None)
    appels = {"n": 0}

    def faux_lancer(role, prompt, nom=None, mode=None):
        appels["n"] += 1
        if mode == "expert":
            return {"ok": True, "texte": "PROPOSITION 1: x", "journal": []}
        if appels["n"] == 1:
            return {"ok": True, "texte": "BRANCHE 1: A\nBRANCHE 2: B", "journal": []}
        if appels["n"] == 2:  # la 1re branche echoue
            return {"ok": False, "texte": "", "journal": []}
        return {"ok": True, "texte": "recherche B", "journal": []}

    monkeypatch.setattr(ponts, "lancer", faux_lancer)

    res = boucle_ponts.deepseek_exploration_puis_expert("q", lambda b: b, lambda m: m)

    assert res["ok"] is True  # l'echec d'UNE branche ne bloque pas la synthese finale
    assert len(res["recherches"]) == 2
    assert "échec" in res["recherches"][0]
