"""Registre d'actions de la secrétaire (contrat schema/handler/requires_env/check_fn).

Une action reste invisible tant que son service manque (check_fn() falsy ou levant).
"""

from dataclasses import dataclass
from typing import Callable


@dataclass
class Action:
    nom: str
    description: str
    handler: Callable
    requires_env: tuple = ()
    check_fn: Callable | None = None


registre: dict[str, Action] = {}


def enregistrer(a: Action) -> None:
    registre[a.nom] = a


def disponibles() -> list:
    out = []
    for a in registre.values():
        try:
            if a.check_fn is None or a.check_fn():
                out.append(a)
        except Exception:
            pass  # une action dont le check plante est masquée
    return out
