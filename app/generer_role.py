"""Générateur déterministe de fichiers de rôle (agents/<nom>/ROLE.md).

Pur templating de chaînes : AUCUN appel LLM. Produit exactement le format déjà
utilisé par les ROLE.md existants (front-matter + corps), cf. `roles.py` pour
le parseur correspondant.
"""

from pathlib import Path

from roles import _NOM_AGENT


def contenu_role_md(
    nom, departement, triggers, description_routage, corps
) -> str:
    if not _NOM_AGENT.match(nom or ""):
        raise ValueError("nom d'agent invalide")
    triggers_join = ", ".join(triggers)
    return (
        "---\n"
        f"name: {nom}\n"
        f"departement: {departement}\n"
        f"triggers_deterministes: [{triggers_join}]\n"
        f"description_routage: {description_routage}\n"
        "---\n"
        f"{corps}\n"
    )


def ecrire_role(
    nom, departement, triggers, description_routage, corps, racine=None, ecraser=False
) -> Path:
    # validation AVANT tout accès disque : un nom invalide (ex. path traversal)
    # ne doit jamais aboutir à un mkdir, même raté ou hors périmètre.
    texte = contenu_role_md(nom, departement, triggers, description_routage, corps)
    racine = racine or (Path(__file__).parent.parent / "agents")
    dossier = racine / nom
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / "ROLE.md"
    if fichier.exists() and not ecraser:
        raise FileExistsError(f"ROLE.md existe déjà pour {nom!r}")
    fichier.write_text(texte, encoding="utf-8")
    return fichier
