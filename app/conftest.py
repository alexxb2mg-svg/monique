# Ancre pytest : rend le dossier app/ importable (imports plats : serveur, store, ...).
import pytest


@pytest.fixture(autouse=True)
def _mode_test(monkeypatch):
    # revue Orchestrateur MAJEUR-2 : filet d'isolation — toute la suite tourne en MODE=test,
    # quel que soit l'environnement du shell (un pytest lancé en shell « prod » ne doit JAMAIS
    # cibler le store réel). La garde §13.6 de connexion_ecriture ne lève que si mode()=='test'.
    # Les tests qui ont besoin de prod (test_envoyer, test_garde...) surchargent via le même
    # monkeypatch, qui gagne car appliqué après cette fixture.
    monkeypatch.setenv("SECRETAIRE_MODE", "test")
