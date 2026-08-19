import json

import beecham


def contexte_missions_actives(chemin=None) -> list[dict]:
    """Missions en cours (statut='en_cours'), flux d'actions décodé pour affichage direct.

    Lecture seule, jamais de mutation. Le journal est stocké en JSON (chaîne) en base ;
    décodé ICI (fail-soft : une valeur absente/invalide ne doit jamais faire planter la vue).
    """
    missions = beecham.lister_missions(chemin, limit=50)
    actives = []
    for m in missions:
        if m.get("statut") != "en_cours":
            continue
        d = dict(m)
        try:
            d["journal_liste"] = json.loads(d.get("journal") or "[]")
        except (TypeError, ValueError):
            d["journal_liste"] = []
        actives.append(d)
    return actives
