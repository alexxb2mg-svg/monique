"""Point d'entrée pour créer un squelette de vue (app/vue_<nom>.py + template + test).

`generer_vue.generer` fait déjà tout le travail de fond (templating + validation du nom +
écriture disque + garde anti-écrasement) mais n'était jusqu'ici appelé que par son propre
test — aucun point d'entrée réel ne l'invoquait, même symptôme déjà corrigé pour
generer_role.py via creer_agent.py (patron repris ici à l'identique). Ce module est un
wrapper fin (aucune logique dupliquée) + un CLI minimal en stdlib (argparse, règle
supply-chain : pas de dépendance nouvelle).
"""

import argparse

from generer_vue import generer


def creer(nom, libelle, racine=None, ecraser=False) -> dict:
    return generer(nom, libelle, racine=racine, ecraser=ecraser)


def _cli(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Crée app/vue_<nom>.py + template + test")
    parser.add_argument("nom")
    parser.add_argument("libelle")
    parser.add_argument("--ecraser", action="store_true")
    args = parser.parse_args(argv)

    fichiers = creer(args.nom, args.libelle, ecraser=args.ecraser)
    for f in fichiers.values():
        print(f)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
