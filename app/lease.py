import os
import subprocess
from datetime import datetime
from entrepot import connexion_ecriture

_INCONNU = "?inconnu?"


def _process_start(pid):
    # revue §13.2 : TROIS états — heure de démarrage (vivant) / "" (PID absent, PROUVÉ mort) / _INCONNU (erreur-timeout)
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue).StartTime.ToString('o')",
            ],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=0x08000000,
        ).stdout.strip()
        return out  # "" si le process n'existe pas (Get-Process a réussi, sortie vide)
    except Exception:
        return _INCONNU  # PowerShell a échoué/timeout => on NE SAIT PAS (ex. Defender)


def _debut_de(pid) -> str:
    d = _process_start(pid)
    return d if (d and d != _INCONNU) else datetime.now().isoformat()


def _process_vivant(pid, started_at) -> bool:
    cur = _process_start(pid)
    if cur == _INCONNU:
        return True  # revue §13.2 : incapable de PROUVER la mort => présumer vivant (fail-safe anti vol de lease)
    if not cur:
        return False  # PID absent prouvé => mort (le lease peut être volé)
    if not started_at:
        return True  # pas de référence => prudence
    return cur == started_at  # même PID ET même heure de démarrage => vraiment vivant


def acquerir(cle: str, chemin: str | None = None) -> bool:
    con = connexion_ecriture(chemin)
    con.isolation_level = None  # transactions manuelles
    try:
        con.execute(
            "BEGIN IMMEDIATE"
        )  # revue M2 : verrou d'écriture pris AVANT le SELECT => pas de course TOCTOU
        row = con.execute(
            "SELECT owner_pid, owner_started_at FROM secw_turn_lease WHERE cle=?",
            (cle,),
        ).fetchone()
        if row and _process_vivant(row["owner_pid"], row["owner_started_at"]):
            con.execute("ROLLBACK")
            return False
        debut = _debut_de(os.getpid())  # revue §13.2 : gère les 3 états
        con.execute(
            "INSERT OR REPLACE INTO secw_turn_lease(cle, owner_pid, owner_started_at, acquired_at) "
            "VALUES(?,?,?,?)",
            (cle, os.getpid(), debut, datetime.now().isoformat()),
        )
        con.execute("COMMIT")
        return True
    finally:
        con.close()


def liberer(cle: str, chemin: str | None = None) -> None:
    con = connexion_ecriture(chemin)
    try:
        con.execute(
            "DELETE FROM secw_turn_lease WHERE cle=? AND owner_pid=?",
            (cle, os.getpid()),
        )
        con.commit()
    finally:
        con.close()
