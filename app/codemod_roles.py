"""Codemod textuel ciblé — insère une entrée dans un dict Python (ex. ROLES/_OUTILS de
app/beecham.py) sans toucher aux entrées existantes ni reformater le reste du fichier.

Insertion textuelle, PAS un vrai parseur AST round-trip (libcst n'est pas une dépendance de
ce dépôt — décision D-11, éviter une dépendance nouvelle sans validation supply-chain).
Valide le résultat avec `ast.parse` avant de le renvoyer : si l'insertion produit un texte
syntaxiquement invalide, lève une erreur plutôt que de renvoyer un texte cassé.

Périmètre de cette mission (D-11 §3 Générateur A, points A2/A3) : construire et tester ce
module en isolation, sur un texte synthétique — PAS d'application réelle à `app/beecham.py`
(fichier à très forte collision inter-missions, cf. `generer_vue.py`).
"""

import ast


def inserer_entree_dict(texte_source: str, nom_dict: str, ligne_entree: str) -> str:
    """Insère `ligne_entree` juste avant l'accolade fermante du dict `nom_dict = {...}`
    trouvé dans `texte_source`, par comptage d'accolades (robuste aux dicts imbriqués dans
    les valeurs, ex. ROLES dont les valeurs sont des chaînes concaténées sur plusieurs
    lignes). `ligne_entree` est le texte déjà formé à insérer tel quel (ex. '    "nom": '
    '"valeur",\n'), la fonction ne le génère pas.

    Lève ValueError si `nom_dict` n'est pas trouvé, ou si le résultat n'est pas un Python
    syntaxiquement valide (ast.parse) — n'insère jamais un texte cassé sans le signaler.
    """
    marqueur = f"{nom_dict} = {{"
    debut = texte_source.find(marqueur)
    if debut == -1:
        raise ValueError(f"dict {nom_dict!r} introuvable dans le texte source")

    pos = debut + len(marqueur)
    profondeur = 1
    while profondeur > 0:
        if pos >= len(texte_source):
            raise ValueError(f"accolade fermante de {nom_dict!r} jamais trouvée")
        if texte_source[pos] == "{":
            profondeur += 1
        elif texte_source[pos] == "}":
            profondeur -= 1
        pos += 1
    fin_accolade = pos - 1  # index du '}' fermant

    nouveau_texte = (
        texte_source[:fin_accolade] + ligne_entree + texte_source[fin_accolade:]
    )

    try:
        ast.parse(nouveau_texte)
    except SyntaxError as e:
        raise ValueError(f"insertion produit un texte invalide : {e}") from e

    return nouveau_texte
