from fastapi.testclient import TestClient

import beecham
import boite
import brief
import monitoring
import planif
import relances
import store
from bench_latence import ROUTES_A_MESURER, formater_tableau, mesurer_routes
from serveur import app


def _client():
    return TestClient(app)


def test_mesurer_routes(monkeypatch):
    # Mêmes mocks que test_routes.py/test_beecham_routes.py/test_services_routes.py pour
    # ces mêmes vues : store réel non garanti en test (fail-soft ailleurs), et
    # planif.lister_taches/monitoring.etat_moteur ne le sont pas (schtasks réel / connexion
    # non gardée) — sans mock, la mesure serait non déterministe ou lèverait un 500.
    monkeypatch.setattr(
        brief,
        "construire",
        lambda chemin=None: {
            "mails_a_traiter": 0,
            "relances": 0,
            "taches_retard": 0,
            "phrase": "RAS",
        },
    )
    monkeypatch.setattr(boite, "lire_boite", lambda chemin=None, limite=50: [])
    monkeypatch.setattr(store, "lire_taches", lambda kind, chemin=None: [])
    monkeypatch.setattr(
        relances,
        "etat",
        lambda: {"disponible": False, "devis": [], "factures": [], "message": "test"},
    )
    monkeypatch.setattr(
        monitoring,
        "etat_moteur",
        lambda chemin=None: {
            "collecte_active": False,
            "dernier_passage": None,
            "entrees_jour": 0,
            "a_traiter": 0,
        },
    )
    monkeypatch.setattr(planif, "lister_taches", lambda: [])
    monkeypatch.setattr(beecham, "lister_missions", lambda chemin=None, limit=20: [])
    monkeypatch.setattr(beecham, "lister_atelier", lambda: [])

    mesures = mesurer_routes(_client())

    assert len(mesures) == len(ROUTES_A_MESURER)
    for m in mesures:
        assert m["statut"] == 200
        assert isinstance(m["secondes"], float) and m["secondes"] >= 0

    plus_lente = max(m["secondes"] for m in mesures)
    assert plus_lente < 5.0  # garde-fou large, pas une contrainte de perf serrée

    print(formater_tableau(mesures))
