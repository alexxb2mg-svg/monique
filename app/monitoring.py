"""Onglet Monitoring : état du moteur de collecte (read-only)."""

from store import connexion_ro, STORE


def etat_moteur(chemin: str | None = None) -> dict:
    con = connexion_ro(chemin or STORE)
    try:
        dernier = con.execute(
            "SELECT value FROM sys_constants WHERE key='collector_last_run'"
        ).fetchone()
        a_traiter = con.execute(
            "SELECT COUNT(*) FROM sys_incoming_events WHERE processed_at IS NULL"
        ).fetchone()[0]
        jour = con.execute(
            "SELECT COUNT(*) FROM sys_incoming_events WHERE date(timestamp)=date('now')"
        ).fetchone()[0]
        return {
            "collecte_active": dernier is not None,
            "dernier_passage": dernier[0] if dernier else None,
            "entrees_jour": jour,
            "a_traiter": a_traiter,
        }
    finally:
        con.close()
