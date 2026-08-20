"""Socle des ponts LLM web gratuits : chaque « pont » = la fenêtre de chat d'un LLM (DeepSeek,
Gemini…) pilotée par un Chrome DÉDIÉ isolé (profil + port CDP à lui). Ce module gère leur CYCLE DE
VIE via le superviseur (ouvrir → enregistrer / fermer → couper le browser racine ET tout son arbre,
zéro orphelin — que la fenêtre soit fermée à la main ou non) et un ROUTEUR qui tourne entre les
ponts en espaçant les appels (cadence anti-détection).

Sortie au MÊME contrat que beecham._lancer_agent — {ok, texte, journal, session_id} — donc un pont
se branche partout où Beecham accepte un `_agent` injecté (contrôleur, chercheur, délibération…).

Garde-fous (cf. mémoire project_deepseek_bridge) : une requête à la fois, jamais de rafale haute
fréquence. RÉSERVÉ aux rôles « cerveau » (texte in / texte out) — jamais le développeur (qui édite
des fichiers ; un chat web ne fait que répondre du texte). Ajouter un pont = une entrée dans PONTS.

Robustesse (correctifs issus d'une revue adversariale par DeepSeek + Gemini, 2026-08-20) :
verrou par pont, PID pris du Popen (pas de WMI dans le cas nominal), Chrome tué s'il ne démarre pas,
cadence marquée même après un échec (anti-ban), nom de pont validé, _pid_browser vérifie le profil.
"""

import os
import random
import subprocess
import threading
import time
import urllib.request

import journal_ponts
import superviseur

_CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
_PY314 = r"C:\Program Files\Python314\python.exe"  # l'env où Playwright est installé
_NOW = 0x08000000  # CREATE_NO_WINDOW (pas de console qui flashe)
_EXTRACTEUR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extracteur_code.py")
_CLIQUEUR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cliquer_pont.py")

# Un pont = où est son Chrome (profil + port CDP + url) et quel script envoie une question en
# s'attachant au CDP déjà ouvert (jamais relancer Chrome — c'est `ouvrir()` qui le fait).
PONTS = {
    "deepseek": {
        "profil": r"C:\Users\ALEX\.claude\skills\ask-deepseek\chrome_profile",
        "port": 9223,
        "url": "https://chat.deepseek.com/",
        "host": "deepseek.com",
        "sender": r"C:\Users\ALEX\.claude\skills\ask-deepseek\scripts\deepseek_send.py",
        "message_sel": "div.ds-assistant-message-main-content",  # conteneur d'un message assistant
        "btn_nouvelle_conv": "div.ds-button:has-text('Nouvelle conversation')",
        # Séquence d'effacement d'une conversation (sélecteurs relevés par mouchard de clics) :
        "suppr_menu": "div.ds-button--iconLabelTertiary",  # le ⋯ d'une conversation (au survol)
        "suppr_option": "div.ds-dropdown-menu-option__label:has-text('Supprimer')",
        "suppr_confirmer": "div.ds-button--error:has-text('Supprimer le chat')",
        "modes": {"instant": "Instant", "expert": "Expert", "vision": "Vision"},  # sélecteur à 3 modes
        "python": _PY314,
    },
    "gemini": {
        "profil": r"C:\Users\ALEX\.claude\skills\ask-gemini\chrome_profile",
        "port": 9224,
        "url": "https://gemini.google.com/app",
        "host": "gemini.google.com",
        "sender": r"C:\Users\ALEX\.claude\skills\ask-gemini\scripts\gemini_send_chrome.py",
        "message_sel": "model-response",
        "btn_nouvelle_conv": "button[aria-label='Nouvelle discussion']",
        "python": _PY314,
    },
}

# Rythme HUMAIN (« indiscernable d'un humain qui copie-colle ») : espacement ALÉATOIRE entre deux
# appels d'un même pont — jamais un intervalle fixe (la régularité est un signal machine) — et un
# plafond de requêtes par jour et par pont (un humain n'en fait pas des centaines). Réduit le risque
# de détection, ne l'annule pas. Bornes volontairement ajustables.
_INTERVALLE_MIN_S = 8
_INTERVALLE_MAX_S = 35
_PLAFOND_JOUR = 40
_dernier_usage: dict = {}  # nom -> timestamp du dernier envoi (routeur + cadence)
# Un verrou RÉENTRANT par pont : sérialise les appels concurrents (ouvrir/fermer/lancer) sur un même
# pont — sinon deux appels simultanés entremêlent leurs prompts dans le même onglet et violent la
# cadence. RLock car lancer() prend le verrou puis appelle ouvrir() (même thread → réentrée OK).
_verrous = {nom: threading.RLock() for nom in PONTS}


def _probe(port, timeout=2.0) -> bool:
    """Le Chrome du pont répond-il sur son port CDP ?"""
    try:
        with urllib.request.urlopen(
            f"http://localhost:{port}/json/version", timeout=timeout
        ):
            return True
    except Exception:
        return False


def _pid_browser(port, profil=None):
    """PID du chrome.exe BROWSER RACINE de ce pont (il porte le port et n'a pas de `--type=` ;
    ses renderers/gpu/utility en sont les descendants). Si `profil` est fourni, on exige aussi que
    la ligne de commande le contienne — anti « port squatté par un autre Chrome ». Ne sert que de
    FALLBACK : dans le cas nominal, `ouvrir()` prend directement le PID du Popen (pas de WMI)."""
    filtre_profil = (
        f" -and $_.CommandLine -like '*{profil}*'" if profil else ""
    )  # -like : chemin littéral (pas de regex à échapper)
    ps = (
        "Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -eq 'chrome.exe' -and "
        f"$_.CommandLine -match '--remote-debugging-port={port}'"
        f"{filtre_profil} -and "
        "$_.CommandLine -notmatch '--type=' } | "
        "Select-Object -First 1 -ExpandProperty ProcessId"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=12,
            creationflags=_NOW,
        ).stdout.strip()
    except Exception:
        return None
    return int(out) if out.isdigit() else None


def _rid_enregistre(nom):
    """L'id de registre du pont s'il est déjà suivi (et vivant) par le superviseur, sinon None."""
    for p in superviseur.etat():
        if p["nom"] == f"pont:{nom}" and p["vivant"]:
            return p["id"]
    return None


def ouvrir(nom) -> dict:
    """Ouvre le pont `nom` (idempotent) et l'inscrit au superviseur. Si le Chrome tourne déjà, on ne
    relance pas. Si on le lance et qu'il ne répond pas, on le TUE (anti-orphelin) au lieu de le
    laisser traîner. Le PID enregistré est celui du Popen quand on lance (fiable, pas de WMI)."""
    cfg = PONTS[nom]
    port = cfg["port"]
    with _verrous[nom]:
        proc = None
        if not _probe(port):
            proc = subprocess.Popen(
                [
                    _CHROME,
                    f"--user-data-dir={cfg['profil']}",
                    f"--remote-debugging-port={port}",
                    f"--app={cfg['url']}",
                ],
                creationflags=_NOW,
            )
            deadline = time.time() + 20
            while time.time() < deadline and not _probe(port):
                time.sleep(1)
            if not _probe(port):
                # Le Chrome qu'on vient de lancer ne répond pas : le couper pour ne pas créer un
                # orphelin (exactement le fléau que ce module doit éviter).
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        capture_output=True,
                        timeout=15,
                        creationflags=_NOW,
                    )
                except Exception:
                    pass
                return {"ok": False, "nom": nom, "erreur": "cdp_down"}
        rid = _rid_enregistre(nom)
        if not rid:
            # Cas nominal (on vient de lancer) : PID du Popen, pas de WMI. Sinon (Chrome déjà là),
            # fallback WMI qui vérifie le profil.
            pid = proc.pid if proc else _pid_browser(port, cfg["profil"])
            if pid:
                rid = superviseur.enregistrer(
                    pid,
                    nom=f"pont:{nom}",
                    proprietaire="monique",
                    but=f"pont LLM {nom} · {cfg['url']}",
                    ppid=None,  # ressource persistante, coupée explicitement — pas liée à une mission
                )
        return {"ok": True, "nom": nom, "rid": rid, "pid_browser": _pid_browser(port, cfg["profil"])}


def fermer(nom) -> dict:
    """Ferme le pont PROPREMENT : le superviseur coupe le browser racine + TOUT son arbre
    (renderers, gpu, utility) — zéro orphelin, que la fenêtre ait été fermée à la main ou non."""
    with _verrous[nom]:
        rid = _rid_enregistre(nom)
        if not rid:  # Chrome ouvert hors registre ? on l'inscrit d'abord pour le couper proprement.
            pid = _pid_browser(PONTS[nom]["port"], PONTS[nom]["profil"])
            if not pid:
                return {"ok": True, "nom": nom, "note": "déjà fermé"}
            rid = superviseur.enregistrer(
                pid, nom=f"pont:{nom}", proprietaire="monique", but=f"pont LLM {nom}", ppid=None
            )
        res = superviseur.tuer(rid)
        return {"ok": res.get("ok", False), "nom": nom, "pid": res.get("pid")}


def etat() -> list[dict]:
    """État de chaque pont connu : ouvert (CDP up) ? suivi par le superviseur ? — pour l'UI Monique."""
    # Ne garder que les entrées VIVANTES : une entrée morte homonyme ne doit pas masquer une vivante.
    sup = {p["nom"]: p for p in superviseur.etat() if p.get("vivant")}
    out = []
    for nom, cfg in PONTS.items():
        s = sup.get(f"pont:{nom}")
        out.append(
            {
                "nom": nom,
                "ouvert": _probe(cfg["port"]),
                "suivi": bool(s),
                "pid": s["pid"] if s else None,
                "descendants": s["descendants"] if s else 0,
                "dernier_usage": _dernier_usage.get(nom),
            }
        )
    return out


def _choisir_pont(nom=None) -> str:
    """Routeur : le pont demandé (déjà validé par lancer), sinon celui utilisé le moins récemment."""
    if nom:
        return nom
    return min(PONTS, key=lambda n: _dernier_usage.get(n, 0))


def lancer(role, consigne, worktree=None, nom=None, mode=None, timeout_s=120) -> dict:
    """Envoie `consigne` via un pont, au contrat de beecham._lancer_agent (worktree ignoré : texte
    pur). Ouvre le pont au besoin, respecte la cadence, tourne entre les ponts. `nom` force un pont
    (validé). `mode` (ex. DeepSeek : 'expert' pour DeepThink, 'vision' pour l'OCR) sélectionne un
    mode avant l'envoi si le pont le supporte. `timeout_s` : temps laissé au pont pour répondre
    (défaut 120s) — à rallonger pour un prompt volumineux (ex. synthèse sur un gros matériel
    accumulé, cf. bug réel 20/08/2026 : deux échecs `ok=False` sur des prompts de ~36 000
    caractères, probablement le temps de génération dépassant les 120s par défaut).
    Verrou par pont : appels concurrents sérialisés."""
    if nom is not None and nom not in PONTS:
        return {"ok": False, "texte": "", "journal": [f"pont inconnu: {nom}"], "session_id": None}
    nom = _choisir_pont(nom)
    with _verrous[nom]:
        # Plafond quotidien par pont (anti-volume) : au-delà, on refuse SANS même ouvrir Chrome.
        # Basé sur le JOURNAL PERSISTÉ (journal_ponts), pas une mémoire de process — un compteur en
        # mémoire se réinitialise à chaque relance et ne protège donc RIEN en usage réel (trouvé le
        # 20/08/2026 : nos tests via `python -c` repartaient à zéro à chaque appel).
        if journal_ponts.appels_aujourdhui(nom) >= _PLAFOND_JOUR:
            return {
                "ok": False,
                "texte": "",
                "journal": [f"pont {nom}: plafond quotidien atteint ({_PLAFOND_JOUR})"],
                "session_id": None,
            }
        o = ouvrir(nom)
        if not o.get("ok"):
            return {
                "ok": False,
                "texte": "",
                "journal": [f"pont {nom}: {o.get('erreur')}"],
                "session_id": None,
            }
        # Rythme humain : espacement ALÉATOIRE (jamais fixe) depuis le dernier appel du pont.
        cible = random.uniform(_INTERVALLE_MIN_S, _INTERVALLE_MAX_S)
        ecoule = time.time() - _dernier_usage.get(nom, 0)
        if ecoule < cible:
            time.sleep(cible - ecoule)
        # Pas d'incrément manuel ici : journal_ponts.enregistrer_appel() (plus bas) journalise déjà
        # chaque tentative réelle -- c'est CE journal, persisté, qui nourrit le plafond du dessus.
        cfg = PONTS[nom]
        cmd_sender = [cfg["python"], cfg["sender"], "--message", consigne, "--timeout", str(timeout_s)]
        if mode and mode in cfg.get("modes", {}):  # ex. DeepSeek : instant | expert | vision
            cmd_sender += ["--mode", cfg["modes"][mode]]
        try:
            r = subprocess.run(
                cmd_sender,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s + 60,  # marge : ne pas tuer le sender pile à son propre timeout
            )
        except Exception as e:
            journal_ponts.enregistrer_appel(nom, role, False, len(consigne), 0)
            return {
                "ok": False,
                "texte": "",
                "journal": [f"pont {nom} {role}: échec ({type(e).__name__})"],
                "session_id": None,
            }
        finally:
            # Marquer l'usage MÊME en cas d'échec/timeout : sinon la requête suivante croit le pont
            # inactif depuis longtemps et frappe sans délai → risque de ban (revue Gemini #3).
            _dernier_usage[nom] = time.time()
        texte_reponse = (r.stdout or "").strip()
        journal_ponts.enregistrer_appel(nom, role, r.returncode == 0, len(consigne), len(texte_reponse))
        return {
            "ok": r.returncode == 0,
            "texte": texte_reponse,
            "journal": [f"pont {nom} · {role} (rc={r.returncode})"],
            "session_id": None,
            "pont": nom,
        }


def extraire_code(nom) -> str:
    """Récupère le CODE des blocs natifs (`pre`) du DERNIER message du pont — par LECTURE PASSIVE du
    DOM (aucune frappe, aucun clic, aucun signal réseau vers le fournisseur → zéro motif de détection
    ajouté). Bien plus fiable que parser le texte aplati (le markdown y est déformé). Renvoie le code
    propre (blocs concaténés), ou "" si rien. À appeler juste après un `lancer()` qui a produit du code."""
    cfg = PONTS[nom]
    try:
        r = subprocess.run(
            [
                cfg["python"],
                _EXTRACTEUR,
                "--port",
                str(cfg["port"]),
                "--message-sel",
                cfg["message_sel"],
                "--host-hint",
                cfg["host"],
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except Exception:
        return ""
    return (r.stdout or "").strip()


def fermer_inactifs(seuil_s: int = 1800) -> list[str]:
    """Ferme les ponts suivis dont l'inactivité dépasse le seuil spécifié (résilience : évite les
    Chrome oubliés qui traînent en mangeant de la RAM). Scope volontairement simple : ne touche
    PAS aux ponts jamais utilisés (dernier_usage=None) — écrit par Gemini, revu et inséré ici.

    Args:
        seuil_s: Seuil d'inactivité en secondes (par défaut 1800s / 30min).

    Returns:
        La liste des noms des ponts qui ont été fermés.
    """
    maintenant = time.time()
    fermes = []

    for pont in etat():
        if not pont.get("suivi"):
            continue

        dernier_usage = pont.get("dernier_usage")
        if dernier_usage is not None and (maintenant - dernier_usage) > seuil_s:
            nom = pont["nom"]
            fermer(nom)
            fermes.append(nom)

    return fermes


def nouvelle_conversation(nom) -> dict:
    """Repart d'une conversation VIERGE en NAVIGUANT vers l'URL de base du pont (robuste, indépendant
    de la sidebar/boutons). Action UI, AUCUNE requête LLM : évite l'accumulation de contexte
    (anti-détection) et remet le pont à zéro entre deux cycles."""
    cfg = PONTS[nom]
    with _verrous[nom]:
        try:
            r = subprocess.run(
                [
                    cfg["python"],
                    _CLIQUEUR,
                    "--port",
                    str(cfg["port"]),
                    "--host-hint",
                    cfg["host"],
                    "--goto",
                    cfg["url"],
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except Exception as e:
            return {"ok": False, "nom": nom, "erreur": type(e).__name__}
        return {"ok": r.returncode == 0, "nom": nom, "detail": (r.stdout or r.stderr or "").strip()[:120]}
