"""Placeholder du département Approvisionnement (fournisseurs de matériel électrique).

Sans donnée réelle pour l'instant — voir la décomposition complète dans
atelier/connaissances/decomposition_d14_fournisseurs_departement.md (§3, M1).

À ne pas confondre avec app/fournisseurs.py, qui gère les clés API des
fournisseurs de modèles IA (sujet distinct, sans rapport).
"""

REGISTRE: list = []


def lister_fournisseurs() -> list:
    return list(REGISTRE)
