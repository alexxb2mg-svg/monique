"""Point d'entrée unique de l'accueil : Alex dit une intention, Monique décide qui s'en occupe.

Patron repris d'Hermes Agent (vérifié dans leur doc avant de coder) : pas de routage nommé côté
utilisateur, l'agent principal reçoit tout et délègue lui-même. Ici l'intention part au rôle
`chef`, l'orchestrateur — jamais à un persona choisi à la main.
"""

from fastapi.testclient import TestClient

import beecham
import serveur
from serveur import app

client = TestClient(app)


def test_l_accueil_propose_de_dire_quelque_chose_a_monique():
    page = client.get("/").text
    assert 'hx-post="/intention"' in page
    assert 'name="intention"' in page


def test_intention_lance_une_mission_chef(monkeypatch):
    """Le rôle n'est PAS choisi par l'utilisateur : tout va à l'orchestrateur."""
    lances = []
    monkeypatch.setattr(beecham, "demarrer_mission", lambda consigne: lances.append(consigne) or 1)

    class _FauxThread:
        def __init__(self, target=None, args=(), daemon=None):
            self.args = args
            lances.append(("role", args[1] if len(args) > 1 else None))

        def start(self):
            pass

    monkeypatch.setattr(serveur.threading, "Thread", _FauxThread)

    r = client.post("/intention", data={"intention": "il faudrait pouvoir filtrer les devis"})
    assert r.status_code == 200
    assert "il faudrait pouvoir filtrer les devis" in lances
    assert ("role", "chef") in lances


def test_intention_vide_ne_lance_rien(monkeypatch):
    appels = []
    monkeypatch.setattr(beecham, "demarrer_mission", lambda c: appels.append(c) or 1)

    r = client.post("/intention", data={"intention": "   "})
    assert r.status_code == 200
    assert appels == [], "une intention vide ne doit pas créer de mission"
