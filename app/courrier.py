"""Boîte de réception PAR AGENT (D-15) : chaque persona a sa propre boîte, clé `destinataire`.
Distinct de `boite.py`, qui est LA boîte secrétariat côté humain.

Tout message est scanné par `contrats.scanner_message` AVANT insertion — un message déposé ici
sera injecté dans le contexte du destinataire, donc le contenu est une surface d'attaque
(injection de prompt, caractères invisibles). Voir proposition_d15_consolidee.md addendums 9 et 13.

Construit via le pipeline pont, promu depuis atelier/sandbox_courrier_coordination/ le 22/08/2026."""

from datetime import datetime, timezone
import sqlite3

import contrats

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS courrier (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    destinataire TEXT NOT NULL,
    expediteur TEXT NOT NULL,
    sujet TEXT NOT NULL,
    corps TEXT NOT NULL,
    statut TEXT NOT NULL DEFAULT 'non_lu',
    cree_le TEXT NOT NULL,
    lu_le TEXT NULL,
    traite_le TEXT NULL,
    session_id TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_courrier_destinataire_statut
ON courrier (destinataire, statut);
"""


def _ouvrir_connexion(chemin_db: str) -> sqlite3.Connection:
    """Ouvre une connexion SQLite, active PRAGMA journal_mode=WAL et définit row_factory."""
    conn = sqlite3.connect(chemin_db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def _creer_schema(conn: sqlite3.Connection) -> None:
    """Exécute les instructions de création de table et d'index si elles n'existent pas."""
    with conn:
        conn.executescript(SCHEMA_SQL)


def _get_connection(chemin_db: str) -> sqlite3.Connection:
    """Initialise la connexion SQLite et crée le schéma de façon idempotente."""
    conn = _ouvrir_connexion(chemin_db)
    _creer_schema(conn)
    return conn


def deposer_courrier(
    chemin_db: str,
    destinataire: str,
    expediteur: str,
    sujet: str,
    corps: str,
    session_id: str | None = None,
) -> int:
    """Dépose un courrier avec le statut 'non_lu', l'horodatage ISO courant et retourne son ID.

    Le sujet ET le corps sont scannés avant insertion (`contrats.scanner_message`) : un message
    accepté ici finira injecté dans le contexte du destinataire. Lève ValueError si le scan
    refuse — un message dangereux n'entre jamais dans la boîte, plutôt que d'y dormir en attente.
    """
    for champ, valeur in (("sujet", sujet), ("corps", corps)):
        propre, raison = contrats.scanner_message(valeur)
        if not propre:
            raise ValueError(f"Courrier refusé ({champ}) : {raison}")

    conn = _get_connection(chemin_db)
    maintenant = datetime.now(timezone.utc).isoformat()

    with conn:
        cursor = conn.execute(
            """
            INSERT INTO courrier (destinataire, expediteur, sujet, corps, cree_le, session_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (destinataire, expediteur, sujet, corps, maintenant, session_id),
        )
        msg_id = cursor.lastrowid

    conn.close()
    return msg_id


def relever_courrier(
    chemin_db: str, destinataire: str, limite: int = 20
) -> list[dict]:
    """Sélectionne les courriers 'non_lu' par ordre chronologique, les passe à 'lu' avec lu_le=maintenant et renvoie leurs dicts {id, expediteur, sujet, corps, cree_le}."""
    conn = _get_connection(chemin_db)
    maintenant = datetime.now(timezone.utc).isoformat()

    with conn:
        cursor = conn.execute(
            """
            SELECT id, expediteur, sujet, corps, cree_le
            FROM courrier
            WHERE destinataire = ? AND statut = 'non_lu'
            ORDER BY id ASC
            LIMIT ?
            """,
            (destinataire, limite),
        )
        rows = cursor.fetchall()

        if rows:
            ids = [row["id"] for row in rows]
            placeholders = ",".join("?" * len(ids))
            conn.execute(
                f"""
                UPDATE courrier
                SET statut = 'lu', lu_le = ?
                WHERE id IN ({placeholders})
                """,
                [maintenant] + ids,
            )

    conn.close()
    return [dict(row) for row in rows]


def archiver_courrier(
    chemin_db: str, destinataire: str, ids: list[int]
) -> None:
    """Passe le statut des messages spécifiés à 'archive' avec traite_le=maintenant, uniquement pour le destinataire donné."""
    if not ids:
        return

    conn = _get_connection(chemin_db)
    maintenant = datetime.now(timezone.utc).isoformat()
    placeholders = ",".join("?" * len(ids))

    with conn:
        conn.execute(
            f"""
            UPDATE courrier
            SET statut = 'archive', traite_le = ?
            WHERE destinataire = ? AND id IN ({placeholders})
            """,
            [maintenant, destinataire] + list(ids),
        )

    conn.close()


def lister_courrier(
    chemin_db: str, destinataire: str | None = None, statut: str = "non_lu"
) -> list[dict]:
    """Lecture seule : renvoie tous les champs des courriers filtrés par statut et optionnellement par destinataire."""
    conn = _get_connection(chemin_db)

    query = "SELECT * FROM courrier WHERE statut = ?"
    params = [statut]

    if destinataire is not None:
        query += " AND destinataire = ?"
        params.append(destinataire)

    query += " ORDER BY id ASC"

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    conn.close()
    return [dict(row) for row in rows]
