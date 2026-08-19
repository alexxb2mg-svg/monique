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
    return {
        "mails_a_traiter": mails,
        "relances": rel,
        "taches_retard": retard,
        "phrase": phrase,
    }
