"""Le moteur : exécute un pipeline (liste d'étapes) sur un contexte partagé.

Une brique renvoie une `Decision` qui pilote le moteur :
  - continuer()            -> passe à l'étape suivante
  - sauter("nom")          -> reprend à l'étape nommée (permet reprise/boucles)
  - stop(statut, resume)   -> termine le pipeline avec ce statut

Le moteur est DÉTERMINISTE et sans effet de bord propre : toute l'action est dans les briques.
Il journalise chaque passage dans ctx["trace"] et protège contre les boucles infinies.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Decision:
    action: str  # "continue" | "saut" | "stop"
    cible: str | None = None  # pour "saut" : nom de l'étape cible
    statut: str | None = None  # pour "stop" : livre/valide/rejete/echec…
    resume: str | None = None  # pour "stop" : résumé humain


def continuer() -> Decision:
    return Decision("continue")


def sauter(cible: str) -> Decision:
    return Decision("saut", cible=cible)


def stop(statut: str, resume: str = "") -> Decision:
    return Decision("stop", statut=statut, resume=resume)


_GARDE_MAX = 100  # anti-boucle infinie (un pipeline sain fait quelques étapes, pas 100)


def executer_pipeline(etapes, ctx, briques, log=None):
    """Exécute `etapes` (liste de noms) sur `ctx` (dict mutable partagé) avec `briques`
    ({nom: fn(ctx)->Decision}). Renvoie ctx enrichi de statut/resume/trace.

    - Une étape absente de `briques` est une erreur de configuration -> stop 'erreur'.
    - `saut` vers une étape inconnue -> stop 'erreur' (pipeline mal formé, jamais silencieux).
    - Au-delà de `_GARDE_MAX` passages -> stop 'echec' (garde-fou anti-emballement).
    """
    index = {nom: i for i, nom in enumerate(etapes)}
    ctx.setdefault("trace", [])
    i, garde = 0, 0
    while 0 <= i < len(etapes):
        garde += 1
        if garde > _GARDE_MAX:
            ctx["statut"], ctx["resume"] = "echec", "garde anti-boucle du moteur atteinte"
            return ctx
        nom = etapes[i]
        brique = briques.get(nom)
        if brique is None:
            ctx["statut"], ctx["resume"] = "erreur", f"étape inconnue : {nom}"
            return ctx
        d = brique(ctx)
        ctx["trace"].append((nom, d.action, d.cible or d.statut or ""))
        if log:
            log(f"  · {nom} -> {d.action}{(' ' + d.cible) if d.cible else ''}{(' ' + d.statut) if d.statut else ''}")
        if d.action == "continue":
            i += 1
        elif d.action == "saut":
            if d.cible not in index:
                ctx["statut"], ctx["resume"] = "erreur", f"saut vers étape inconnue : {d.cible}"
                return ctx
            i = index[d.cible]
        elif d.action == "stop":
            ctx["statut"], ctx["resume"] = d.statut, d.resume
            return ctx
        else:
            ctx["statut"], ctx["resume"] = "erreur", f"action inconnue : {d.action}"
            return ctx
    ctx.setdefault("statut", "fini")
    ctx.setdefault("resume", "")
    return ctx
