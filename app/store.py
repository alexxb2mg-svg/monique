"""Lecture read-only du store (« le vivant »).

Aucune écriture en Phase 1. Toutes les connexions sont ouvertes en mode=ro.
Le chemin du store vient de config (variable d'environnement MONIQUE_STORE) — jamais en dur.
"""

import sqlite3
import logging

import config

LOG = logging.getLogger(__name__)

STORE = config.REEL


def chemin_store() -> str:
    return STORE


def connexion_ro(chemin: str) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
    con.execute("PRAGMA busy_timeout=8000")
    con.row_factory = sqlite3.Row
    return con


def lire_taches(
    kind: str, chemin: str | None = None, chemin_overlay: str | None = None
) -> list[dict]:
    """Tâches non réglées d'un type donné (a_faire|relance|rdv|devis).

    Tri repris du dashboard existant : confiance décroissante puis id décroissant.
    """
    chemin = chemin or STORE
    # FAIL-SOFT : store réel absent/illisible (fresh install) => liste vide, jamais un 500.
    try:
        con = connexion_ro(chemin)
        try:
            cur = con.execute(
                "SELECT * FROM sec_taches WHERE type=? AND statut!='regle' "
                "ORDER BY confiance DESC, id DESC",
                (kind,),
            )
            rows = [dict(r) for r in cur.fetchall()]
        finally:
            con.close()
    except sqlite3.OperationalError as e:
        if "lock" in str(e).lower():
            LOG.warning("store: base verrouillée (contention) sur %s: %s", chemin, e)
        return []
    except Exception:
        return []

    # Fusion overlay (Phase 2b) : une tâche cochée (secw_taches_overlay, statut='regle') est exclue.
    # L'overlay vit dans la base d'ÉCRITURE (shadow en test, réel en prod) — là où `cocher_tache`
    # écrit — pas forcément le même fichier que sec_taches (revue Fable 5).
    # FAIL-SOFT STRICT : table/fichier absent (ex. fixtures Phase 1) => on ne filtre rien.
    try:
        from config import chemin_ecriture

        ov = chemin_overlay or chemin_ecriture()
        con2 = connexion_ro(ov)
        try:
            regles = {
                r["tache_id"]
                for r in con2.execute(
                    "SELECT tache_id FROM secw_taches_overlay WHERE statut='regle'"
                )
            }
        finally:
            con2.close()
        if regles:
            rows = [r for r in rows if r["id"] not in regles]
    except Exception:
        pass  # overlay absent/illisible => ne rien filtrer (Phase 1 reste intacte)

    return rows
