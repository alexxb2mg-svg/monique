"""Overlays shadow (Phase 2b) : statuts de tâches cochées et brouillons.

Tout passe par entrepot.connexion_ecriture() -> chemin_ecriture() (jamais le store réel).
"""

import json
from datetime import datetime

from entrepot import connexion_ecriture


def cocher_tache(tache_id, par="alex", chemin=None) -> None:
    con = connexion_ecriture(chemin)
    try:
        con.execute(
            "INSERT OR REPLACE INTO secw_taches_overlay(tache_id, statut, cloture_par, cloture_le) "
            "VALUES(?, 'regle', ?, ?)",
            (tache_id, par, datetime.now().isoformat()),
        )
        con.commit()
    finally:
        con.close()


def statut_tache(tache_id, chemin=None):
    con = connexion_ecriture(chemin)
    try:
        r = con.execute(
            "SELECT statut FROM secw_taches_overlay WHERE tache_id=?", (tache_id,)
        ).fetchone()
        return r["statut"] if r else None
    finally:
        con.close()


def enregistrer_brouillon(
    event_id, canal, contexte, brouillon, attendu, hors, chemin=None
) -> str:
    con = connexion_ecriture(chemin)
    try:
        now = datetime.now().isoformat()
        bid = f"b{event_id}"
        con.execute(
            """
          INSERT INTO secw_brouillons(id, event_id, canal, contexte, brouillon, attendu_json, hors_json, cree_le, maj_le)
          VALUES(?,?,?,?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET brouillon=excluded.brouillon, contexte=excluded.contexte,
            attendu_json=excluded.attendu_json, hors_json=excluded.hors_json, maj_le=excluded.maj_le
        """,
            (
                bid,
                event_id,
                canal,
                contexte,
                brouillon,
                json.dumps(attendu, ensure_ascii=False),
                json.dumps(hors, ensure_ascii=False),
                now,
                now,
            ),
        )
        con.commit()
        return bid
    finally:
        con.close()


def lire_brouillon(event_id, chemin=None):
    con = connexion_ecriture(chemin)
    try:
        r = con.execute(
            "SELECT * FROM secw_brouillons WHERE event_id=?", (event_id,)
        ).fetchone()
        if not r:
            return None
        return {
            "id": r["id"],
            "brouillon": r["brouillon"],
            "contexte": r["contexte"],
            "attendu": json.loads(r["attendu_json"] or "[]"),
            "hors": json.loads(r["hors_json"] or "[]"),
            "statut": r["statut"],
        }
    finally:
        con.close()
