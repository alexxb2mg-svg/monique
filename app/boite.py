"""Lecture de « La boîte » depuis la file unifiée sys_incoming_events (read-only).

Décision v1 (SPEC §6) : source = sys_incoming_events. Bascule éventuelle vers
INBOX.db = refinement Phase 2, à trancher avec l'utilisateur.
"""

import logging
import sqlite3

from store import connexion_ro, STORE

LOG = logging.getLogger(__name__)


def lire_event(event_id: int, chemin: str | None = None) -> dict | None:
    """Un événement en plein texte (contenu complet, pas l'aperçu tronqué).

    Sert la rédaction de brouillon : la secrétaire doit lire tout le message,
    pas 140 caractères (revue Phase 2b M2). Le spillover de cerveau gère les corps trop gros.

    FAIL-SOFT (même patron que beecham.lire_mission) : store réel absent/illisible
    (fresh install) OU contention SQLite (OperationalError) => None, jamais un 500.
    """
    try:
        con = connexion_ro(chemin or STORE)
        try:
            r = con.execute(
                "SELECT id, source, raw_content, status, timestamp, processed_at "
                "FROM sys_incoming_events WHERE id=?",
                (event_id,),
            ).fetchone()
            if not r:
                return None
            return {
                "id": r["id"],
                "source": r["source"],
                "contenu": r["raw_content"] or "",
                "status": r["status"],
                "timestamp": r["timestamp"],
                "traite": r["processed_at"] is not None,
            }
        finally:
            con.close()
    except sqlite3.OperationalError as e:
        if "lock" in str(e).lower():
            LOG.warning(
                "boite: base verrouillée (contention) sur lire_event(%s): %s",
                event_id,
                e,
            )
        return None
    except Exception:
        return None


def lire_boite(chemin: str | None = None, limite: int = 50) -> list[dict]:
    """FAIL-SOFT (même patron que beecham.lire_mission) : store réel absent/illisible
    (fresh install) OU contention SQLite (OperationalError) => boîte vide, jamais un 500.
    """
    try:
        con = connexion_ro(chemin or STORE)
        try:
            cur = con.execute(
                "SELECT id, source, raw_content, status, timestamp, processed_at "
                "FROM sys_incoming_events "
                "ORDER BY (processed_at IS NOT NULL), timestamp DESC LIMIT ?",
                (limite,),
            )
            out = []
            for r in cur.fetchall():
                contenu = r["raw_content"] or ""
                out.append(
                    {
                        "id": r["id"],
                        "source": r["source"],
                        "apercu": contenu[:140],
                        "status": r["status"],
                        "timestamp": r["timestamp"],
                        "traite": r["processed_at"] is not None,
                    }
                )
            return out
        finally:
            con.close()
    except sqlite3.OperationalError as e:
        if "lock" in str(e).lower():
            LOG.warning(
                "boite: base verrouillée (contention) sur lire_boite(): %s", e
            )
        return []
    except Exception:
        return []
