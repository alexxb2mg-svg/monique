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


def _echecs_recents(n=6):
    """Sert à Beecham ses derniers ÉCHECS avec le rapport du réviseur — la MATIÈRE pour diagnostiquer
    au lieu de re-dispatcher à l'aveugle. Lu depuis le journal d'incidents (déjà écrit par la boucle),
    croisé avec le sujet de la mission. On donne l'info ; on ne dicte pas quoi en penser."""
    try:
        lignes = INCIDENTS.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    rejets = []
    for li in reversed(lignes):
        try:
            r = json.loads(li)
        except Exception:
            continue
        if r.get("type") in ("rejet_controleur", "tests_rouges", "moteur_echec", "reprise_ko"):
            rejets.append(r)
        if len(rejets) >= n:
            break
    if not rejets:
        return "Aucun échec récent à analyser."
    try:
        sujets = {m["id"]: (m.get("consigne") or "")[:80] for m in beecham.lister_missions(limit=40)}
    except Exception:
        sujets = {}
    out = []
    for r in rejets:
        suj = sujets.get(r.get("mid"), "(sujet inconnu)")
        out.append(f"- [{r.get('type')}] {suj} → {str(r.get('detail'))[:280]}")
    return "\n".join(out)


def planifier(numero):
    echecs = _echecs_recents()
    consigne = (
        "Tu es Beecham, le directeur de la brigade. Tu es intelligent : tu ne dispatches pas à "
        "l'aveugle, tu réfléchis d'abord comme un chef de projet, avec la matière ci-dessous, puis "
        "tu décides à ta façon. Ce qui suit est une démarche et des données, pas une checklist à cocher.\n\n"
        "ÉTAT DES LIEUX. Où en est-on vraiment ? Appuie-toi sur "
        + f"{AT}/decisions_direction.md (TES décisions passées = ton CAP, tiens-t'y et construis dessus), "
        + f"{AT}/plan.md, {AT}/journal.md, le CAP en tête de {AT}/demandes_alex.md, {AT}/DIRECTIVES.md, "
        "et le CODE RÉEL (app/serveur.py, app/templates/, app/harnais/, app/beecham.py). PHASE ACTUELLE = "
        "CONSTRUCTION de l'outil (harnais, front par département, back, archi) ; le métier viendra après.\n\n"
        "APPRENDS DE CE QUI A RATÉ (rapports réels du réviseur) :\n" + echecs + "\n"
        "Demande-toi honnêtement, pour chacun : pourquoi ça a VRAIMENT échoué — sujet infaisable, "
        "approche mauvaise, test mal conçu, cause pas comprise ? Ne relance un sujet déjà raté QUE si tu "
        "as compris la cause ET changes d'approche ; sinon diagnostique-le d'abord (mission de lecture "
        "seule) ou abandonne-le. S'acharner à l'identique, c'est se cogner au mur.\n\n"
        "DÉLIBÈRE comme un humain le ferait : pourquoi ce sujet maintenant, comment l'atteindre "
        "proprement, QUI (quel persona) est le bon, quand. Envisage plusieurs pistes, pèse-les, TRANCHE, "
        "et sache pourquoi tu tranches ainsi. Une grosse décision d'archi se RECHERCHE et se PROPOSE à "
        "Alex, jamais codée à l'aveugle.\n\n"
        "GRAVE TA DÉCISION : ajoute UNE ligne datée à " + f"{AT}/decisions_direction.md disant ce que tu "
        "décides pour cette vague et POURQUOI — c'est ainsi que tu tiens un cap d'une vague à l'autre.\n\n"
        f"PUIS DISPATCHE la VAGUE {numero}. Écris SEULEMENT {AT}/file_attente.json : jusqu'à {CONCURRENCE} micro-missions "
        "PETITES et STRICTEMENT INDÉPENDANTES (fichiers DIFFÉRENTS — deux missions partageant un fichier "
        "ne tournent pas ensemble). Pour CHAQUE : consigne précise, scope VÉRIFIÉ contre l'état réel du "
        "fichier (lis-le), liste EXACTE des fichiers touchés. Backlog épuisé => file VIDE [].\n"
        'Format : [{"agent":"developpeur","consigne":"…","fichiers":["app/x.py","app/tests/test_x.py"]}, …]. '
        "L'agent ne verra QUE sa consigne."
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
