"""Tests déterministes de boucle_ponts.deepseek_recherche_puis_expert — DeepSeek en 2 temps :
conversation fraîche = Instant (accès web) pour la recherche, PUIS nouvelle conversation fraîche
en mode expert (DeepThink, sans accès web) pour approfondir sur la base du résultat capturé."""

import boucle_ponts
import ponts


def test_chaine_recherche_puis_expert(monkeypatch):
    appels_conv = []
    monkeypatch.setattr(ponts, "nouvelle_conversation", lambda nom: appels_conv.append(nom))

    appels_lancer = []

    def faux_lancer(role, prompt, nom=None, mode=None):
        appels_lancer.append({"role": role, "prompt": prompt, "nom": nom, "mode": mode})
        if mode == "expert":
            return {"ok": True, "texte": "APPROFONDI: " + prompt[:20], "journal": []}
        return {"ok": True, "texte": "RECHERCHE BRUTE", "journal": []}

    monkeypatch.setattr(ponts, "lancer", faux_lancer)

    res = boucle_ponts.deepseek_recherche_puis_expert(
        "question de recherche", lambda recherche: f"Approfondis : {recherche}"
    )

    assert res["ok"] is True
    assert res["recherche"] == "RECHERCHE BRUTE"
    assert "APPROFONDI" in res["expert"]
    assert appels_conv == ["deepseek", "deepseek"]  # une conv fraîche AVANT chaque étape
    assert appels_lancer[0]["mode"] is None  # 1re étape : Instant (pas de mode= -> web actif)
    assert appels_lancer[1]["mode"] == "expert"  # 2e étape : Expert
    assert "RECHERCHE BRUTE" in appels_lancer[1]["prompt"]  # le contexte de l'étape 1 est transmis


def test_echec_recherche_ne_tente_pas_expert(monkeypatch):
    monkeypatch.setattr(ponts, "nouvelle_conversation", lambda nom: None)
    monkeypatch.setattr(ponts, "lancer", lambda role, prompt, nom=None, mode=None: {"ok": False, "texte": "", "journal": []})

    res = boucle_ponts.deepseek_recherche_puis_expert("q", lambda r: r)

    assert res["ok"] is False
    assert res["recherche"] == ""
    assert res["expert"] == ""
