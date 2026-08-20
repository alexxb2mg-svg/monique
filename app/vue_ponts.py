import time

import ponts


def contexte_ponts() -> list[dict]:
    """Construit le contexte d'affichage des ponts, sans lever d'exception."""
    try:
        etats = ponts.etat()
    except Exception:
        return []

    if not isinstance(etats, list):
        return []

    contexte = []
    for entree in etats:
        if not isinstance(entree, dict):
            continue

        d = dict(entree)  # copie superficielle pour ne jamais muter l'original

        ouvert = bool(d.get("ouvert", False))
        suivi = bool(d.get("suivi", False))

        if ouvert and suivi:
            d["libelle_etat"] = "actif"
        elif ouvert and not suivi:
            d["libelle_etat"] = "orphelin"
        else:
            d["libelle_etat"] = "ferme"

        dernier_usage = d.get("dernier_usage")
        if dernier_usage is None:
            d["dernier_usage_txt"] = "jamais utilise"
        else:
            try:
                secondes = round(time.time() - float(dernier_usage))
                if secondes < 0:
                    secondes = 0
                d["dernier_usage_txt"] = f"il y a {secondes}s"
            except (TypeError, ValueError, OverflowError):
                d["dernier_usage_txt"] = "jamais utilise"

        contexte.append(d)

    return contexte
