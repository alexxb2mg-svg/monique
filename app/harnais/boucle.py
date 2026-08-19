"""Boucle autonome de Beecham, portée sur le MOTEUR modulaire.

Chaque mission d'une vague est un PIPELINE exécuté dans son thread : le code des devs tourne en
parallèle, tandis qu'UN verrou unique sérialise test/revue/fusion (jamais deux pytest, deux
contrôleurs ou deux fusions git en même temps — même charge que l'orchestration historique).
La composition du pipeline vient de harnais.pipelines (les orientations) ; à terme Beecham choisira.

Durable et versionné (remplace l'ancien script du scratchpad temporaire). Lancement :
    python -m harnais.boucle        (depuis le dossier app/)
Interrupteur : créer atelier/STOP.
"""

import json
import os
import sys
import threading
import time
from datetime import datetime

# app/ dans le path (calculé, jamais un chemin de poste en dur) pour importer beecham & co.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import beecham  # noqa: E402
import entrepot  # noqa: E402
import superviseur  # noqa: E402
from harnais import pipelines  # noqa: E402
from harnais.briques import BRIQUES  # noqa: E402
from harnais.moteur import executer_pipeline  # noqa: E402

entrepot.init_fondations()
beecham.init_atelier()
ATELIER = beecham.ATELIER
AT = str(ATELIER).replace("\\", "/")
STOP = ATELIER / "STOP"
INCIDENTS = ATELIER / "incidents_boucle.jsonl"
CONCURRENCE = pipelines.CONCURRENCE
MAX_VAGUES = pipelines.MAX_VAGUES


def log(m):
    print(m, flush=True)


def incident(type_, detail, mid=None):
    """Grave un incident en une ligne JSON append-only (fil relu par le suivi dynamique)."""
    rec = {"t": datetime.now().isoformat(timespec="seconds"), "type": type_, "detail": str(detail)[:500]}
    if mid is not None:
        rec["mid"] = mid
    log(f"  [!] {type_}: {str(detail)[:80]}")
    try:
        with open(INCIDENTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def deja_en_cours():
    """Garde SINGLETON via le registre : une autre boucle-beecham vivante (PID ≠ moi) => refus."""
    moi = os.getpid()
    try:
        for x in superviseur.etat():
            if x.get("nom") == "boucle-beecham" and x.get("vivant") and x.get("pid") != moi:
                return x.get("pid")
    except Exception:
        pass
    return None


def reconcilier_fantomes():
    """Au démarrage (singleton garanti), toute mission 'en_cours' est orpheline -> 'interrompu'."""
    try:
        c = entrepot.connexion_ecriture()
        n = c.execute(
            "UPDATE secw_beecham_missions SET statut='interrompu', maj_le=datetime('now') "
            "WHERE statut='en_cours'"
        ).rowcount
        c.commit()
        if n:
            incident("reconcilie_fantomes", f"{n} mission(s) en_cours orpheline(s) -> interrompu")
    except Exception as e:
        incident("reconcilie_ko", e)


def voie_libre():
    for _ in range(120):
        if not any(x["statut"] == "en_cours" for x in beecham.lister_missions(limit=80)):
            return
        time.sleep(5)


def planifier(numero):
    consigne = (
        "Tu es Beecham, tu diriges la brigade en autonomie. Commence par un BREF ÉTAT DES LIEUX "
        "(state du store/appli, avancées récentes du journal, orientation en cours), puis DÉCIDE.\n"
        "Lis le CAP en tête de " + f"{AT}/demandes_alex.md : le BUT est le métier, MAIS la PHASE "
        "ACTUELLE est la CONSTRUCTION → priorité d'exécution du moment = CODE : le HARNAIS (la brigade "
        "elle-même : boucle, contrôle, mesure), le FRONT-END (lisible, rapide, par département), le "
        "BACK-END, l'architecture. On calibre l'outil en machine de guerre ; le métier viendra après. "
        "Lis aussi " + f"{AT}/DIRECTIVES.md, {AT}/plan.md, {AT}/journal.md, et le code "
        "(app/serveur.py, app/templates/, app/beecham.py, app/roles.py). Une grosse décision "
        "d'architecture/stack se RECHERCHE et se PROPOSE à Alex, elle ne se code pas à l'aveugle. "
        "Avant de dispatcher, demande-toi si la brigade a les capacités (yeux, savoir, outils) — sinon "
        "comble le manque d'abord (ex. agent vision, banc de mesure de latence).\n\n"
        "Lis AUSSI " + f"{AT}/decisions_direction.md : ce sont TES décisions du conseil de "
        "Direction, APPLIQUE-LES. Notamment : (a) VÉRIFIE le scope contre l'état RÉEL du fichier cible "
        "avant de rédiger une consigne (lis le fichier, pas juste le backlog) ; (b) aucune mission déjà "
        "rejetée re-dispatchée à l'identique sans citer le motif du rejet précédent + ce qui change.\n\n"
        f"Planifie la VAGUE {numero} : jusqu'à {CONCURRENCE} micro-missions PETITES et STRICTEMENT "
        "INDÉPENDANTES (fichiers différents — deux missions qui partagent un fichier NE PEUVENT PAS "
        "tourner dans la même vague). Pour CHAQUE mission, DÉCLARE la liste EXACTE des fichiers "
        "qu'elle va toucher. Stack existante (FastAPI+HTMX+Jinja). Backlog épuisé => file VIDE [].\n\n"
        f"Écris SEULEMENT {AT}/file_attente.json : "
        '[{"agent":"developpeur","consigne":"…précise, scope vérifié, fichier+test…",'
        '"fichiers":["app/x.py","app/tests/test_x.py"]}, …]. L\'agent ne verra QUE sa consigne.'
    )
    mid = beecham.demarrer_mission(consigne)
    beecham.executer_mission(mid, role="chef")
    try:
        q = json.loads((ATELIER / "file_attente.json").read_text(encoding="utf-8"))
        return [m for m in q if isinstance(m, dict) and m.get("consigne")][:CONCURRENCE]
    except Exception as e:
        incident("file_illisible", e)
        return []


def _outils_vague():
    """Le kit d'outils injecté dans chaque pipeline de la vague. Le CODE (agent) reste libre
    (parallèle) ; test/revue/fusion partagent UN verrou -> sérialisation git + charge maîtrisée."""
    verrou = threading.Lock()

    def harnais(wt):
        with verrou:
            return beecham._harnais(wt)

    def controleur(scope, diff, tr, wt):
        with verrou:
            return beecham._lancer_controleur(scope, diff, tr, wt)

    def fusion(branche, wt, mid):
        with verrou:
            ok = beecham._fusion_locale(branche, wt, mid)
            if not ok:
                try:
                    beecham._git(beecham.RACINE, "merge", "--abort")
                except Exception:
                    pass
            return ok

    return {"agent": beecham._lancer_agent, "harnais": harnais, "controleur": controleur, "fusion": fusion}


def _clore_mission(m):
    """Enregistre l'issue de la mission + nettoie le worktree si besoin + grave l'incident.
    La fusion (donc le nettoyage pour 'valide'/'echec conflit') a déjà eu lieu dans le thread."""
    ctx = m.get("ctx", {})
    statut = ctx.get("statut", "echec")
    role = m.get("agent", "developpeur")
    journal = ctx.get("journal", [])
    resume = ctx.get("resume", "")
    h = ctx.get("h") or {"diff": "", "tests_ok": False, "tests_resume": "", "fichiers": []}
    statut_m = statut if statut in ("valide", "livre", "rejete", "echec") else "echec"
    # 'valide' et 'echec conflit' ont nettoyé via _fusion_locale ; les autres restent à nettoyer.
    if statut_m in ("livre", "rejete") or (statut_m == "echec" and "conflit" not in resume):
        try:
            beecham._nettoyer(m["branche"], m["wt"])
        except Exception:
            pass
    beecham._clore(m["mid"], None, statut_m, role, journal, h, resume)
    if statut_m == "rejete" and resume == "tests rouges":
        incident("tests_rouges", h["tests_resume"], m["mid"])
    elif statut_m == "rejete":
        incident("rejet_controleur", resume, m["mid"])
    elif statut_m == "echec":
        incident("conflit_fusion" if "conflit" in resume else "moteur_echec", resume, m["mid"])


def executer_vague(missions):
    # FILE-LOCK : ne garder qu'un sous-ensemble à FICHIERS DISJOINTS (les collisions sont reportées).
    retenues, pris = [], set()
    for m in missions:
        f = set(m.get("fichiers") or ["*"])
        if "*" in pris or (f & pris):
            log(f"  reportée (collision fichiers) : {m['consigne'][:45]}")
            continue
        retenues.append(m)
        pris |= f
    missions = retenues

    # worktrees EN SÉRIE (git worktree add = verrou partagé)
    prets = []
    for m in missions:
        try:
            m["mid"] = beecham.demarrer_mission(m["consigne"])
            m["branche"] = beecham.lire_mission(m["mid"])["branche"]
            m["wt"] = beecham._creer_worktree(m["branche"])
            prets.append(m)
        except Exception as e:
            incident("worktree_ko", e, m.get("mid"))

    outils = _outils_vague()
    etapes = pipelines.pipeline()  # pipeline standard (à terme choisi par mission)

    # chaque mission = un pipeline dans son thread (le code des devs est parallèle)
    def bosser(m):
        ctx = {
            "mission": {"mid": m["mid"], "consigne": m["consigne"], "role": m.get("agent", "developpeur")},
            "worktree": m["wt"],
            "branche": m["branche"],
            "outils": outils,
            "journal": [],
        }
        m["ctx"] = ctx
        try:
            executer_pipeline(etapes, ctx, BRIQUES)
        except Exception as e:
            ctx["statut"], ctx["resume"] = "echec", f"exception moteur: {e!r}"
            incident("moteur_exception", e, m["mid"])

    threads = [threading.Thread(target=bosser, args=(m,)) for m in prets]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # clôture EN SÉRIE
    for m in prets:
        _clore_mission(m)


def main():
    if STOP.exists():
        STOP.unlink()
    autre = deja_en_cours()
    if autre:
        log(f"Une boucle-beecham tourne déjà (PID {autre}) — je m'efface (singleton).")
        return
    rid = None
    try:
        rid = superviseur.enregistrer(
            os.getpid(), nom="boucle-beecham", proprietaire="beecham",
            but="boucle autonome (harnais modulaire, pipelines)",
        )
    except Exception as e:
        incident("superviseur_enregistrer_ko", e)
    reconcilier_fantomes()
    vague, vides = 0, 0
    try:
        while vague < MAX_VAGUES:
            if STOP.exists():
                log("STOP demandé — Beecham s'arrête proprement (fin de vague).")
                break
            voie_libre()
            vague += 1
            log(f"=== VAGUE {vague} : Beecham fait l'état des lieux et décide ===")
            try:
                missions = planifier(vague)
                if not missions:
                    vides += 1
                    log(f"  rien d'utile à dispatcher (vague vide {vides}/2)")
                    if vides >= 2:
                        log("Backlog sec — Beecham se met en veille.")
                        break
                    time.sleep(20)
                    continue
                vides = 0
                log(f"  {len(missions)} missions indépendantes -> pipelines EN PARALLÈLE")
                executer_vague(missions)
                log(f"=== VAGUE {vague} terminée ===")
            except Exception as e:
                incident("crash_vague", f"vague {vague}: {e!r}")
                time.sleep(20)
    finally:
        if rid:
            try:
                superviseur.finir(rid)
            except Exception:
                pass
    log("=== SERVICE BEECHAM EN VEILLE ===")


if __name__ == "__main__":
    main()
