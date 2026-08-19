from fastapi.testclient import TestClient

import beecham
import brief
import relances
import serveur
import store
import superviseur
from serveur import app


def test_page_coquille(monkeypatch):
    monkeypatch.setattr(
        brief,
        "construire",
        lambda chemin=None: {
            "mails_a_traiter": 3,
            "relances": 2,
            "taches_retard": 1,
            "phrase": "Ce matin, 3...",
        },
    )
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "Aujourd" in r.text and "onglet" in r.text.lower()


def test_vue_faire(monkeypatch):
    monkeypatch.setattr(
        store,
        "lire_taches",
        lambda kind, chemin=None: [
            {"titre": "Rappeler Consuel", "echeance": "2026-08-14", "statut": "a_faire"}
        ],
    )
    r = TestClient(app).get("/vue/faire")
    assert r.status_code == 200 and "Rappeler Consuel" in r.text


def test_vue_relances(monkeypatch):
    monkeypatch.setattr(
        relances,
        "etat",
        lambda: {
            "disponible": True,
            "devis": [{"ref": "D26070009", "montant": 4120}],
            "factures": [],
            "message": "ok",
        },
    )
    r = TestClient(app).get("/vue/relances")
    assert r.status_code == 200 and "D26070009" in r.text


def test_api_processus(monkeypatch):
    monkeypatch.setattr(
        superviseur,
        "etat",
        lambda chemin=None: [{"rid": "abc123", "commande": "claude", "statut": "running"}],
    )
    monkeypatch.setattr(superviseur, "orphelins_vivants", lambda chemin=None: [])
    r = TestClient(app).get("/api/processus")
    assert r.status_code == 200
    corps = r.json()
    assert "procs" in corps and "orphelins" in corps
    assert corps["procs"][0]["rid"] == "abc123"


def test_vue_recherche(monkeypatch):
    monkeypatch.setattr(
        beecham,
        "lister_atelier",
        lambda: [
            {"chemin": "connaissances/diagnostic_d4_nav_departements.md", "octets": 4321},
            {"chemin": "roles/chef_dev/ROLE.md", "octets": 512},
        ],
    )
    r = TestClient(app).get("/vue/recherche")
    assert r.status_code == 200
    assert "diagnostic_d4_nav_departements.md" in r.text
    assert "ROLE.md" not in r.text


def test_reconciliation_periodique_appelle_balayer_auto_tuer(monkeypatch):
    # D-16, trou B : la boucle de fond doit réconcilier avec auto_tuer=True, pas
    # seulement au boot / clic manuel. On casse la boucle infinie au premier tour
    # via un faux time.sleep qui lève SystemExit — jamais de vrai sleep en test.
    appels = []
    monkeypatch.setattr(superviseur, "balayer", lambda auto_tuer=False: appels.append(auto_tuer))

    def _sleep_qui_coupe(_intervalle):
        raise SystemExit

    monkeypatch.setattr(serveur.time, "sleep", _sleep_qui_coupe)

    try:
        serveur._reconciliation_periodique(intervalle=0)
    except SystemExit:
        pass

    assert appels == [True]
