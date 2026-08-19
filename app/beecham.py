"""Beecham — le chef d'orchestre qui fait évoluer Monique (missions GARDÉES).

Sécurité (le cœur) :
  - Le travail réel se fait dans une BRANCHE GIT JETABLE via un worktree isolé, HORS du
    dépôt principal — jamais sur le vrai store ni les données métier.
  - Les agents codeurs tournent SANS Bash (Read/Edit/Write/Glob/Grep uniquement), scopés
    au worktree (`claude --allowedTools ... --strict-mcp-config`). Ils touchent du CODE,
    rien d'autre. Ils ne peuvent pas exécuter de commande arbitraire.
  - Le HARNAIS (ce module, déterministe) lance les tests + le diff. Pas les agents.
  - L'utilisateur VALIDE avant toute fusion/déploiement. Rien n'est automatique.

Beecham conduit des agents-personas (développeur, chercheur, contrôleur) et peut proposer
de nouveaux agents (nommés dans l'esprit de la brigade) — créés seulement après validation.
"""

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

from entrepot import connexion_ecriture

RACINE = Path(__file__).resolve().parent.parent  # dépôt Monique (secretaire/)
WORKTREES = RACINE.parent / ".beecham_worktrees"  # hors dépôt, jamais versionné
# Atelier partagé : le tableau blanc des agents (notes, plans, messages, trouvailles) ET la
# fenêtre d'observation de l'utilisateur. Page blanche : Beecham l'organise comme il veut.
# Zone d'écriture LIBRE autorisée (avec la branche de code) ; tout le reste est refusé.
ATELIER = RACINE.parent / "atelier"


def init_atelier() -> Path:
    ATELIER.mkdir(parents=True, exist_ok=True)
    accueil = ATELIER / "LISEZMOI.md"
    if not accueil.exists():
        accueil.write_text(
            "# Atelier de Beecham\n\n"
            "Espace de travail et de communication partagé de la brigade.\n"
            "Écrivez ici librement : notes, plans, trouvailles, messages entre agents.\n"
            "Organisez-le comme bon vous semble — c'est votre page blanche.\n\n"
            "Rappel de la SEULE règle inviolable : aucune écriture hors de cet atelier et de\n"
            "la branche de code. Les dossiers de production se LISENT (inspiration), ne se\n"
            "touchent JAMAIS. Toute action sur la production est fictive, décrite ici.\n",
            encoding="utf-8",
        )
    return ATELIER


def zone_ecriture_autorisee(chemin: str, zones: list[str]) -> bool:
    """LE garde-fou (logique) : une écriture n'est permise que SOUS l'une des zones autorisées
    (worktree de la mission + atelier). Tout le reste — dossiers de production inclus — est REFUSÉ.
    Deny-by-default : chemin illisible/hors zone => False. Comparaison normalisée (casse + realpath),
    anti-`..` (realpath résout les remontées)."""
    try:
        cible = os.path.normcase(os.path.realpath(chemin))
    except Exception:
        return False
    for z in zones:
        if not z:
            continue
        base = os.path.normcase(os.path.realpath(z))
        if cible == base or cible.startswith(base + os.sep):
            return True
    return False


GARDE_DIR = (
    RACINE.parent / ".beecham_garde"
)  # substrat hors dépôt : hors de portée des agents

_GARDE_PY = '''#!/usr/bin/env python3
"""Garde-fou d'ecriture de Beecham (hook PreToolUse). NE PAS EDITER (hors depot).
Refuse toute ecriture hors des zones BEECHAM_ZONES (os.pathsep). Deny-by-default."""
import json, os, sys

def _autorise(chemin, zones):
    try:
        cible = os.path.normcase(os.path.realpath(chemin))
    except Exception:
        return False
    for z in zones:
        if not z:
            continue
        base = os.path.normcase(os.path.realpath(z))
        if cible == base or cible.startswith(base + os.sep):
            return True
    return False

try:
    data = json.load(sys.stdin)
except Exception:
    print("garde-fou: entree illisible -> refus", file=sys.stderr)
    sys.exit(2)
outil = data.get("tool_name", "")
if outil not in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
    sys.exit(0)
ti = data.get("tool_input") or {}
fp = ti.get("file_path") or ti.get("notebook_path") or ""
zones = [z for z in os.environ.get("BEECHAM_ZONES", "").split(os.pathsep) if z]
if not _autorise(fp, zones):
    raison = ("REFUSE: ecriture hors zone autorisee (%s). Seuls la branche de code et "
              "l'atelier sont accessibles en ecriture. La production ne se touche jamais." % fp)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
          "permissionDecision": "deny", "permissionDecisionReason": raison}}))
    print(raison, file=sys.stderr)
    sys.exit(2)
sys.exit(0)
'''


def _ecrire_garde() -> Path:
    """Écrit le garde-fou + les settings de hook dans le substrat (HORS dépôt, donc hors des
    zones où les agents peuvent écrire). Renvoie le chemin du settings pour `claude --settings`."""
    GARDE_DIR.mkdir(parents=True, exist_ok=True)
    garde = GARDE_DIR / "garde.py"
    garde.write_text(_GARDE_PY, encoding="utf-8")
    settings = GARDE_DIR / "settings.json"
    conf = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit|MultiEdit|NotebookEdit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": f'python "{garde}"',
                            "timeout": 30,
                        }
                    ],
                }
            ]
        }
    }
    settings.write_text(json.dumps(conf), encoding="utf-8")
    return settings


def lister_atelier() -> list[dict]:
    """Contenu de l'atelier (pour l'observer). Lecture seule, fail-soft."""
    if not ATELIER.exists():
        return []
    out = []
    for p in sorted(ATELIER.rglob("*")):
        if p.is_file():
            try:
                taille = p.stat().st_size
            except OSError:
                taille = 0
            out.append(
                {
                    "chemin": str(p.relative_to(ATELIER)).replace("\\", "/"),
                    "octets": taille,
                }
            )
    return out


# Windows only : évite le flash de console. 0 ailleurs (le CI tourne sous Linux) — sinon
# subprocess lève « creationflags is only supported on Windows ».
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Agents que Beecham peut missionner (avatars déjà présents). Read/Edit only, jamais Bash.
ROLES = {
    "developpeur": "Tu es le développeur de Monique. Tu écris et modifies le code proprement, "
    "en suivant les conventions du dépôt (français, style existant). Tu ne touches QUE le code.",
    "chercheur": "Tu es le chercheur. Tu investigues le code et la documentation du dépôt et "
    "tu synthétises ce que tu trouves. Tu ne modifies rien sans qu'on te le demande.",
    "controleur": "Tu es le contrôleur qualité. Tu relis le code de façon adversariale et tu "
    "signales les défauts, sans complaisance.",
}
_OUTILS_AGENT = (
    "Read,Edit,Write,Glob,Grep"  # JAMAIS Bash : le harnais lance les tests, pas l'agent
)


def _git(cwd, *args, timeout=120):
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=CREATE_NO_WINDOW,
    )


def _now():
    return datetime.now().isoformat()


def _maj(mission_id, chemin=None, **champs):
    con = connexion_ecriture(chemin)
    try:
        sets = ", ".join(f"{k}=?" for k in champs)
        con.execute(
            f"UPDATE secw_beecham_missions SET {sets}, maj_le=? WHERE id=?",
            (*champs.values(), _now(), mission_id),
        )
        con.commit()
    finally:
        con.close()


def lire_mission(mission_id, chemin=None) -> dict | None:
    con = connexion_ecriture(chemin)
    try:
        r = con.execute(
            "SELECT * FROM secw_beecham_missions WHERE id=?", (mission_id,)
        ).fetchone()
        return dict(r) if r else None
    finally:
        con.close()


def lister_missions(chemin=None, limit=20) -> list[dict]:
    """Missions récentes (plus récentes d'abord). Lecture seule, jamais de mutation."""
    con = connexion_ecriture(chemin)
    try:
        rows = con.execute(
            "SELECT * FROM secw_beecham_missions ORDER BY cree_le DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def demarrer_mission(consigne, chemin=None) -> str:
    mid = "m" + uuid.uuid4().hex[:8]
    con = connexion_ecriture(chemin)
    try:
        con.execute(
            "INSERT INTO secw_beecham_missions(id, consigne, statut, branche, journal, cree_le, maj_le) "
            "VALUES(?,?,?,?,?,?,?)",
            (mid, consigne, "en_cours", f"beecham/{mid}", "[]", _now(), _now()),
        )
        con.commit()
    finally:
        con.close()
    return mid


def _creer_worktree(branche) -> Path:
    WORKTREES.mkdir(parents=True, exist_ok=True)
    wt = WORKTREES / branche.replace("/", "_")
    if wt.exists():
        _git(RACINE, "worktree", "remove", "--force", str(wt))
    _git(RACINE, "branch", "-D", branche)  # au cas où la branche traîne
    r = _git(RACINE, "worktree", "add", "-b", branche, str(wt), "HEAD")
    if r.returncode != 0:
        raise RuntimeError(f"worktree: {r.stderr.strip()[:200]}")
    return wt


def _lancer_agent(role, consigne, worktree) -> dict:
    """Session codeur SCOPÉE : Read/Edit/Write only (pas de Bash), cwd=worktree, aucun MCP.
    Renvoie {ok, journal:[actions], texte}. Mockable en test."""
    systeme = ROLES.get(role, ROLES["developpeur"])
    prompt = (
        f"{consigne}\n\n"
        "Tu travailles dans une COPIE ISOLÉE du dépôt Monique. Modifie uniquement les fichiers "
        "nécessaires, proprement. Ne lance aucune commande (tu n'as pas de shell) : les tests "
        "seront lancés automatiquement après toi. Réponds par un court résumé de ce que tu as fait."
    )
    settings = (
        _ecrire_garde()
    )  # garde-fou d'écriture (hors dépôt) : refuse tout hors zones
    env = dict(os.environ)
    env["BEECHAM_ZONES"] = os.pathsep.join(
        [str(Path(worktree).resolve()), str(ATELIER.resolve())]
    )
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        "sonnet",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        _OUTILS_AGENT,
        "--strict-mcp-config",
        "--settings",
        str(settings),
        "--append-system-prompt",
        systeme,
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(worktree),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1800,
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception as e:
        return {
            "ok": False,
            "journal": [f"agent {role}: échec ({type(e).__name__})"],
            "texte": "",
        }
    journal, texte = [], ""
    for ligne in (proc.stdout or "").splitlines():
        try:
            ev = json.loads(ligne)
        except Exception:
            continue
        if ev.get("type") == "assistant":
            for bloc in ev.get("message", {}).get("content", []):
                if bloc.get("type") == "tool_use":
                    cible = (
                        bloc.get("input", {}).get("file_path")
                        or bloc.get("input", {}).get("pattern")
                        or ""
                    )
                    journal.append(
                        f"{role} · {bloc.get('name')} {Path(str(cible)).name if cible else ''}".strip()
                    )
                elif bloc.get("type") == "text":
                    texte += bloc.get("text", "")
        elif ev.get("type") == "result":
            texte = ev.get("result", texte)
    return {"ok": proc.returncode == 0, "journal": journal, "texte": texte}


def _harnais(worktree) -> dict:
    """Déterministe : lance les tests + le diff DANS le worktree. Jamais l'agent."""
    py = subprocess.run(
        ["python", "-m", "pytest", "-q"],
        cwd=str(worktree / "app"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        creationflags=CREATE_NO_WINDOW,
    )
    derniere = (py.stdout or "").strip().splitlines()[-1] if py.stdout else ""
    _git(
        worktree, "add", "-A"
    )  # inclure les fichiers NEUFs dans le diff (sinon invisibles)
    diff = _git(worktree, "diff", "--cached").stdout
    fichiers = (
        _git(worktree, "diff", "--cached", "--name-only").stdout.strip().splitlines()
    )
    return {
        "tests_ok": py.returncode == 0,
        "tests_resume": derniere,
        "diff": diff,
        "fichiers": fichiers,
    }


def executer_mission(mission_id, role="developpeur", chemin=None, _agent=None) -> dict:
    """Crée la branche, missionne un agent, passe le harnais, met la mission en `propose`."""
    m = lire_mission(mission_id, chemin)
    if not m:
        return {"ok": False, "erreur": "mission_absente"}
    agent = _agent or _lancer_agent  # injectable en test
    try:
        wt = _creer_worktree(m["branche"])
    except Exception as e:
        _maj(mission_id, chemin, statut="echec", journal=json.dumps([str(e)]))
        return {"ok": False, "erreur": str(e)}
    res = agent(role, m["consigne"], wt)
    h = _harnais(wt)
    journal = res.get("journal", []) + [f"harnais · tests: {h['tests_resume'] or '?'}"]
    _maj(
        mission_id,
        chemin,
        statut="propose",
        agents_json=json.dumps([role], ensure_ascii=False),
        journal=json.dumps(journal, ensure_ascii=False),
        diff=h["diff"],
        tests_json=json.dumps(
            {
                "ok": h["tests_ok"],
                "resume": h["tests_resume"],
                "fichiers": h["fichiers"],
            },
            ensure_ascii=False,
        ),
    )
    return {
        "ok": True,
        "tests_ok": h["tests_ok"],
        "fichiers": h["fichiers"],
        "journal": journal,
    }


def valider(mission_id, chemin=None) -> dict:
    """Fusionne la branche de la mission dans main. (Redéploiement = étape séparée.)"""
    m = lire_mission(mission_id, chemin)
    if not m or m["statut"] != "propose":
        return {"ok": False, "erreur": "statut_invalide"}
    wt = WORKTREES / m["branche"].replace("/", "_")
    _git(wt, "add", "-A")
    _git(
        wt,
        "-c",
        "user.name=beecham",
        "-c",
        "user.email=beecham@users.noreply.github.com",
        "commit",
        "-m",
        f"beecham: {m['consigne'][:60]}",
    )
    r = _git(
        RACINE, "merge", "--no-ff", "-m", f"beecham: {m['consigne'][:60]}", m["branche"]
    )
    _nettoyer(m["branche"], wt)
    ok = r.returncode == 0
    _maj(mission_id, chemin, statut="valide" if ok else "echec")
    return {"ok": ok, "erreur": None if ok else r.stderr.strip()[:200]}


def rejeter(mission_id, chemin=None) -> dict:
    m = lire_mission(mission_id, chemin)
    if not m:
        return {"ok": False, "erreur": "mission_absente"}
    _nettoyer(m["branche"], WORKTREES / m["branche"].replace("/", "_"))
    _maj(mission_id, chemin, statut="rejete")
    return {"ok": True}


def _nettoyer(branche, worktree):
    _git(RACINE, "worktree", "remove", "--force", str(worktree))
    _git(RACINE, "branch", "-D", branche)
