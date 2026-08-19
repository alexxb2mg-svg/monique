"""Vue « Missions actives » : le test contrôle sa propre entrée (mock de la source) au lieu de
lire la DB réelle — sinon il échoue dès que la boucle Beecham a une mission en cours."""

from fastapi.testclient import TestClient

import vue_missions
from serveur import app


def test_vue_missions_actives_vide(monkeypatch):
    """Aucune mission en cours -> message d'état."""
    monkeypatch.setattr(vue_missions, "contexte_missions_actives", lambda chemin=None: [])
    r = TestClient(app).get("/vue/missions-actives")
    assert r.status_code == 200
    assert "Aucune mission en cours" in r.text


def test_vue_missions_actives_avec_mission(monkeypatch):
    """Une mission en cours -> son résumé s'affiche."""
    monkeypatch.setattr(
        vue_missions,
        "contexte_missions_actives",
        lambda chemin=None: [{"id": "m1", "consigne": "refonte du module X", "actions": []}],
    )
    r = TestClient(app).get("/vue/missions-actives")
    assert r.status_code == 200
    assert "Aucune mission en cours" not in r.text
