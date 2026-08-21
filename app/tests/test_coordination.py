import json
import sqlite3
import pytest
from coordination import (
    poster_fil,
    lire_fil_non_lu,
    lister_fil,
    epingler_fil,
    archiver_fil,
)


@pytest.fixture
def db_path(tmp_path):
    """Fournit un chemin vers une base de données temporaire SQLite."""
    return str(tmp_path / "test_coordination.db")


def test_cas_nominal_poster_et_lister(db_path):
    """Teste la création automatique de la table, l'insertion et la lecture globale."""
    id_1 = poster_fil(db_path, "Agent_A", "Message initial", type="note")
    id_2 = poster_fil(db_path, "Agent_B", "Alerte système", type="alerte")

    assert id_1 == 1
    assert id_2 == 2

    entrees = lister_fil(db_path)
    assert len(entrees) == 2
    assert entrees[0]["id"] == id_1
    assert entrees[0]["auteur"] == "Agent_A"
    assert entrees[0]["corps"] == "Message initial"
    assert entrees[0]["type"] == "note"
    assert entrees[0]["epingle"] == 0
    assert entrees[0]["statut"] == "actif"
    assert json.loads(entrees[0]["lu_par"]) == []

    # Vérification que la base est bien initialisée en mode WAL
    conn = sqlite3.connect(db_path)
    mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
    conn.close()
    assert mode.lower() == "wal"


def test_lire_fil_non_lu_et_idempotence(db_path):
    """Vérifie que l'agent ne reçoit les messages qu'une seule fois et met à jour lu_par."""
    poster_fil(db_path, "Agent_A", "Note 1")
    poster_fil(db_path, "Agent_A", "Note 2")

    # Première lecture par Agent_B
    non_lus_b1 = lire_fil_non_lu(db_path, "Agent_B", limite=50)
    assert len(non_lus_b1) == 2
    assert "Agent_B" in json.loads(non_lus_b1[0]["lu_par"])

    # Seconde lecture par Agent_B : aucun nouveau message
    non_lus_b2 = lire_fil_non_lu(db_path, "Agent_B")
    assert len(non_lus_b2) == 0

    # Lecture par Agent_C : reçoit les messages
    non_lus_c = lire_fil_non_lu(db_path, "Agent_C")
    assert len(non_lus_c) == 2


def test_epingler_et_archiver_fil(db_path):
    """Vérifie le changement d'état (épinglé) et le filtrage lors de l'archivage."""
    id_1 = poster_fil(db_path, "Agent_A", "Information importante")
    id_2 = poster_fil(db_path, "Agent_B", "Discussion générale")

    epingler_fil(db_path, id_1)
    archiver_fil(db_path, id_2)

    # Filtrage par éléments épinglés
    epingles = lister_fil(db_path, epingle_seulement=True)
    assert len(epingles) == 1
    assert epingles[0]["id"] == id_1
    assert epingles[0]["epingle"] == 1

    # Les éléments archivés ne doivent plus apparaître dans la liste par défaut
    actifs = lister_fil(db_path, statut="actif")
    assert len(actifs) == 1
    assert actifs[0]["id"] == id_1

    # Un message archivé ne doit pas apparaître dans les non-lus
    non_lus = lire_fil_non_lu(db_path, "Agent_C")
    assert len(non_lus) == 1
    assert non_lus[0]["id"] == id_1


def test_limite_et_ordre_chronologique(db_path):
    """Vérifie le respect de la paramètre limite et de l'ordre d'insertion."""
    for i in range(5):
        poster_fil(db_path, f"Agent_{i}", f"Message {i}")

    non_lus_limite = lire_fil_non_lu(db_path, "Agent_X", limite=3)
    assert len(non_lus_limite) == 3
    assert non_lus_limite[0]["corps"] == "Message 0"
    assert non_lus_limite[2]["corps"] == "Message 2"

    # Les 2 restants au second passage
    non_lus_reste = lire_fil_non_lu(db_path, "Agent_X", limite=3)
    assert len(non_lus_reste) == 2
    assert non_lus_reste[0]["corps"] == "Message 3"


def test_lire_fil_non_lu_base_vide(db_path):
    """Vérifie la lecture sur une base entièrement vide sans erreur."""
    res = lire_fil_non_lu(db_path, "Agent_X")
    assert res == []


def test_lister_fil_statut_archive(db_path):
    """Vérifie que lister_fil avec statut='archive' renvoie les entrées archivées."""
    id_1 = poster_fil(db_path, "Agent_A", "Note 1")
    id_2 = poster_fil(db_path, "Agent_B", "Note 2")

    archiver_fil(db_path, id_1)

    archives = lister_fil(db_path, statut="archive")
    assert len(archives) == 1
    assert archives[0]["id"] == id_1
    assert archives[0]["statut"] == "archive"


def test_cumul_lu_par_plusieurs_agents(db_path):
    """Vérifie que plusieurs agents lisant la même entrée apparaissent tous dans lu_par."""
    id_1 = poster_fil(db_path, "Agent_A", "Message partagé")

    lire_fil_non_lu(db_path, "Agent_X")
    lire_fil_non_lu(db_path, "Agent_Y")

    entrees = lister_fil(db_path)
    lu_par_liste = json.loads(entrees[0]["lu_par"])

    assert "Agent_X" in lu_par_liste
    assert "Agent_Y" in lu_par_liste
    assert len(lu_par_liste) == 2
