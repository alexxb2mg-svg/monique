"""Générateur déterministe de squelette de vue (contexte + template + test).

Pur templating de chaînes : AUCUN appel LLM, même esprit que `generer_role.py`.
Écrit 3 fichiers déterministes à partir d'un nom de vue validé et d'un libellé
humain — un squelette à COMPLÉTER ensuite par un humain/agent, jamais de
logique métier ici (cf. `vue_usage.py::contexte_usage` pour le patron réel à
suivre une fois le stub complété).

Limite volontaire : cette fonction NE TOUCHE JAMAIS `serveur.py`,
`templates/coquille.html` ni `nav.py` (fichiers à très forte collision
inter-missions). Le branchement route + nav reste manuel — `generer()`
imprime seulement le bloc à coller.
"""

from pathlib import Path

from roles import _NOM_AGENT


def contenu_vue_py(nom) -> str:
    if not _NOM_AGENT.match(nom or ""):
        raise ValueError("nom de vue invalide")
    return (
        f'"""Contexte de la vue {nom} — squelette généré, à compléter."""\n'
        "\n"
        "\n"
        f"def contexte_{nom}(chemin=None):\n"
        f'    """Lecture seule, fail-soft — STUB : aucune logique métier pour l\'instant.\n'
        "\n"
        "    À compléter (même patron que vue_usage.py::contexte_usage) : connexion\n"
        "    sqlite en mode=ro sur chemin_ecriture(), try/except Exception large =>\n"
        "    valeur vide par défaut, jamais de 500 sur une vue.\n"
        '    """\n'
        "    try:\n"
        "        return []\n"
        "    except Exception:\n"
        "        return []\n"
    )


def contenu_vue_html(libelle) -> str:
    return (
        f'<div class="besoin-titre">{libelle}</div>\n'
        "{% for item in items %}\n"
        '  <div class="rel">\n'
        '    <div class="r1"><span class="ref">{{ item }}</span></div>\n'
        "  </div>\n"
        "{% else %}\n"
        f'  <p class="vide">Aucun élément {libelle.lower()} pour l\'instant.</p>\n'
        "{% endfor %}\n"
    )


def contenu_test_py(nom) -> str:
    return (
        f"import vue_{nom}\n"
        "\n"
        "\n"
        f"def test_contexte_{nom}_fail_soft_si_absent(tmp_path):\n"
        '    db_absente = str(tmp_path / "n_existe_pas.db")\n'
        "\n"
        f"    assert vue_{nom}.contexte_{nom}(db_absente) == []\n"
    )


def bloc_branchement(nom) -> str:
    """Bloc de 4-6 lignes (contexte + route FastAPI) à coller à la main dans
    serveur.py + nav.py — cf. limite volontaire en tête de module."""
    return (
        f"import vue_{nom}\n"
        "\n"
        f'@app.get("/vue/{nom}", response_class=HTMLResponse)\n'
        f"async def vue_{nom}_route(request: Request):\n"
        f"    ctx = vue_{nom}.contexte_{nom}()\n"
        f'    return templates.TemplateResponse("vue_{nom}.html", {{"request": request, "items": ctx}})\n'
    )


def generer(nom, libelle, racine=None, ecraser=False) -> dict[str, Path]:
    # validation AVANT tout accès disque : un nom invalide (ex. path traversal)
    # ne doit jamais aboutir à un mkdir, même raté ou hors périmètre (cf. generer_role.py).
    if not _NOM_AGENT.match(nom or ""):
        raise ValueError("nom de vue invalide")

    racine = Path(racine) if racine is not None else Path(__file__).parent
    fichiers = {
        "vue_py": racine / f"vue_{nom}.py",
        "template": racine / "templates" / f"vue_{nom}.html",
        "test": racine / "tests" / f"test_vue_{nom}.py",
    }

    # garde-fou anti-écrasement silencieux (même patron que generer_role.py::ecrire_role) :
    # vérifier les 3 cibles AVANT d'écrire quoi que ce soit, sinon un nom déjà branché en
    # production (ex. "usage") écraserait à moitié un module réel écrit et testé à la main.
    if not ecraser:
        deja_existants = [f for f in fichiers.values() if f.exists()]
        if deja_existants:
            noms = ", ".join(str(f) for f in deja_existants)
            raise FileExistsError(f"vue {nom!r} déjà générée : {noms}")

    for fichier in fichiers.values():
        fichier.parent.mkdir(parents=True, exist_ok=True)

    fichiers["vue_py"].write_text(contenu_vue_py(nom), encoding="utf-8")
    fichiers["template"].write_text(contenu_vue_html(libelle), encoding="utf-8")
    fichiers["test"].write_text(contenu_test_py(nom), encoding="utf-8")

    print(bloc_branchement(nom))
    return fichiers
