"""Vérifie que le VRAI `nav.DEPARTEMENTS` de production est fidèlement rendu
par coquille.html — pas un jeu de données synthétique monkeypatché
(cf. test_coquille_nav_branchement.py) ni `nav.py` en isolation
(cf. test_nav.py).

Piège identifié lors du rejet précédent : Jinja2 échappe automatiquement
"Infra & Surveillance Système" en "Infra &amp; Surveillance Système" dans le
HTML rendu — comparer la forme échappée, pas la chaîne Python brute.
"""

import html

from fastapi.testclient import TestClient

import nav
from serveur import app


def test_nav_departements_rendus_fidelement():
    r = TestClient(app).get("/")
    assert r.status_code == 200

    noms = [d["nom"] for d in nav.DEPARTEMENTS]
    assert len(noms) == len(set(noms))  # aucun doublon dans la structure elle-même

    for nom in noms:
        # Jinja autoescape : "Infra & Surveillance Système" -> "Infra &amp; Surveillance Système"
        # dans le HTML rendu — comparer la forme échappée, pas la chaîne Python brute.
        assert html.escape(nom) in r.text, f"département absent du rendu : {nom}"

    for dep in nav.DEPARTEMENTS:
        for persona in dep["personas"]:
            for onglet in persona["onglets"]:
                assert f'hx-get="{onglet["route"]}"' in r.text, (
                    f"onglet non rendu : {dep['nom']} / {persona['nom']} / {onglet['label']}"
                )
