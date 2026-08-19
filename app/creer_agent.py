"""Point d'entrée pour créer un agent (agents/<nom>/ROLE.md).

`generer_role.ecrire_role` fait déjà tout le travail de fond (templating +
validation du nom + écriture disque) mais n'était jusqu'ici appelé que par ses
tests — aucun point d'entrée réel ne l'invoquait. Ce module est un wrapper fin
(aucune logique dupliquée) + un CLI minimal en stdlib (`argparse`, règle
supply-chain : pas de dépendance nouvelle).

Choix CLI pour le corps du rôle : `--corps-fichier <chemin>` si fourni (lu tel
quel), sinon lecture de stdin — permet aussi bien un usage scripté qu'un
`cat corps.md | python -m creer_agent ...`.
"""

import argparse
import sys
from pathlib import Path

from generer_role import ecrire_role


def creer(
    nom, departement, triggers, description_routage, corps, racine=None, ecraser=False
) -> Path:
    return ecrire_role(
        nom, departement, triggers, description_routage, corps, racine=racine, ecraser=ecraser
    )


def _cli(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Crée agents/<nom>/ROLE.md")
    parser.add_argument("nom")
    parser.add_argument("departement")
    parser.add_argument("description_routage")
    parser.add_argument(
        "--trigger",
        action="append",
        default=[],
        dest="triggers",
        help="déclencheur déterministe, répétable (ex. --trigger tag=front)",
    )
    parser.add_argument(
        "--corps-fichier",
        dest="corps_fichier",
        help="chemin du fichier contenant le corps du rôle (défaut : stdin)",
    )
    parser.add_argument("--ecraser", action="store_true")
    args = parser.parse_args(argv)

    if args.corps_fichier:
        corps = Path(args.corps_fichier).read_text(encoding="utf-8")
    else:
        corps = sys.stdin.read()

    fichier = creer(
        args.nom,
        args.departement,
        args.triggers,
        args.description_routage,
        corps,
        ecraser=args.ecraser,
    )
    print(fichier)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
