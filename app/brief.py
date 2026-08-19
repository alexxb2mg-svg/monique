"""Onglet Aujourd'hui : le brief du jour, agrégé depuis le store + relances."""

from store import connexion_ro, STORE
import relances


def construire(chemin: str | None = None) -> dict:
    # FAIL-SOFT : store réel absent/illisible (fresh install, MONIQUE_STORE non branché) => brief
    # vide plutôt qu'un 500. Le vrai store, quand il est là, remplit tout normalement.
    mails = retard = 0
    try:
        con = connexion_ro(chemin or STORE)
        try:
            mails = con.execute(
                "SELECT COUNT(*) FROM sys_incoming_events WHERE processed_at IS NULL"
            ).fetchone()[0]
            retard = con.execute(
                "SELECT COUNT(*) FROM sec_taches WHERE statut!='regle' "
                "AND echeance IS NOT NULL AND echeance != '' AND echeance < date('now')"
            ).fetchone()[0]
        finally:
            con.close()
    except Exception:
        pass

    try:
        e = relances.etat()
        rel = len(e["devis"]) + len(e["factures"])
    except Exception:
        rel = 0

    phrase = (
        f"Ce matin, {mails} message(s) attendent une réponse, "
        f"{rel} relance(s) à valider, et {retard} tâche(s) en retard."
    )

    # Pouls de la brigade (ce que Monique se construit) — fail-soft, jamais un 500 sur l'accueil.
    try:
        import monitoring

        chantier = monitoring.chantier_brigade(limit=40)
    except Exception:
        chantier = {"disponible": False, "en_cours": [], "fusionnes": [], "compte": {}}

    # Santé système (registre des process) — n vivants + orphelins éventuels.
    try:
        import superviseur

        vivants = [x for x in superviseur.etat() if x.get("vivant")]
        orph = superviseur.orphelins_vivants() or []
        systeme = {
            "vivants": len(vivants),
            "orphelins": len(orph),
            "noms": [x["nom"] for x in vivants],
        }
    except Exception:
        systeme = {"vivants": 0, "orphelins": 0, "noms": []}

    return {
        "mails_a_traiter": mails,
        "relances": rel,
        "taches_retard": retard,
        "phrase": phrase,
        "chantier": chantier,
        "systeme": systeme,
    }
