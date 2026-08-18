import re
import subprocess

import config
from entrepot import connexion_ecriture

CREATE_NO_WINDOW = 0x08000000

# Garde-fou anti-boucle (SPEC §14). CAUSE RACINE (revue A/B) : la vraie défense au câblage
# prod est un ALLOWLIST — appliquer_job ne composera JAMAIS de /tr à partir d'une cible_cmd
# libre, il n'autorise que le programme de run canonique (note M5). Ce denylist est une
# ceinture-bretelles : ANCRÉ en position de commande (_CMD) pour ne pas déclencher sur des
# sous-chaînes de flags (ex. « --no-shutdown-check »), et élargi aux variantes réelles
# (.exe, chemins, sc stop, Stop-Process, Restart/Stop-Computer, /end, wmic … delete, kill -KILL).
_CMD = r"(?:^|[\s;&|(\\/\"'])"  # début de chaîne, séparateur shell, ou préfixe de chemin/quote
_MOTIFS_DANGER = re.compile(
    _CMD + r"(?:"
    r"schtasks(?:\.exe)?[\"']?\s+/(?:create|change|delete|end)"
    r"|sc(?:\.exe)?[\"']?\s+(?:stop|start|delete|config)"
    r"|net[\"']?\s+(?:stop|start)"
    r"|(?:stop|start|restart)-service"
    r"|stop-process|taskkill(?:\.exe)?|pkill|kill\s+-(?:9|kill|sigkill)"
    r"|shutdown|restart-computer|stop-computer"
    r"|wmic\b(?=.*\bdelete\b)"
    r"|reg(?:\.exe)?[\"']?\s+(?:add|delete)|remove-item"
    r"|restart\b.*(?:secretaire|coquille|gateway)"
    r")",
    re.I,
)


def cron_vers_schtasks(planning: dict) -> list:
    k = planning.get("kind")
    if k == "daily":
        return ["/SC", "DAILY", "/ST", planning["heure"]]
    if k == "interval":
        return ["/SC", "MINUTE", "/MO", str(int(planning["minutes"]))]
    if k == "weekly":
        args = ["/SC", "WEEKLY", "/D", ",".join(planning["jours"])]
        if planning.get("heure"):
            args += ["/ST", planning["heure"]]
        return args
    raise ValueError(f"kind inconnu: {k}")


def _interroger_schtasks() -> str:
    try:
        return (
            subprocess.run(
                ["schtasks", "/query", "/fo", "LIST"],
                capture_output=True,
                text=True,
                encoding="oem",  # revue F1 : sortie console OEM (cp850 FR) — jamais le locale ni PYTHONUTF8
                errors="replace",  # (sinon UnicodeDecodeError dans le thread lecteur => stdout=None => crash)
                timeout=15,
                creationflags=CREATE_NO_WINDOW,
            ).stdout
            or ""
        )
    except Exception:
        return ""


def lister_taches() -> list:
    texte = _interroger_schtasks()
    taches, cur = [], {}
    for ligne in texte.splitlines():
        if ":" not in ligne:
            if cur:
                taches.append(cur)
                cur = {}
            continue
        cle, val = ligne.split(":", 1)
        cle, val = cle.strip().lower(), val.strip()
        if cle in ("taskname", "nom de la tâche"):
            cur["nom"] = val
        elif "next run" in cle or "prochaine" in cle:
            cur["prochaine"] = val
        elif cle in (
            "status",
            "statut",
            "état",
        ):  # revue F2 : le champ FR réel est « Statut »
            cur["statut"] = val
    if cur:
        taches.append(cur)
    return [t for t in taches if t.get("nom")]


def job_dangereux(texte: str) -> bool:
    return bool(_MOTIFS_DANGER.search(texte or ""))


def _cible_job(job_id, chemin=None):
    # revue M6 : on scanne la COMMANDE exécutée (cible_cmd), pas le libellé humain
    con = connexion_ecriture(chemin)
    try:
        r = con.execute(
            "SELECT cible_cmd FROM secw_jobs WHERE id=?", (job_id,)
        ).fetchone()
        return (r["cible_cmd"] or "") if r else ""
    finally:
        con.close()


def appliquer_job(job_id, planning_args, chemin=None) -> dict:
    if config.mode() != "prod":
        return {"applique": False, "raison": "mode_test"}
    if job_dangereux(
        _cible_job(job_id, chemin)
    ):  # revue M6 : garde sur la commande, pas l'étiquette
        return {"applique": False, "raison": "dangereux"}
    # revue M5 : NE PAS livrer de code faux. Le câblage prod reste à écrire, avec :
    #   - /tr = programme FIXE du run secrétaire (pythonw … run_secretaire), JAMAIS planning_args
    #   - planning_args = *cron_vers_schtasks(planning), ajoutés APRÈS /tr
    #   - revue M7 : traduire les jours /D en FR (LUN,MAR,MER,JEU,VEN,SAM,DIM) sur Windows FR au /create
    raise NotImplementedError(
        "câblage schtasks prod : /tr <programme fixe> + *planning_args + jours FR"
    )
