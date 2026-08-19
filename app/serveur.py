"""Monique — serveur FastAPI (Phase 1, lecture seule).

Sert la coquille HTML + des fragments HTMX. Écoute UNIQUEMENT 127.0.0.1:8770.
Ne lancer que via les scripts start_secretaire.* (pas au boot tant que la
bascule n'est pas décidée).
"""

import json
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import actions as actions_mod
import beecham
import blueprint
import boite
import brief
import config
import digest as digest_module
import entrepot
import fournisseurs
import fournisseurs_materiel
import monitoring
import orchestrateur
import overlays
import parametres
import planif
import relances
import roles
import secretaire_actions
import store
import superviseur
import vue_missions
import vue_usage

BASE = Path(__file__).parent
tpl = Jinja2Templates(directory=str(BASE / "templates"))


def _en_retard(echeance: str | None) -> bool:
    return bool(echeance) and echeance < date.today().isoformat()


tpl.env.globals["en_retard"] = _en_retard


def _reconciliation_periodique(intervalle=900):
    """D-16, trou B : réconciliation CONTINUE du superviseur, pas seulement au
    boot ou sur clic manuel (`/processus/balayer`). Sans cette boucle, un
    process qui devient orphelin entre deux boots reste invisible jusqu'au
    prochain redémarrage du serveur. `auto_tuer=True` est sûr par
    construction : `superviseur` n'agit QUE sur des PID que Monique a
    elle-même enregistrés, jamais un tiers (cf. docstring superviseur.py).
    """
    while True:
        try:
            superviseur.balayer(auto_tuer=True)
        except Exception:
            pass
        time.sleep(intervalle)


@asynccontextmanager
async def lifespan(app):
    # revue D : garantir que la write-DB du mode courant porte les tables secw_ AVANT le
    # premier GET (sinon reglages/planif/fournisseurs sont cassés au premier boot réel).
    # Fail-soft : un hoquet d'init ne doit pas empêcher de servir (dégradé mais debout).
    try:
        entrepot.init_fondations()  # chemin_ecriture() : shadow en test, réel en prod
    except Exception:
        pass
    # Superviseur (D-16) : au boot on RÉCONCILIE (nettoie les records morts des runs précédents +
    # signale les orphelins vivants) et on INSCRIT le serveur lui-même — pour qu'il soit au tableau
    # et coupable. Fail-soft : jamais bloquer le démarrage pour ça.
    try:
        superviseur.balayer()
        superviseur.enregistrer(
            os.getpid(),
            nom="serveur",
            proprietaire="monique",
            but="serveur FastAPI :8790",
        )
    except Exception:
        pass
    # D-16, trou B : réconciliation périodique pendant que le serveur tourne (pas
    # seulement au boot / clic manuel) — même patron thread daemon que les missions
    # Beecham plus bas dans ce fichier.
    threading.Thread(target=_reconciliation_periodique, daemon=True).start()
    yield


app = FastAPI(title="Monique", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")


@app.get("/sante")
def sante():
    return {"ok": True}


@app.get("/vue/jour", response_class=HTMLResponse)
def vue_jour(request: Request):
    return tpl.TemplateResponse(request, "vue_jour.html", {"brief": brief.construire()})


@app.get("/vue/boite", response_class=HTMLResponse)
def vue_boite(request: Request):
    return tpl.TemplateResponse(
        request, "vue_boite.html", {"items": boite.lire_boite()}
    )


@app.get("/vue/faire", response_class=HTMLResponse)
def vue_faire(request: Request):
    return tpl.TemplateResponse(
        request, "vue_faire.html", {"taches": store.lire_taches("a_faire")}
    )


@app.post("/taches/{tache_id}/cocher", response_class=HTMLResponse)
def cocher_tache(request: Request, tache_id: int):
    overlays.cocher_tache(tache_id)
    return tpl.TemplateResponse(
        request, "vue_faire.html", {"taches": store.lire_taches("a_faire")}
    )


# --- Maître-détail de la Boîte (Phase 2b, Tasks 4-6) -----------------------------------


def _item(event_id):
    for it in boite.lire_boite():
        if it["id"] == event_id:
            return it
    return {
        "id": event_id,
        "source": "?",
        "apercu": "",
        "timestamp": "",
        "traite": False,
    }


def _detail_ctx(event_id):
    ev = boite.lire_event(event_id)
    return {
        "item": _item(event_id),
        "contenu_complet": (ev or {}).get("contenu", ""),
        "b": overlays.lire_brouillon(event_id),
        "actions": actions_mod.disponibles(),
        "resultat_action": None,
    }


@app.get("/boite/{event_id}", response_class=HTMLResponse)
def detail(request: Request, event_id: int):
    return tpl.TemplateResponse(request, "detail_boite.html", _detail_ctx(event_id))


@app.post("/boite/{event_id}/amorcer", response_class=HTMLResponse)
def amorcer(request: Request, event_id: int):
    ev = boite.lire_event(event_id) or _item(
        event_id
    )  # revue M2 : plein texte, pas l'aperçu 140c
    secretaire_actions.amorcer_brouillon(
        event_id, ev.get("contenu", ev.get("apercu", "")), ev["source"]
    )
    return tpl.TemplateResponse(request, "detail_boite.html", _detail_ctx(event_id))


@app.post("/boite/{event_id}/parler", response_class=HTMLResponse)
def parler(request: Request, event_id: int, consigne: str = Form(...)):
    secretaire_actions.reprendre_brouillon(event_id, consigne)
    return tpl.TemplateResponse(request, "detail_boite.html", _detail_ctx(event_id))


# Dispatcher générique des boutons du registre (revue M3). Déclaré APRÈS les routes
# spécifiques ci-dessus (amorcer/parler) pour ne pas les capter ; ceinture-bretelles
# (revue red-team M5) : les noms réservés sont AUSSI exclus explicitement dans le handler,
# pour ne pas dépendre uniquement de l'ordre de déclaration des routes.
_NOMS_RESERVES = {"amorcer", "parler"}


@app.post("/boite/{event_id}/{nom}", response_class=HTMLResponse)
def action_generique(request: Request, event_id: int, nom: str):
    if nom in _NOMS_RESERVES:
        raise HTTPException(status_code=404)
    a = actions_mod.registre.get(nom)
    resultat = None
    if a and (a.check_fn is None or a.check_fn()):
        try:
            resultat = a.handler(event_id=event_id)
        except Exception:
            resultat = None
    ctx = _detail_ctx(event_id)
    ctx["resultat_action"] = resultat
    return tpl.TemplateResponse(request, "detail_boite.html", ctx)


@app.get("/vue/relances", response_class=HTMLResponse)
def vue_relances(request: Request):
    return tpl.TemplateResponse(request, "vue_relances.html", {"r": relances.etat()})


@app.get("/vue/monitoring", response_class=HTMLResponse)
def vue_monitoring(request: Request):
    return tpl.TemplateResponse(
        request,
        "vue_monitoring.html",
        {"m": monitoring.etat_moteur(), "chantier": monitoring.chantier_brigade()},
    )


# --- Services transverses (Phase 3, Batch C) : Réglages / Planificateur / Fournisseurs -----------


def _reglages_ctx(enregistre=False, enregistre_chercheur=False):
    return {
        "veille_freq": config.cfg_get("secretaire", "veille_freq", "2x/jour"),
        "canaux": config.cfg_get("secretaire", "canaux", "mail,wa,sms"),
        "options_freq": ["1x/jour", "2x/jour", "3x/jour", "toutes les heures"],
        "enregistre": enregistre,
        "chercheur_veille_freq": config.cfg_get("chercheur", "veille_freq", "1x/jour"),
        "chercheur_canaux": config.cfg_get("chercheur", "canaux", "web"),
        "enregistre_chercheur": enregistre_chercheur,
    }


@app.get("/vue/reglages", response_class=HTMLResponse)
def vue_reglages(request: Request):
    return tpl.TemplateResponse(request, "vue_reglages.html", _reglages_ctx())


@app.post("/reglages", response_class=HTMLResponse)
def maj_reglages(
    request: Request, veille_freq: str = Form(...), canaux: str = Form(...)
):
    parametres.definir(
        "secretaire.veille_freq", veille_freq
    )  # -> shadow en test (chemin_ecriture)
    parametres.definir("secretaire.canaux", canaux)
    return tpl.TemplateResponse(
        request, "vue_reglages.html", _reglages_ctx(enregistre=True)
    )


@app.post("/reglages/chercheur", response_class=HTMLResponse)
def maj_reglages_chercheur(
    request: Request, veille_freq: str = Form(...), canaux: str = Form(...)
):
    parametres.definir("chercheur.veille_freq", veille_freq)
    parametres.definir("chercheur.canaux", canaux)
    return tpl.TemplateResponse(
        request, "vue_reglages.html", _reglages_ctx(enregistre_chercheur=True)
    )


def _fournisseurs_materiel_ctx():
    return {"fournisseurs": fournisseurs_materiel.lister_fournisseurs()}


@app.get("/vue/fournisseurs-materiel", response_class=HTMLResponse)
def vue_fournisseurs_materiel(request: Request):
    return tpl.TemplateResponse(
        request, "vue_fournisseurs_materiel.html", _fournisseurs_materiel_ctx()
    )


def _missions_actives_ctx():
    return {"missions": vue_missions.contexte_missions_actives()}


@app.get("/vue/missions-actives", response_class=HTMLResponse)
def vue_missions_actives_route(request: Request):
    return tpl.TemplateResponse(
        request, "vue_missions_actives.html", _missions_actives_ctx()
    )


def _recherche_ctx():
    notes = sorted(
        (n for n in beecham.lister_atelier() if n["chemin"].startswith("connaissances/")),
        key=lambda n: n["chemin"],
    )
    return {"notes": notes}


@app.get("/vue/recherche", response_class=HTMLResponse)
def vue_recherche(request: Request):
    return tpl.TemplateResponse(request, "vue_recherche.html", _recherche_ctx())


def _planif_ctx(cree=None, erreur=None):
    # lister_taches = LECTURE seule des vraies tâches ; prod-gate pour le bouton « Appliquer »
    return {
        "taches": planif.lister_taches(),
        "prod": config.mode() == "prod",
        "cree": cree,
        "erreur": erreur,
    }


@app.get("/vue/planif", response_class=HTMLResponse)
def vue_planif(request: Request):
    return tpl.TemplateResponse(request, "vue_planif.html", _planif_ctx())


@app.post("/planif/creer", response_class=HTMLResponse)
def creer_planif(
    request: Request,
    module: str = Form(...),
    libelle: str = Form(...),
    modele: str = Form(...),
    valeur: str = Form(...),
):
    # revue E : retour explicite (erreur vs succès), plus d'échec muet.
    cree = erreur = None
    if not module.strip() or not libelle.strip():
        erreur = "Agent et libellé sont requis."
    else:
        try:
            valeurs = (
                {"minutes": valeur}
                if modele == "toutes_les_n_min"
                else {"heure": valeur}
            )
            planning = blueprint.remplir(
                modele, valeurs
            )  # valide heure/minutes (revue E)
            blueprint.creer_job(
                module, libelle, planning
            )  # méta-job shadow, ne touche PAS schtasks
            cree = libelle
        except (ValueError, KeyError) as e:
            erreur = str(e) or "Entrée invalide."
    return tpl.TemplateResponse(
        request, "vue_planif.html", _planif_ctx(cree=cree, erreur=erreur)
    )


def _fournisseurs_ctx(cle_ok=False):
    provs = []
    for p in fournisseurs.REGISTRE.values():
        env_var = getattr(p, "env_var", "") or ""
        provs.append(
            {
                "nom": p.nom,
                "mode": p.mode,
                "model": getattr(p, "model", "") or "",
                "env_var": env_var,
                "cle_presente": bool(
                    env_var and fournisseurs.lire_cle(env_var)
                ),  # présence, jamais la valeur
            }
        )
    return {
        "fournisseurs": provs,
        "usage": fournisseurs.usage_par_agent("secretaire"),
        "cle_ok": cle_ok,
    }


@app.get("/vue/fournisseurs", response_class=HTMLResponse)
def vue_fournisseurs(request: Request):
    return tpl.TemplateResponse(request, "vue_fournisseurs.html", _fournisseurs_ctx())


def _env_vars_declares() -> set:
    return {
        getattr(p, "env_var", "")
        for p in fournisseurs.REGISTRE.values()
        if getattr(p, "env_var", "")
    }


@app.post("/fournisseurs/cle", response_class=HTMLResponse)
def maj_cle(request: Request, env_var: str = Form(...), valeur: str = Form(...)):
    # revue C : n'accepter QUE les env_var déclarés dans le REGISTRE (whitelist) — pas de PATH & co.
    ok = False
    if valeur and env_var in _env_vars_declares():
        try:
            fournisseurs.ecrire_cle(
                env_var, valeur
            )  # -> coffre, jamais le store ni un log ; valide \n/=
            ok = True
        except ValueError:
            ok = False  # clé/nom invalide (injection de ligne, etc.) -> refus silencieux, rien écrit
    # la valeur n'est jamais renvoyée dans la réponse (seulement l'état « enregistrée »)
    return tpl.TemplateResponse(
        request, "vue_fournisseurs.html", _fournisseurs_ctx(cle_ok=ok)
    )


# --- Onglet « Agents » (Orchestrateur Task 6) : brigade + suggestions, lecture seule ------------

_AVATARS = BASE / "static" / "avatars"


def _avatar(nom: str):
    for ext in (".png", ".jpg"):
        if (_AVATARS / f"{nom}{ext}").exists():
            return f"/static/avatars/{nom}{ext}"
    return None


def _agents_ctx():
    carte = roles.carte_departements()
    departements = [
        {
            "nom": dep,
            "agents": [
                {
                    "nom": nom,
                    "description": f.get("description", ""),
                    "triggers": f.get("triggers", []),
                    "avatar": _avatar(nom),
                }
                for nom, f in sorted(agents_dep.items())
            ],
        }
        for dep, agents_dep in carte.items()
    ]
    return {"departements": departements, "suggestions": orchestrateur.suggerer()}


@app.get("/vue/agents", response_class=HTMLResponse)
def vue_agents(request: Request):
    return tpl.TemplateResponse(request, "vue_agents.html", _agents_ctx())


# --- Onglet « Beecham » (chef d'orchestre) : missions gardées, l'utilisateur valide -------------


LIBELLES_STATUT = {
    "en_cours": "En cours",
    "propose": "Proposé",
    "valide": "Validé",
    "rejete": "Rejeté",
    "echec": "Échec",
    "livre": "Livré",
    "bloque": "Bloqué",
}


def _decoder_missions(missions):
    # journal/tests_json sont des chaînes JSON en base -> décodées ICI (fail-soft), jamais dans Jinja.
    out = []
    for m in missions:
        d = dict(m)
        try:
            d["journal_liste"] = json.loads(d.get("journal") or "[]")
        except (TypeError, ValueError):
            d["journal_liste"] = []
        try:
            d["tests"] = json.loads(d.get("tests_json") or "null")
        except (TypeError, ValueError):
            d["tests"] = None
        try:
            d["agents"] = json.loads(d.get("agents_json") or "[]")
        except (TypeError, ValueError):
            d["agents"] = []
        d["statut_libelle"] = LIBELLES_STATUT.get(
            d.get("statut"), (d.get("statut") or "").capitalize()
        )
        out.append(d)
    return out


def _beecham_ctx():
    missions = _decoder_missions(beecham.lister_missions())
    try:
        digest = (
            (beecham.ATELIER / "journal.md").read_text(encoding="utf-8")
            if (beecham.ATELIER / "journal.md").exists()
            else ""
        )
    except OSError:
        digest = ""
    digest_resume = digest_module.digest_texte(digest, n_dernieres=20)
    return {
        "missions": missions,
        "roles": list(beecham.ROLES),
        "en_cours_actif": any(m.get("statut") == "en_cours" for m in missions),
        "digest": digest,
        "digest_resume": digest_resume,
        "atelier": beecham.lister_atelier(),
    }


def _processus_ctx():
    return {"procs": superviseur.etat(), "orphelins": superviseur.orphelins_vivants()}


@app.get("/vue/processus", response_class=HTMLResponse)
def vue_processus(request: Request):
    return tpl.TemplateResponse(request, "vue_processus.html", _processus_ctx())


@app.post("/processus/balayer", response_class=HTMLResponse)
def balayer_processus(request: Request):
    superviseur.balayer(
        auto_tuer=True
    )  # nettoie les morts + COUPE les orphelins vivants
    return tpl.TemplateResponse(request, "vue_processus.html", _processus_ctx())


@app.post("/processus/{rid}/tuer", response_class=HTMLResponse)
def tuer_processus(request: Request, rid: str):
    superviseur.tuer(rid)  # coupe ce process + tout son sous-arbre
    return tpl.TemplateResponse(request, "vue_processus.html", _processus_ctx())


@app.get("/vue/beecham", response_class=HTMLResponse)
def vue_beecham(request: Request):
    return tpl.TemplateResponse(request, "vue_beecham.html", _beecham_ctx())


@app.get("/vue/usage", response_class=HTMLResponse)
def vue_usage_html(request: Request):
    return tpl.TemplateResponse(
        request,
        "vue_usage.html",
        {
            "usage": vue_usage.contexte_usage(),
            "previsionnel": vue_usage.previsionnel_multi_fournisseurs(),
        },
    )


@app.post("/beecham/mission", response_class=HTMLResponse)
def creer_mission_beecham(
    request: Request, consigne: str = Form(...), role: str = Form(...)
):
    mid = beecham.demarrer_mission(consigne)
    # exécution LONGUE (vraie session claude + tests) -> thread de fond, la requête revient de suite ;
    # la mission passe en_cours -> propose en arrière-plan (le poll htmx du template la rattrape).
    threading.Thread(
        target=beecham.executer_mission, args=(mid, role), daemon=True
    ).start()
    return tpl.TemplateResponse(request, "vue_beecham.html", _beecham_ctx())


@app.post("/beecham/{mid}/valider", response_class=HTMLResponse)
def valider_mission_beecham(request: Request, mid: str):
    beecham.valider(mid)
    return tpl.TemplateResponse(request, "vue_beecham.html", _beecham_ctx())


@app.post("/beecham/{mid}/rejeter", response_class=HTMLResponse)
def rejeter_mission_beecham(request: Request, mid: str):
    beecham.rejeter(mid)
    return tpl.TemplateResponse(request, "vue_beecham.html", _beecham_ctx())


@app.get("/", response_class=HTMLResponse)
def racine(request: Request):
    # revue red-team H3 : plus de pré-rendu réinjecté en |safe — include autoéchappé côté coquille
    return tpl.TemplateResponse(
        request,
        "coquille.html",
        {"date": date.today().strftime("%d/%m/%Y"), "brief": brief.construire()},
    )
