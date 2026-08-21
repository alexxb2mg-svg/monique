"""Fil de coordination PARTAGÉ entre agents Beecham (D-15) : distinct des boîtes individuelles
de `courrier.py` — ici tous les agents lisent le même fil, chacun une seule fois (`lu_par`).

Comme le courrier, toute entrée est scannée avant publication : une entrée du fil est lue par
TOUS les agents, donc sa surface d'attaque est plus large encore qu'un message individuel.

Construit via le pipeline pont, promu depuis atelier/sandbox_courrier_coordination/ le 22/08/2026."""

import json
import sqlite3
from datetime import datetime

import contrats

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS coordination (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auteur TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'note',
    corps TEXT NOT NULL,
    cree_le TEXT NOT NULL,
    lu_par TEXT NOT NULL DEFAULT '[]',
    epingle INTEGER NOT NULL DEFAULT 0,
    statut TEXT NOT NULL DEFAULT 'actif'
);
"""


def _ouvrir_connexion(chemin_db: str) -> sqlite3.Connection:
    conn = sqlite3.connect(chemin_db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def _creer_schema(connexion: sqlite3.Connection) -> None:
    connexion.execute(_SCHEMA_SQL)
    connexion.commit()


def _get_connection(chemin_db: str) -> sqlite3.Connection:
    conn = _ouvrir_connexion(chemin_db)
    _creer_schema(conn)
    return conn


def _maintenant_iso() -> str:
    return datetime.now().isoformat()


def poster_fil(
    chemin_db: str, auteur: str, corps: str, type: str = "note"
) -> int:
    """Publie une entrée dans le fil partagé. Le corps est scanné avant publication
    (`contrats.scanner_message`) — lève ValueError si le scan refuse."""
    propre, raison = contrats.scanner_message(corps)
    if not propre:
        raise ValueError(f"Entrée de fil refusée : {raison}")

    conn = _get_connection(chemin_db)
    cree_le = _maintenant_iso()
    cursor = conn.execute(
        "INSERT INTO coordination (auteur, type, corps, cree_le) VALUES (?, ?, ?, ?)",
        (auteur, type, corps, cree_le),
    )
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id


def lire_fil_non_lu(
    chemin_db: str, agent_id: str, limite: int = 50
) -> list[dict]:
    conn = _get_connection(chemin_db)
    cursor = conn.execute(
        "SELECT * FROM coordination WHERE statut = 'actif' ORDER BY id ASC"
    )
    rows = cursor.fetchall()

    resultats = []
    a_mettre_a_jour = []

    for row in rows:
        lu_par_list = json.loads(row["lu_par"])
        if agent_id not in lu_par_list:
            d = dict(row)
            lu_par_list.append(agent_id)
            d["lu_par"] = json.dumps(lu_par_list)
            resultats.append(d)
            a_mettre_a_jour.append((d["lu_par"], row["id"]))

            if len(resultats) >= limite:
                break

    for nouveau_lu_par, row_id in a_mettre_a_jour:
        conn.execute(
            "UPDATE coordination SET lu_par = ? WHERE id = ?",
            (nouveau_lu_par, row_id),
        )

    conn.commit()
    conn.close()
    return resultats


def lister_fil(
    chemin_db: str, epingle_seulement: bool = False, statut: str = "actif"
) -> list[dict]:
    conn = _get_connection(chemin_db)
    query = "SELECT * FROM coordination WHERE statut = ?"
    params = [statut]

    if epingle_seulement:
        query += " AND epingle = 1"

    query += " ORDER BY id ASC"

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def epingler_fil(chemin_db: str, id: int) -> None:
    conn = _get_connection(chemin_db)
    conn.execute(
        "UPDATE coordination SET epingle = 1 WHERE id = ?", (id,)
    )
    conn.commit()
    conn.close()


def archiver_fil(chemin_db: str, id: int) -> None:
    conn = _get_connection(chemin_db)
    conn.execute(
        "UPDATE coordination SET statut = 'archive' WHERE id = ?", (id,)
    )
    conn.commit()
    conn.close()
