"""Superviseur de processus (D-16) — registre + arbre + coupe, intransigeant.

Le problème d'Alex, de toujours : des process/sous-process orphelins survivent des jours parce que
personne ne les voit. Ici : TOUT ce que Monique lance s'inscrit (nom, proprietaire, but, PID, PID
parent). À tout instant on peut voir qui tourne (et ce que c'est / à qui c'est), détecter les morts
(PID + heure de démarrage exacte, anti-PID-recyclé) ET les orphelins VIVANTS (process vivant mais
propriétaire mort), et COUPER un process + tout son sous-arbre.

SÉCURITÉ ABSOLUE : le superviseur n'agit QUE sur des PID enregistrés + leurs descendants réels.
Il ne touche JAMAIS un process tiers (Cowork, MCP, terminaux d'Alex) — ceux-là ne sont pas au registre.
"""

import subprocess
import uuid
from datetime import datetime

from entrepot import connexion_ecriture
from lease import _debut_de, _process_start, _process_vivant

_NOW = 0x08000000  # CREATE_NO_WINDOW (pas de fenêtre qui flashe)


def _n():
    return datetime.now().isoformat()


def enregistrer(pid, nom, proprietaire, but, ppid=None, chemin=None) -> str:
    """Inscrit un process lancé par Monique. Renvoie l'id de registre (à passer à finir/tuer)."""
    rid = "p" + uuid.uuid4().hex[:8]
    con = connexion_ecriture(chemin)
    try:
        con.execute(
            "INSERT INTO secw_processus(id, pid, ppid, nom, proprietaire, but, statut, "
            "process_started_at, started_at) VALUES(?,?,?,?,?,?, 'running', ?, ?)",
            (
                rid,
                int(pid),
                (int(ppid) if ppid else None),
                nom,
                proprietaire,
                but,
                _debut_de(pid),  # heure de démarrage EXACTE : anti-PID-recyclé
                _n(),
            ),
        )
        con.commit()
    finally:
        con.close()
    return rid


def finir(rid, statut="fini", chemin=None) -> None:
    """Retire un process du registre (statut terminal : fini | orphelin | tue | unknown)."""
    con = connexion_ecriture(chemin)
    try:
        con.execute(
            "UPDATE secw_processus SET statut=?, finished_at=? WHERE id=? AND statut='running'",
            (statut, _n(), rid),
        )
        con.commit()
    finally:
        con.close()


def _tous_pid_ppid() -> dict:
    """Arbre des process de la machine : {ppid: [pids enfants]}. UN seul spawn PowerShell."""
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                'Get-CimInstance Win32_Process | ForEach-Object { "$($_.ProcessId) $($_.ParentProcessId)" }',
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
            creationflags=_NOW,
        ).stdout
    except Exception:
        return {}
    enfants: dict = {}
    for ligne in out.splitlines():
        p = ligne.split()
        if len(p) == 2 and p[0].isdigit() and p[1].isdigit():
            enfants.setdefault(int(p[1]), []).append(int(p[0]))
    return enfants


def arbre(pid, enfants=None) -> list[int]:
    """PIDs de TOUS les descendants (sous-process + sous-sous-process…) de `pid`."""
    enfants = enfants if enfants is not None else _tous_pid_ppid()
    vus, pile = [], [int(pid)]
    while pile:
        for c in enfants.get(pile.pop(), []):
            if c not in vus:
                vus.append(c)
                pile.append(c)
    return vus


def etat(chemin=None) -> list[dict]:
    """Le tableau : chaque process encore 'running' au registre, avec son état RÉEL + son arbre."""
    con = connexion_ecriture(chemin)
    try:
        rows = con.execute(
            "SELECT * FROM secw_processus WHERE statut='running' ORDER BY started_at DESC"
        ).fetchall()
    finally:
        con.close()
    enfants = _tous_pid_ppid()
    out = []
    for r in rows:
        vivant = _process_vivant(r["pid"], r["process_started_at"])
        out.append(
            {
                "id": r["id"],
                "pid": r["pid"],
                "nom": r["nom"],
                "proprietaire": r["proprietaire"],
                "but": r["but"],
                "vivant": vivant,
                "depuis": r["started_at"],
                "descendants": len(arbre(r["pid"], enfants)) if vivant else 0,
            }
        )
    return out


def orphelins_vivants(chemin=None) -> list[dict]:
    """Registrés VIVANTS dont le PROPRIÉTAIRE (process parent) est PROUVÉ mort => orphelins réels
    (ils survivent pour rien). Le vrai fléau : ce sont EUX qu'il faut couper."""
    con = connexion_ecriture(chemin)
    try:
        rows = con.execute(
            "SELECT * FROM secw_processus WHERE statut='running'"
        ).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        if not r["ppid"]:
            continue
        if (
            _process_vivant(r["pid"], r["process_started_at"])
            and _process_start(r["ppid"]) == ""
        ):
            out.append(
                {
                    "id": r["id"],
                    "pid": r["pid"],
                    "nom": r["nom"],
                    "but": r["but"],
                    "ppid": r["ppid"],
                }
            )
    return out


def tuer(rid, avec_arbre=True, chemin=None) -> dict:
    """Coupe le process enregistré `rid` (+ tout son sous-arbre si avec_arbre). SÉCURITÉ : n'agit
    QUE sur un PID présent au registre. Marque le registre 'tue'."""
    con = connexion_ecriture(chemin)
    try:
        r = con.execute("SELECT pid FROM secw_processus WHERE id=?", (rid,)).fetchone()
    finally:
        con.close()
    if not r:
        return {"ok": False, "erreur": "id inconnu au registre"}
    args = ["taskkill", "/PID", str(r["pid"])] + (["/T"] if avec_arbre else []) + ["/F"]
    try:
        subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            creationflags=_NOW,
        )
        ok = True
    except Exception:
        ok = False
    finir(rid, "tue", chemin)
    return {"ok": ok, "pid": r["pid"]}


def balayer(auto_tuer=False, chemin=None) -> dict:
    """Réconciliation, à déclencher au démarrage serveur + périodiquement :
    - un 'running' dont le PID est PROUVÉ mort => 'fini' (nettoie le registre) ;
    - un orphelin VIVANT (parent mort) => signalé, et COUPÉ si auto_tuer.
    Renvoie les compteurs."""
    con = connexion_ecriture(chemin)
    try:
        rows = con.execute(
            "SELECT id, pid, process_started_at FROM secw_processus WHERE statut='running'"
        ).fetchall()
    finally:
        con.close()
    nettoyes = 0
    for r in rows:
        if not _process_vivant(r["pid"], r["process_started_at"]):  # prouvé mort
            finir(r["id"], "fini", chemin)
            nettoyes += 1
    orphelins = orphelins_vivants(chemin)
    coupes = 0
    if auto_tuer:
        for o in orphelins:
            if tuer(o["id"], avec_arbre=True, chemin=chemin).get("ok"):
                coupes += 1
    return {
        "controles": len(rows),
        "records_morts_nettoyes": nettoyes,
        "orphelins_vivants": len(orphelins),
        "coupes": coupes,
    }
