"""Le pipeline « standard » (moteur + vraies briques) doit reproduire EXACTEMENT le comportement
du harnais historique, sur les 5 cas. Outils factices — aucune dépendance git/claude."""

from harnais.briques import BRIQUES
from harnais.moteur import executer_pipeline
from harnais.pipelines import pipeline


def _ctx(outils, consigne="fais X"):
    return {
        "mission": {"mid": "m1", "consigne": consigne, "role": "developpeur"},
        "worktree": "/wt",
        "branche": "b1",
        "outils": outils,
    }


def _agent(session_id="SID-1"):
    def agent(role, consigne, worktree, reprendre=None, modele=None):
        return {"journal": [f"{role} · code"], "texte": "fait", "session_id": session_id}

    return agent


def test_accepte_fusionne():
    outils = {
        "agent": _agent(),
        "harnais": lambda wt: {"diff": "diff+", "tests_ok": True, "tests_resume": "1 passed"},
        "controleur": lambda *a: {"verdict": "accepte", "raison": "ok"},
        "fusion": lambda *a: True,
    }
    ctx = executer_pipeline(pipeline("standard"), _ctx(outils), BRIQUES)
    assert ctx["statut"] == "valide"
    assert [t[0] for t in ctx["trace"]] == ["code", "test", "revue", "fusion"]


def test_corriger_puis_reprise_puis_accepte():
    """« corriger » -> reprise (code relancé avec --resume) -> re-test -> re-revue accepte ->
    fusion. Le code doit tourner DEUX fois, et le statut final valide."""
    tours = {"code": 0, "revue": 0}

    def agent(role, consigne, worktree, reprendre=None, modele=None):
        tours["code"] += 1
        return {"journal": [], "session_id": "SID-1"}

    def controleur(*a):
        tours["revue"] += 1
        return {"verdict": "corriger" if tours["revue"] == 1 else "accepte", "raison": "corrige la ligne 3"}

    outils = {
        "agent": agent,
        "harnais": lambda wt: {"diff": "diff+", "tests_ok": True, "tests_resume": "1 passed"},
        "controleur": controleur,
        "fusion": lambda *a: True,
    }
    ctx = executer_pipeline(pipeline("standard"), _ctx(outils), BRIQUES)
    assert tours["code"] == 2  # reprise
    assert tours["revue"] == 2
    assert ctx["statut"] == "valide"


def test_rejeter_abandonne():
    outils = {
        "agent": _agent(),
        "harnais": lambda wt: {"diff": "diff+", "tests_ok": True, "tests_resume": "1 passed"},
        "controleur": lambda *a: {"verdict": "rejeter", "raison": "approche mauvaise"},
        "fusion": lambda *a: True,
    }
    ctx = executer_pipeline(pipeline("standard"), _ctx(outils), BRIQUES)
    assert ctx["statut"] == "rejete"
    assert "fusion" not in [t[0] for t in ctx["trace"]]  # jamais fusionné


def test_tests_rouges_rejette():
    outils = {
        "agent": _agent(),
        "harnais": lambda wt: {"diff": "diff+", "tests_ok": False, "tests_resume": "1 failed, 9 passed"},
        "controleur": lambda *a: {"verdict": "accepte", "raison": "ok"},  # jamais atteint
        "fusion": lambda *a: True,
    }
    ctx = executer_pipeline(pipeline("standard"), _ctx(outils), BRIQUES)
    assert ctx["statut"] == "rejete"
    assert ctx["resume"] == "tests rouges"
    assert [t[0] for t in ctx["trace"]] == ["code", "test"]  # revue/fusion non atteintes


def test_diff_vide_est_livre():
    outils = {
        "agent": _agent(),
        "harnais": lambda wt: {"diff": "   ", "tests_ok": True, "tests_resume": "0 tests"},
        "controleur": lambda *a: {"verdict": "accepte", "raison": "ok"},
        "fusion": lambda *a: True,
    }
    ctx = executer_pipeline(pipeline("standard"), _ctx(outils), BRIQUES)
    assert ctx["statut"] == "livre"
    assert ctx["resume"] == "livré (rien à coder)"


def test_corriger_sans_session_ne_boucle_pas():
    """Si l'agent n'a pas renvoyé de session_id, « corriger » ne peut pas reprendre -> rejet
    propre (pas de saut sans session)."""
    def agent(role, consigne, worktree, reprendre=None, modele=None):
        return {"journal": []}  # pas de session_id

    outils = {
        "agent": agent,
        "harnais": lambda wt: {"diff": "diff+", "tests_ok": True, "tests_resume": "1 passed"},
        "controleur": lambda *a: {"verdict": "corriger", "raison": "à revoir"},
        "fusion": lambda *a: True,
    }
    ctx = executer_pipeline(pipeline("standard"), _ctx(outils), BRIQUES)
    assert ctx["statut"] == "rejete"
