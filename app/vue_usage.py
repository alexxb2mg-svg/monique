import sqlite3

from config import chemin_ecriture


def contexte_usage(chemin=None) -> list[dict]:
    """Usage agrégé PAR AGENT (tokens, appels, coût), lecture seule, fail-soft.

    Même modèle que usage.py::total() : connexion RO sur la write-DB courante,
    jamais connexion_ecriture dans un chemin de lecture (SPEC §16 — pas de 500
    sur une vue). Table/fichier absent, ou toute autre exception => liste vide.

    Honnêteté épistémique : le cost_status agrégé d'un agent vaut 'unknown' dès
    qu'UN SEUL de ses enregistrements est 'unknown' (jamais présenter un total
    comme fiable si une partie de son calcul ne l'est pas). S'ils sont tous
    identiques (et non 'unknown'), l'agrégé garde ce statut commun. Dans le cas
    restant — mélange non homogène de statuts connus (ex: 'included' et
    'estimated') — l'agrégé retombe aussi sur 'unknown' par prudence : un total
    unique ne peut pas représenter fidèlement deux statuts différents à la fois.
    """
    cible = chemin or chemin_ecriture()
    try:
        con = sqlite3.connect(f"file:{cible}?mode=ro", uri=True, timeout=8)
        con.row_factory = sqlite3.Row
        try:
            lignes = con.execute(
                "SELECT agent, input_tokens, output_tokens, calls, "
                "estimated_cost_usd, cost_status FROM secw_model_usage"
            ).fetchall()
        finally:
            con.close()
    except Exception:
        return []

    par_agent = {}
    for l in lignes:
        agrege = par_agent.setdefault(
            l["agent"],
            {
                "agent": l["agent"],
                "input_tokens": 0,
                "output_tokens": 0,
                "calls": 0,
                "estimated_cost_usd": 0.0,
                "_statuts": set(),
            },
        )
        agrege["input_tokens"] += l["input_tokens"] or 0
        agrege["output_tokens"] += l["output_tokens"] or 0
        agrege["calls"] += l["calls"] or 0
        agrege["estimated_cost_usd"] += l["estimated_cost_usd"] or 0.0
        agrege["_statuts"].add(l["cost_status"])

    resultat = []
    for agrege in par_agent.values():
        statuts = agrege.pop("_statuts")
        if "unknown" in statuts or len(statuts) != 1:
            agrege["cost_status"] = "unknown"
        else:
            agrege["cost_status"] = next(iter(statuts))
        resultat.append(agrege)

    resultat.sort(key=lambda d: d["agent"])
    return resultat
