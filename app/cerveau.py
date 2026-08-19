import hashlib
import json
import re
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

import httpx

import estop
import tarifs
import usage

CREATE_NO_WINDOW = 0x08000000
# revue M4 : hors arbre versionné (dans le coffre), jamais dans secretaire/
SPILL_DIR = Path.home() / ".monique_secrets" / "spillover"
# revue §13.7 : masquage = remplacement COMPLET (jamais un masque tronqué réutilisable)
_MASQUES = [
    # revue red-team H1 : IBAN AVEC espaces (FR76 3000 4000 …) — le format le plus courant en mail
    (re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){10,30}"), "[IBAN masqué]"),
    (re.compile(r"\bsk-[A-Za-z0-9\-_]{16,}"), "[clé masquée]"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}"), "[token masqué]"),
    (re.compile(r"\b\d{5}[ ]*\d{5}[ ]*[A-Za-z0-9]{11}[ ]*\d{2}\b"), "[RIB masqué]"),
    (
        re.compile(r"\b[12][ ]?\d{2}[ ]?\d{2}[ ]?\d{2}[ ]?\d{3}[ ]?\d{3}[ ]?\d{2}\b"),
        "[NIR masqué]",
    ),
    (re.compile(r"\b(?:\d{4}[ ]?){3}\d{4}\b"), "[CB masquée]"),
]


def nettoyer_texte(s: str) -> str:
    # revue §13.3 : neutralise les lone surrogates (U+D800–DFFF) qui crashent json.dumps/SQLite
    return s.encode("utf-8", "replace").decode("utf-8", "replace") if s else s


@dataclass
class ProviderProfile:
    nom: str
    mode: str  # "claude_cli" | "openai_compat"
    model: str = "sonnet"
    base_url: str = ""
    env_var: str = ""
    default_max_tokens: int = 4096


def classifier_erreur(texte: str) -> str:
    t = (texte or "").lower()
    if (
        "winerror 2" in t
        or "no such file" in t
        or "introuvable" in t
        or "cannot find" in t
    ):
        return "binaire_absent"  # revue résilience : distinguer environnement cassé d'un vrai résultat
    if "429" in t or "rate limit" in t or "quota" in t:
        return "rate_limit"
    if "529" in t or "overloaded" in t:
        return "overloaded"
    if "content" in t and ("policy" in t or "blocked" in t or "refus" in t):
        return "content_policy"
    if "context" in t and ("overflow" in t or "length" in t or "too long" in t):
        return "context_overflow"
    if "network" in t or "timeout" in t or "connection" in t:
        return "network"
    return "ok"


def _masquer(t: str) -> str:
    for rx, rep in _MASQUES:
        t = rx.sub(rep, t)
    return t


def spillover(texte: str, seuil: int = 8000) -> str:
    if len(texte) <= seuil:
        return texte
    SPILL_DIR.mkdir(parents=True, exist_ok=True)
    propre = _masquer(texte)  # revue M4 : IBAN masqués avant écriture disque
    h = hashlib.sha1(propre.encode("utf-8", "replace")).hexdigest()[:12]
    (SPILL_DIR / f"{h}.txt").write_text(propre, encoding="utf-8")
    return f"{propre[:seuil]}\n[…tronqué… voir coffre spillover/{h}.txt ({len(texte)} car.)]"


def _lancer_claude_cli(prompt: str, system: str | None, prof: ProviderProfile) -> dict:
    # CONFINEMENT (revue B1) : le cerveau ne produit QUE du texte.
    #  - --strict-mcp-config SANS --mcp-config => AUCUN serveur MCP chargé
    #    (donc pas de dolibarr-ops / gmail / telegram / whatsapp / db-ops : zéro envoi/écriture externe)
    #  - --permission-mode default (PAS acceptEdits) + --disallowedTools => ni fichier ni shell
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        prof.model,
        "--permission-mode",
        "default",
        "--strict-mcp-config",
        # revue red-team C2 : AUCUN outil. Le cerveau ne fait que du TEXTE. Sinon un mail injecté
        # ferait lire le coffre via Read/Glob/Grep et l'exfiltrerait dans le brouillon.
        "--disallowedTools",
        "Read,Write,Edit,Bash,Glob,Grep,LS,WebFetch,WebSearch,Task,NotebookRead,NotebookEdit,TodoWrite",
    ]
    if system:
        cmd += ["--append-system-prompt", system]
    # stderr fusionné dans stdout (revue M6) => pas de deadlock si claude est bavard
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=CREATE_NO_WINDOW,
    )
    lignes = []
    lecteur = threading.Thread(target=lambda: lignes.extend(proc.stdout), daemon=True)
    lecteur.start()
    lecteur.join(
        timeout=1800
    )  # revue §13.5 : deadline murale sur la LECTURE (pas juste sur wait)
    if lecteur.is_alive():  # stdout ne se ferme jamais => claude figé
        proc.kill()
        lecteur.join(timeout=5)  # drain borné après kill
        raise RuntimeError("claude -p figé (timeout de lecture)")
    try:
        code = proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        # revue résilience : pas d'orphelin claude
        proc.kill()
        proc.wait(timeout=5)
        code = -1
    texte, it, ot, err = "", 0, 0, ""
    for ligne in lignes:
        try:
            ev = json.loads(ligne)
        except Exception:
            err += ligne  # lignes non-JSON (stderr) accumulées pour le diagnostic
            continue
        if ev.get("type") == "result":
            texte = ev.get("result") or ""
            u = ev.get("usage") or {}
            it, ot = u.get("input_tokens", 0), u.get("output_tokens", 0)
    if code != 0 or not texte:  # revue M6 : échec réel, pas un "succès vide"
        raise RuntimeError((err[-500:] or f"claude -p code={code} sans result").strip())
    return {"texte": texte, "input_tokens": it, "output_tokens": ot}


def _lancer_openai_compat(prompt: str, system: str | None, prof: ProviderProfile) -> dict:
    # import local (pas en tête de module) : fournisseurs.py importe ProviderProfile
    # depuis cerveau.py — un import en tête créerait un cycle.
    import fournisseurs

    cle = fournisseurs.lire_cle(prof.env_var)
    if not cle:
        return {"ok": False, "erreur": "cle_absente", "texte": ""}
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        rep = httpx.post(
            f"{prof.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {cle}"},
            json={"model": prof.model, "messages": messages},
            timeout=120,
        )
    except httpx.HTTPError:
        return {"ok": False, "erreur": "reseau", "texte": ""}
    if rep.status_code != 200:
        return {"ok": False, "erreur": f"http_{rep.status_code}", "texte": ""}
    d = rep.json()
    texte = d["choices"][0]["message"]["content"]
    u = d.get("usage") or {}
    return {
        "ok": True,
        "texte": texte,
        "input_tokens": u.get("prompt_tokens", 0),
        "output_tokens": u.get("completion_tokens", 0),
    }


def appeler(
    agent, prompt, profile: ProviderProfile, task, system=None, chemin=None
) -> dict:
    if estop.engage():
        return {"ok": False, "texte": "", "erreur": "estop", "usage": None}
    prompt = _masquer(
        nettoyer_texte(prompt)
    )  # revue §13.3/§13.7 : surrogates neutralisés + secrets masqués avant modèle/disque
    prompt = spillover(prompt)
    try:
        if profile.mode == "claude_cli":
            res = _lancer_claude_cli(prompt, system, profile)
        elif profile.mode == "openai_compat":
            oc = _lancer_openai_compat(prompt, system, profile)
            if not oc["ok"]:
                return {
                    "ok": False,
                    "texte": "",
                    "erreur": oc["erreur"],
                    "usage": None,
                }
            res = {
                "texte": oc["texte"],
                "input_tokens": oc["input_tokens"],
                "output_tokens": oc["output_tokens"],
            }
        else:
            return {
                "ok": False,
                "texte": "",
                "erreur": f"mode_inconnu:{profile.mode}",
                "usage": None,
            }
    except Exception as e:
        cat = classifier_erreur(str(e))
        # revue résilience : dans un except, "ok" n'a pas de sens
        return {
            "ok": False,
            "texte": "",
            "erreur": cat if cat != "ok" else "erreur",
            "usage": None,
        }

    cout_status = "included" if profile.mode == "claude_cli" else "estimated"
    cout = tarifs.estimer_cout_usd(
        profile.model, res.get("input_tokens", 0), res.get("output_tokens", 0)
    )
    usage.compter(
        agent,
        profile.model,
        profile.mode,
        task,
        res.get("input_tokens", 0),
        res.get("output_tokens", 0),
        estimated_cost_usd=cout if cout is not None else 0.0,
        cost_status=cout_status,
        chemin=chemin,
    )
    return {
        "ok": True,
        "texte": res["texte"],
        "erreur": None,
        "usage": {
            "input_tokens": res.get("input_tokens", 0),
            "output_tokens": res.get("output_tokens", 0),
        },
    }
