import re
from pathlib import Path

import nav


def test_departements_non_vide():
    assert nav.DEPARTEMENTS


def test_slugs_et_routes_uniques():
    slugs = [d["slug"] for d in nav.DEPARTEMENTS]
    assert len(slugs) == len(set(slugs))

    routes = [o["route"] for d in nav.DEPARTEMENTS for o in d["onglets"]]
    assert routes  # au moins un onglet quelque part
    assert len(routes) == len(set(routes))


def test_chaque_route_est_declaree_dans_serveur():
    serveur_py = Path(__file__).resolve().parents[1] / "serveur.py"
    texte = serveur_py.read_text(encoding="utf-8")
    routes_declarees = set(re.findall(r'@app\.get\("(/vue/[^"]+)"', texte))

    routes_nav = {o["route"] for d in nav.DEPARTEMENTS for o in d["onglets"]}
    manquantes = routes_nav - routes_declarees
    assert not manquantes, f"routes absentes de serveur.py : {manquantes}"
