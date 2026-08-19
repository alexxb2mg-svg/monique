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
import unicodedata
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
# Mémoire entre les missions (cf. atelier/01_organisation.md §a) : un digest append-only
# (journal.md), un backlog priorisé (plan.md) et une note par agent-persona (memoire/<agent>.md).
MEMOIRE = ATELIER / "memoire"
JOURNAL = ATELIER / "journal.md"
PLAN = ATELIER / "plan.md"


def init_atelier() -> Path:
    ATELIER.mkdir(parents=True, exist_ok=True)
    (ATELIER / "memoire").mkdir(parents=True, exist_ok=True)
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
    if not (ATELIER / "journal.md").exists():
        (ATELIER / "journal.md").write_text(
            "# Journal\n\n"
            "Digest humain, append-only — une ligne par mission terminée. La trace complète\n"
            "(consigne, diff, tests) reste dans `secw_beecham_missions` (`lister_missions`).\n"
            "Jamais réécrit, seulement complété.\n\n",
            encoding="utf-8",
        )
    if not (ATELIER / "plan.md").exists():
        (ATELIER / "plan.md").write_text(
            "# Plan\n\n"
            "Backlog priorisé des prochains pas, chacun avec son pourquoi-maintenant en une\n"
            "ligne.\n\n",
            encoding="utf-8",
        )
    return ATELIER


def journal_ajouter(agent, resume, statut) -> None:
    """Ajoute une ligne datée à journal.md (append-only, jamais réécrit). Fail-soft : une
    erreur d'écriture (ex. disque plein) ne doit jamais faire échouer une mission."""
    init_atelier()
    ligne = f"- {_now()} · {agent} · {resume} · {statut}\n"
    try:
        with open(ATELIER / "journal.md", "a", encoding="utf-8") as f:
            f.write(ligne)
    except OSError:
        pass


def chemin_memoire(role) -> Path:
    """Chemin de la note mémoire d'un agent-persona (atelier/memoire/<role>.md), créée avec
    un en-tête si elle manque."""
    init_atelier()
    fichier = ATELIER / "memoire" / f"{role}.md"
    if not fichier.exists():
        fichier.write_text(
            f"# Mémoire — {role}\n\n"
            "Conventions du dépôt observées, pièges déjà rencontrés, décisions déjà prises —\n"
            "à relire au début d'une mission, à compléter à la fin.\n\n",
            encoding="utf-8",
        )
    return fichier


def _graver_lecon_rejet(consigne, raison) -> None:
    """Grave la leçon d'un rejet DÉFINITIF du contrôleur dans la mémoire du développeur
    (atelier/memoire/developpeur.md) — seul verdict où l'approche est jugée mauvaise et
    vaut la peine d'être évitée la prochaine fois. Fail-soft : une erreur d'écriture ne
    doit jamais faire échouer la mission, même principe que `journal_ajouter`."""
    try:
        with open(chemin_memoire("developpeur"), "a", encoding="utf-8") as f:
            f.write(f"- {_now()} · rejet : {consigne[:80]} · raison : {raison[:200]}\n")
    except OSError:
        pass


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
    "chef": "Tu es Beecham, le chef d'orchestre de Monique. Tu ne codes pas toi-même : tu observes "
    "l'état de l'entreprise, tu réfléchis à sa bonne marche (mémoire, journal, communication, "
    "planification) et tu proposes les prochains pas — missions, nouveaux agents, règles. Tu "
    "PROPOSES toujours ; Alex valide. Petit pas par petit pas, chaque décision réfléchie.",
    "auditeur": "Tu es l'auditeur de la brigade, pair de Beecham (Direction). Ton métier : des "
    "BILANS HONNÊTES et sans complaisance, à partir de MESURES (taux de réussite, tokens brûlés pour "
    "rien, missions rejetées, conflits, collisions de fichiers). Tu juges l'EFFICACITÉ et "
    "l'ORGANISATION — pas le code : ce qui a marché, ce qui a échoué, où c'est du gâchis, POURQUOI. "
    "Puis tu imposes à Beecham des MESURES D'ORGANISATION concrètes pour corriger (process, "
    "découpage, qui décide quoi). Tu ne flattes jamais ; tu chiffres et tu tranches.",
    "stratege": "Tu es le stratège de la brigade, adjoint de Beecham (Direction). Ton métier : "
    "proposer des STRATÉGIES et des DIRECTIONS pour faire avancer Monique efficacement — tu "
    "n'exécutes pas, tu ne codes pas. Tu pars des bilans de l'auditeur et du cap d'Alex, et tu "
    "proposes le PROCESS (découpage, qui décide quoi, ordre des priorités) et les grandes "
    "orientations. Tu ALLÈGES Beecham : tu penses la stratégie pour qu'il décide sans noyer son "
    "contexte. Tu proposes ; Beecham tranche.",
    "developpeur": "Tu es le développeur de Monique. Tu écris et modifies le code proprement, "
    "en suivant les conventions du dépôt (français, style existant). Tu ne touches QUE le code.",
    "chercheur": "Tu es le chercheur. Tu investigues le code et la documentation du dépôt et "
    "tu synthétises ce que tu trouves. Tu ne modifies rien sans qu'on te le demande.",
    "controleur": "Tu es le contrôleur qualité. Tu relis le code de façon adversariale (cherche ce "
    "qui casserait) et tu signales les défauts sans complaisance. Tu vérifies AUSSI l'arbre git : "
    "messages de commit sans identité ni chemin de poste, aucun code rejeté fusionné, diff conforme "
    "au scope annoncé. Tout écart, tu le signales pour correction.",
    "veilleur": "Tu es le veilleur, l'administrateur système de la brigade. Tu surveilles que tout "
    "se passe comme prévu : intégrité de l'arbre git, état du dépôt, déviations, comportements non "
    "attendus. Tu tiens ton propre corpus de règles et tu SIGNALES tout écart pour correction. Tu "
    "observes, tu alertes, tu documentes ; tu ne codes pas.",
    "planificateur": "Tu es le planificateur de la brigade. Tu lis atelier/journal.md, la mémoire "
    "des agents (atelier/memoire/) et le code du dépôt pour comprendre où en est Monique, puis tu "
    "réécris atelier/plan.md en backlog priorisé. Chaque pas du backlog est SOUS-PLANIFIÉ : une "
    "micro-tâche à la fois — un fichier, une fonction, un test — jamais une grosse session "
    "fourre-tout. Pour chaque pas, tu expliques le pourquoi-maintenant : ce qui le rend "
    "prioritaire à cet instant plutôt qu'un autre. Tu ne codes JAMAIS toi-même : tu planifies, "
    "tu laisses le développeur exécuter.",
    "vitrine": "Tu es vitrine, l'agent Interface de Monique. Ton SEUL mandat : rendre lisible "
    "et accessible à un humain ce que produit la brigade — vues par département, contenu réel "
    "(jamais des clés/identifiants techniques bruts), réglages par agent, tableaux de bord "
    "simples. Tu ne touches QU'aux templates (app/templates/) et au style visuel (CSS) ; le "
    "fond (logique métier, routes, données) reste aux autres agents — si une vue manque de "
    "données pour être lisible, tu le signales, tu ne les fabriques pas.",
}
# Profils d'outils par rôle. JAMAIS Bash (le harnais lance les tests). Le garde-fou d'écriture
# borne les Write/Edit aux zones autorisées quoi qu'il arrive.
_OUTILS = {
    # Beecham observe et écrit ses plans/propositions dans l'atelier (ne code pas)
    "chef": "Read,Glob,Grep,Write",
    # l'auditeur lit les mesures/journaux et écrit ses bilans (ne code pas)
    "auditeur": "Read,Glob,Grep,Write",
    # le stratège lit les bilans/le cap et écrit ses propositions de stratégie (ne code pas)
    "stratege": "Read,Glob,Grep,Write",
    # le dev édite le code
    "developpeur": "Read,Edit,Write,Glob,Grep",
    # le chercheur LIT large (dont le web, pour aller apprendre dehors) et écrit ses notes
    "chercheur": "Read,Glob,Grep,Write,WebSearch,WebFetch",
    # le contrôleur relit, ne modifie rien
    "controleur": "Read,Glob,Grep",
    # le veilleur (sysadmin) observe et écrit son corpus / ses alertes dans l'atelier
    "veilleur": "Read,Glob,Grep,Write",
    # le planificateur observe et écrit le backlog (atelier/plan.md), jamais Bash/Edit : il ne code pas
    "planificateur": "Read,Glob,Grep,Write",
    # vitrine ne touche que templates/CSS, mêmes outils que le développeur
    "vitrine": "Read,Edit,Write,Glob,Grep",
}


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
    outils = _OUTILS.get(role, _OUTILS["developpeur"])
    # Contexte de la brigade : plan.md + mémoire du rôle, en tête du prompt. Fail-soft (même
    # principe que journal_ajouter) : fichier absent/vide ou erreur de lecture => on ignore
    # silencieusement ce bloc, la mission ne doit JAMAIS échouer pour ça.
    contexte = ""
    try:
        plan_txt = (ATELIER / "plan.md").read_text(encoding="utf-8")
        if plan_txt:
            contexte += f"# Contexte de la brigade (plan.md)\n{plan_txt}\n\n"
    except OSError:
        pass
    try:
        memoire_txt = chemin_memoire(role).read_text(encoding="utf-8")
        if memoire_txt:
            contexte += f"# Mémoire de ton rôle\n{memoire_txt}\n\n"
    except OSError:
        pass
    prompt = (
        f"{contexte}"
        f"{consigne}\n\n"
        "Tu travailles dans une COPIE ISOLÉE du dépôt Monique. Modifie uniquement les fichiers "
        "nécessaires, proprement. Ne lance aucune commande (tu n'as pas de shell) : les tests "
        "seront lancés automatiquement après toi. Réponds par un court résumé de ce que tu as fait."
    )
    # Anti-octet-nul : Windows CreateProcess refuse tout argument contenant \x00 (ValueError).
    # Un chemin ou une consigne mal échappé (ex. « \00 ») en glisserait un — on nettoie par sécurité.
    prompt = prompt.replace("\x00", "")
    systeme = systeme.replace("\x00", "")
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
        outils,
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


def _normaliser_verdict(s: str) -> str:
    """Majuscule SANS accents — « ACCEPTÉ » et « ACCEPTE » deviennent identiques (leçon incident)."""
    return "".join(
        c
        for c in unicodedata.normalize("NFKD", s or "")
        if unicodedata.category(c) != "Mn"
    ).upper()


def _lancer_controleur(scope, diff, tests_resume, worktree, _agent=None) -> dict:
    """Revue adversariale ancrée sur le diff réel + les tests. TROIS verdicts (directive Alex) :
    - « accepte » : correct, on fusionne ;
    - « corriger » : récupérable, on renvoie au dev AVEC la correction précise (pas de gâchis) ;
    - « rejeter » : approche mauvaise, on abandonne (inutile d'itérer).
    Verdict lu sur la PREMIÈRE ligne non vide seule, insensible aux accents — jamais un substring
    global (une citation du verdict opposé tromperait, cf. incident 2026-08-19)."""
    agent = _agent or _lancer_agent
    consigne = (
        f"SCOPE de la mission : {scope}\n\n"
        f"Résumé des tests (harnais déterministe) : {tests_resume}\n\n"
        "Diff réel — seule source de vérité :\n```diff\n" + (diff or "") + "\n```\n\n"
        "Relis de façon ADVERSARIALE : cherche ce qui casserait, tout écart au SCOPE (plus, moins, "
        "autre chose), si les tests couvrent vraiment le chemin. Un signal vert ne prouve rien. "
        "Vérifie aussi qu'aucune identité ni chemin de poste ne s'introduit.\n\n"
        "PREMIÈRE LIGNE de ta réponse, EXACTEMENT l'un de :\n"
        "  VERDICT: ACCEPTÉ     (correct — on fusionne)\n"
        "  VERDICT: À CORRIGER  (récupérable — donne la correction PRÉCISE et actionnable)\n"
        "  VERDICT: REJETÉ      (approche mauvaise — on abandonne)\n"
        "Puis explique. Si À CORRIGER : sois précis, le dev repartira de ta consigne, pas de zéro."
    )
    res = agent("controleur", consigne, worktree)
    texte = res.get("texte", "") if isinstance(res, dict) else ""
    premiere = _normaliser_verdict(
        next((li for li in texte.splitlines() if li.strip()), "")
    )
    if "ACCEPTE" in premiere:
        verdict = "accepte"
    elif "CORRIGER" in premiere:
        verdict = "corriger"
    else:
        verdict = "rejeter"
    return {"verdict": verdict, "raison": texte}


def _fusion_locale(branche, worktree, mission_id) -> bool:
    """Commit + merge --no-ff LOCAL (jamais de push). Message générique — jamais la consigne."""
    _git(worktree, "add", "-A")
    _git(
        worktree,
        "-c",
        "user.name=beecham",
        "-c",
        "user.email=beecham@users.noreply.github.com",
        "commit",
        "-m",
        f"beecham: mission {mission_id}",
    )
    r = _git(
        RACINE, "merge", "--no-ff", "-m", f"beecham: mission {mission_id}", branche
    )
    _nettoyer(branche, worktree)
    return r.returncode == 0


def _clore(mission_id, chemin, statut, role, journal, h, resume) -> dict:
    """État TERMINAL de la mission (jamais « propose ») : enregistre + trace au journal."""
    _maj(
        mission_id,
        chemin,
        statut=statut,
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
    journal_ajouter(role, resume, statut)
    return {
        "ok": statut in ("livre", "valide"),
        "statut": statut,
        "tests_ok": h["tests_ok"],
        "fichiers": h["fichiers"],
        "journal": journal,
    }


def executer_mission(
    mission_id,
    role="developpeur",
    chemin=None,
    _agent=None,
    _controleur=None,
    max_tours=2,
) -> dict:
    """Traite la mission AUTOMATIQUEMENT jusqu'à un état terminal — jamais de « propose » qui traîne :
    - pas de diff de code (mission atelier) → `livre` ;
    - code accepté par le contrôleur → fusion locale → `valide` ;
    - code « à corriger » → renvoyé au dev avec la correction précise (borné à max_tours) ;
    - code « rejeté » (approche mauvaise) → `rejete` (abandon, pas de gâchis d'itérations) ;
    - encore « à corriger » au bout de max_tours → `bloque` (remonté à Alex)."""
    m = lire_mission(mission_id, chemin)
    if not m:
        return {"ok": False, "erreur": "mission_absente"}
    agent = _agent or _lancer_agent
    controle = _controleur or _lancer_controleur
    try:
        wt = _creer_worktree(m["branche"])
    except Exception as e:
        _maj(mission_id, chemin, statut="echec", journal=json.dumps([str(e)]))
        return {"ok": False, "erreur": str(e)}

    journal, consigne = [], m["consigne"]
    for tour in range(1, max_tours + 1):
        res = agent(role, consigne, wt)
        journal += res.get("journal", [])
        h = _harnais(wt)
        journal.append(f"harnais · tests: {h['tests_resume'] or '?'}")

        if not h["diff"].strip():  # mission atelier : rien à fusionner
            _nettoyer(m["branche"], wt)
            return _clore(
                mission_id,
                chemin,
                "livre",
                role,
                journal,
                h,
                "livré (rien à fusionner)",
            )

        if not h["tests_ok"]:
            verdict, raison = "corriger", f"tests en échec : {h['tests_resume']}"
        else:
            v = controle(m["consigne"], h["diff"], h["tests_resume"], wt)
            verdict, raison = v["verdict"], v["raison"]
            journal.append(f"controleur · {verdict}")

        if verdict == "accepte":
            ok = _fusion_locale(m["branche"], wt, mission_id)
            return _clore(
                mission_id,
                chemin,
                "valide" if ok else "echec",
                role,
                journal,
                h,
                "accepté + fusionné (local)" if ok else "conflit de fusion",
            )
        if verdict == "rejeter":
            _graver_lecon_rejet(m["consigne"], raison)
            _nettoyer(m["branche"], wt)
            return _clore(
                mission_id,
                chemin,
                "rejete",
                role,
                journal,
                h,
                "rejeté (abandon) : " + raison[:80],
            )
        # « corriger » : on renvoie au dev avec la correction, sans repartir de zéro
        if tour < max_tours:
            consigne = (
                m["consigne"]
                + f"\n\n[CORRECTION — tour {tour + 1}] Le contrôleur demande : "
                + raison[:800]
                + "\nCorrige PRÉCISÉMENT ces points, ne repars pas de zéro."
            )
            journal.append(f"→ correction demandée (tour {tour + 1})")
        else:
            _maj(
                mission_id,
                chemin,
                statut="bloque",
                diff=h["diff"],
                agents_json=json.dumps([role], ensure_ascii=False),
                journal=json.dumps(journal, ensure_ascii=False),
                tests_json=json.dumps(
                    {
                        "ok": h["tests_ok"],
                        "resume": h["tests_resume"],
                        "fichiers": h["fichiers"],
                    },
                    ensure_ascii=False,
                ),
            )
            journal_ajouter(role, m["consigne"][:50], "bloqué (à revoir par Alex)")
            return {
                "ok": False,
                "statut": "bloque",
                "journal": journal,
                "raison": raison,
            }
    return {
        "ok": False,
        "statut": "echec",
        "journal": journal,
    }  # max_tours < 1 (garde-fou)


def valider(mission_id, chemin=None) -> dict:
    """Validation MANUELLE (rare) : Alex fusionne une mission `bloque` (ou `propose` héritée).
    Le flux normal est automatique (executer_mission) — ceci n'est qu'un filet pour l'escalade."""
    m = lire_mission(mission_id, chemin)
    if not m or m["statut"] not in ("propose", "bloque"):
        return {"ok": False, "erreur": "statut_invalide"}
    wt = WORKTREES / m["branche"].replace("/", "_")
    ok = _fusion_locale(m["branche"], wt, mission_id)
    _maj(mission_id, chemin, statut="valide" if ok else "echec")
    return {"ok": ok, "erreur": None if ok else "conflit de fusion"}


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
