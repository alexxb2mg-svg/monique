"""Vrais tests (avant dispatch au pont) pour ponts.fermer_inactifs — fermeture auto des ponts
inactifs depuis trop longtemps. ponts.etat/ponts.fermer mockés."""

import time

import ponts


def test_ferme_un_pont_inactif_depuis_longtemps(monkeypatch):
    monkeypatch.setattr(
        ponts,
        "etat",
        lambda: [{"nom": "deepseek", "ouvert": True, "suivi": True, "dernier_usage": time.time() - 9999}],
    )
    fermes = []
    monkeypatch.setattr(ponts, "fermer", lambda nom: fermes.append(nom) or {"ok": True})

    resultat = ponts.fermer_inactifs(seuil_s=1800)

    assert resultat == ["deepseek"]
    assert fermes == ["deepseek"]


def test_ne_touche_pas_un_pont_utilise_recemment(monkeypatch):
    monkeypatch.setattr(
        ponts,
        "etat",
        lambda: [{"nom": "gemini", "ouvert": True, "suivi": True, "dernier_usage": time.time() - 10}],
    )
    fermes = []
    monkeypatch.setattr(ponts, "fermer", lambda nom: fermes.append(nom) or {"ok": True})

    resultat = ponts.fermer_inactifs(seuil_s=1800)

    assert resultat == []
    assert fermes == []


def test_ignore_un_pont_deja_ferme(monkeypatch):
    monkeypatch.setattr(
        ponts, "etat", lambda: [{"nom": "deepseek", "ouvert": False, "suivi": False, "dernier_usage": None}]
    )
    fermes = []
    monkeypatch.setattr(ponts, "fermer", lambda nom: fermes.append(nom) or {"ok": True})

    resultat = ponts.fermer_inactifs(seuil_s=1800)

    assert resultat == []


def test_ignore_un_pont_jamais_utilise(monkeypatch):
    """Scope volontairement simple : un pont ouvert mais jamais appele (dernier_usage=None) n'est
    PAS ferme par ce mecanisme (pas de moyen fiable de savoir depuis quand il traine, sans risque
    de fermer un pont tout juste ouvert)."""
    monkeypatch.setattr(
        ponts, "etat", lambda: [{"nom": "deepseek", "ouvert": True, "suivi": True, "dernier_usage": None}]
    )
    fermes = []
    monkeypatch.setattr(ponts, "fermer", lambda nom: fermes.append(nom) or {"ok": True})

    resultat = ponts.fermer_inactifs(seuil_s=1800)

    assert resultat == []
