import os
from datetime import datetime
from entrepot import connexion_ecriture
from lease import (
    _debut_de,
    _process_vivant,
)  # détection Windows partagée (revue §13.2, 3 états)

TERMINAL = ("completed", "failed", "unknown")


def creer(id_: str, agent: str, chemin=None) -> None:
    con = connexion_ecriture(chemin)
    try:
        now = datetime.now().isoformat()
        deb = _debut_de(
            os.getpid()
        )  # vraie heure de démarrage (revue §13.2) pour que la reprise compare juste
        con.execute(
            "INSERT OR IGNORE INTO secw_executions(id, agent, statut, pid, process_started_at, started_at) "
            "VALUES(?,?, 'claimed', ?, ?, ?)",
            (id_, agent, os.getpid(), deb, now),
        )
        con.commit()
    finally:
        con.close()


def marquer_en_cours(id_: str, chemin=None) -> None:
    con = connexion_ecriture(chemin)
    try:
        con.execute(
            "UPDATE secw_executions SET statut='running' WHERE id=? AND statut='claimed'",
            (id_,),
        )
        con.commit()
    finally:
        con.close()


def finir(
    id_: str, statut: str, resultat="", delivery_outcome=None, chemin=None
) -> None:
    con = connexion_ecriture(chemin)
    try:
        con.execute(
            "UPDATE secw_executions SET statut=?, resultat=?, delivery_outcome=?, finished_at=? "
            "WHERE id=? AND statut IN ('claimed','running')",  # terminal immuable
            (statut, resultat, delivery_outcome, datetime.now().isoformat(), id_),
        )
        con.commit()
    finally:
        con.close()


def reprendre_interrompues(chemin=None) -> int:
    con = connexion_ecriture(chemin)
    try:
        rows = con.execute(
            "SELECT id, pid, process_started_at FROM secw_executions WHERE statut IN ('claimed','running')"
        ).fetchall()
        n = 0
        for r in rows:
            if not _process_vivant(r["pid"], r["process_started_at"]):  # prouvé mort
                con.execute(
                    "UPDATE secw_executions SET statut='unknown', finished_at=? WHERE id=?",
                    (datetime.now().isoformat(), r["id"]),
                )
                n += 1
        con.commit()
        return n
    finally:
        con.close()
