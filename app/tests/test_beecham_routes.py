from fastapi.testclient import TestClient

import beecham
from serveur import app


def _client():
    return TestClient(app)


def _mission_propose(mid="m1"):
    return {
        "id": mid,
        "consigne": "ajouter un module bonjour",
        "statut": "propose",
        "branche": f"beecham/{mid}",
        "plan": None,
        "agents_json": '["developpeur"]',
        "journal": '["developpeur \\u00b7 Write bonjour.py", "harnais \\u00b7 tests: 1 passed"]',
        "diff": "+VALEUR = 42\n<script>alert(1)</script>",
        "tests_json": '{"ok": true, "resume": "1 passed", "fichiers": ["app/bonjour.py"]}',
        "suggestions_agents": None,
        "cree_le": "2026-08-19T10:00:00",
        "maj_le": "2026-08-19T10:05:00",
    }


# --- GET /vue/beecham -------------------------------------------------------------------


def test_vue_beecham_affiche_mission_proposee(monkeypatch):
    monkeypatch.setattr(
        beecham, "lister_missions", lambda chemin=None, limit=20: [_mission_propose()]
    )
    r = _client().get("/vue/beecham")
    assert r.status_code == 200
    assert "ajouter un module bonjour" in r.text
    assert "propose" in r.text
    assert "1 passed" in r.text
    assert "VALEUR = 42" in r.text
    # boutons de décision présents
    assert 'hx-post="/beecham/m1/valider"' in r.text
    assert 'hx-post="/beecham/m1/rejeter"' in r.text


def test_vue_beecham_echappe_le_diff_xss(monkeypatch):
    monkeypatch.setattr(
        beecham, "lister_missions", lambda chemin=None, limit=20: [_mission_propose()]
    )
    r = _client().get("/vue/beecham")
    assert "<script>alert(1)</script>" not in r.text  # jamais brut
    assert "&lt;script&gt;" in r.text  # échappé par autoescape (pas de |safe)


def test_vue_beecham_liste_vide(monkeypatch):
    monkeypatch.setattr(beecham, "lister_missions", lambda chemin=None, limit=20: [])
    r = _client().get("/vue/beecham")
    assert r.status_code == 200
    assert "Aucune mission encore." in r.text


def test_vue_beecham_en_cours_declenche_le_poll(monkeypatch):
    m = _mission_propose()
    m["statut"] = "en_cours"
    monkeypatch.setattr(beecham, "lister_missions", lambda chemin=None, limit=20: [m])
    r = _client().get("/vue/beecham")
    assert "en cours" in r.text
    assert 'hx-trigger="every 4s"' in r.text  # auto-refresh htmx


# --- POST /beecham/mission --------------------------------------------------------------


def test_creer_mission_lance_un_thread_sans_executer_pour_de_vrai(monkeypatch):
    demarres = []
    executes = []

    monkeypatch.setattr(
        beecham,
        "demarrer_mission",
        lambda consigne, chemin=None: demarres.append(consigne) or "m9",
    )
    # executer_mission JAMAIS appelé pour de vrai (pas de claude) : mock no-op qui enregistre l'appel
    monkeypatch.setattr(
        beecham,
        "executer_mission",
        lambda mid, role="developpeur", chemin=None, _agent=None: executes.append(
            (mid, role)
        ),
    )
    monkeypatch.setattr(beecham, "lister_missions", lambda chemin=None, limit=20: [])

    r = _client().post(
        "/beecham/mission", data={"consigne": "corrige le bug X", "role": "developpeur"}
    )
    assert r.status_code == 200
    assert demarres == ["corrige le bug X"]

    # le thread de fond tourne en parallèle : laisser une chance au scheduler de le dérouler
    import time

    for _ in range(50):
        if executes:
            break
        time.sleep(0.02)
    assert executes == [("m9", "developpeur")]


# --- POST /beecham/{mid}/valider et /rejeter --------------------------------------------


def test_valider_appelle_beecham_valider(monkeypatch):
    appels = []
    monkeypatch.setattr(
        beecham, "valider", lambda mid, chemin=None: appels.append(mid) or {"ok": True}
    )
    monkeypatch.setattr(beecham, "lister_missions", lambda chemin=None, limit=20: [])
    r = _client().post("/beecham/m1/valider")
    assert r.status_code == 200
    assert appels == ["m1"]


def test_rejeter_appelle_beecham_rejeter(monkeypatch):
    appels = []
    monkeypatch.setattr(
        beecham, "rejeter", lambda mid, chemin=None: appels.append(mid) or {"ok": True}
    )
    monkeypatch.setattr(beecham, "lister_missions", lambda chemin=None, limit=20: [])
    r = _client().post("/beecham/m1/rejeter")
    assert r.status_code == 200
    assert appels == ["m1"]
