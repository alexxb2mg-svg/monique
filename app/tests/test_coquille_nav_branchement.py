"""Vérifie que coquille.html boucle sur le contexte `departements` transmis
par serveur.py (nav.DEPARTEMENTS), et non plus sur un bloc `{% set arbre = [...] %}`
figé en dur dans le template — cf. plan.md, Informatique.
"""

from fastapi.testclient import TestClient

import brief
import nav
import serveur
from serveur import app


def test_arbre_vient_du_contexte_pas_du_template(monkeypatch):
    monkeypatch.setattr(
        brief,
        "construire",
        lambda chemin=None: {
            "mails_a_traiter": 3,
            "relances": 2,
            "taches_retard": 1,
            "phrase": "Ce matin, 3...",
        },
    )
    monkeypatch.setattr(
        nav,
        "DEPARTEMENTS",
        [
            {
                "slug": "test_branchement",
                "nom": "Departement Test Branchement",
                "couleur": "#123456",
                "personas": [
                    {
                        "nom": "Persona Test",
                        "avatar": "secretaire.png",
                        "onglets": [
                            {"route": "/vue/beecham", "label": "Onglet Test"},
                        ],
                    },
                ],
            },
        ],
    )

    r = TestClient(app).get("/")

    assert r.status_code == 200
    assert "Departement Test Branchement" in r.text
