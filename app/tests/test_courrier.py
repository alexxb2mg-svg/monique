import sqlite3
import pytest

from courrier import (
    archiver_courrier,
    deposer_courrier,
    lister_courrier,
    relever_courrier,
)


@pytest.fixture
def db_path(tmp_path):
    """Fixture fournissant un chemin vers un fichier SQLite temporaire."""
    return str(tmp_path / "courrier_test.db")


def test_cas_nominal_flux_complet(db_path):
    """Test du flux nominal : dépôt, relevé, vérification de mise à jour et archivage."""
    # 1. Dépôt d'un message (crée aussi la base/table de manière idempotente)
    msg_id = deposer_courrier(
        chemin_db=db_path,
        destinataire="alice",
        expediteur="bob",
        sujet="Bienvenue",
        corps="Bonjour Alice !",
        session_id="sess_123",
    )
    assert isinstance(msg_id, int)
    assert msg_id > 0

    # 2. Relever le courrier
    messages = relever_courrier(db_path, destinataire="alice")
    assert len(messages) == 1
    msg = messages[0]
    assert msg["id"] == msg_id
    assert msg["expediteur"] == "bob"
    assert msg["sujet"] == "Bienvenue"
    assert msg["corps"] == "Bonjour Alice !"
    assert "cree_le" in msg

    # Vérification que le message est désormais 'lu' via lister_courrier
    non_lus = lister_courrier(db_path, destinataire="alice", statut="non_lu")
    assert len(non_lus) == 0

    lus = lister_courrier(db_path, destinataire="alice", statut="lu")
    assert len(lus) == 1
    assert lus[0]["statut"] == "lu"
    assert lus[0]["lu_le"] is not None

    # 3. Archiver le courrier
    archiver_courrier(db_path, destinataire="alice", ids=[msg_id])

    archives = lister_courrier(db_path, destinataire="alice", statut="archive")
    assert len(archives) == 1
    assert archives[0]["statut"] == "archive"
    assert archives[0]["traite_le"] is not None


def test_creation_auto_et_idempotence_base_inexistante(db_path):
    """Vérifie que lister ou archiver sur un fichier/table non existant ne plante pas."""
    # Lister sur une base inexistante doit retourner une liste vide (après création automatique)
    messages = lister_courrier(db_path, destinataire="charlie", statut="non_lu")
    assert messages == []

    # Vérifie que la table et les index ont bien été créés
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='courrier';"
        )
        assert cursor.fetchone() is not None


def test_isolation_par_destinataire(db_path):
    """Vérifie l'isolation des courriers entre différents destinataires."""
    id_alice = deposer_courrier(
        db_path, "alice", "bob", "Sujet Alice", "Corps Alice"
    )
    id_bob = deposer_courrier(
        db_path, "bob", "alice", "Sujet Bob", "Corps Bob"
    )

    # Relever pour Alice ne doit pas impacter ni retourner le courrier de Bob
    courrier_alice = relever_courrier(db_path, destinataire="alice")
    assert len(courrier_alice) == 1
    assert courrier_alice[0]["id"] == id_alice

    courrier_bob = lister_courrier(db_path, destinataire="bob", statut="non_lu")
    assert len(courrier_bob) == 1
    assert courrier_bob[0]["id"] == id_bob

    # Tentative d'archivage par le mauvais destinataire : ne doit pas archiver le message de Bob
    archiver_courrier(db_path, destinataire="alice", ids=[id_bob])

    # Le message de Bob doit être toujours 'non_lu'
    courrier_bob_apres = lister_courrier(
        db_path, destinataire="bob", statut="non_lu"
    )
    assert len(courrier_bob_apres) == 1


def test_relever_courrier_ordre_chronologique_et_limite(db_path):
    """Vérifie le respect de la limite d'affichage et l'ordre chronologique (FIFO)."""
    ids = []
    for i in range(5):
        msg_id = deposer_courrier(
            db_path, "alice", "systeme", f"Message {i}", f"Contenu {i}"
        )
        ids.append(msg_id)

    # Relever avec une limite de 3
    messages = relever_courrier(db_path, destinataire="alice", limite=3)
    assert len(messages) == 3

    # Ordre chronologique
    assert messages[0]["id"] == ids[0]
    assert messages[1]["id"] == ids[1]
    assert messages[2]["id"] == ids[2]

    # Il doit rester 2 messages 'non_lu'
    restants = lister_courrier(db_path, destinataire="alice", statut="non_lu")
    assert len(restants) == 2


def test_lister_courrier_sans_destinataire(db_path):
    """Vérifie que lister_courrier sans destinataire retourne les courriers de tous les destinataires."""
    id_alice = deposer_courrier(
        db_path, "alice", "systeme", "Sujet Alice", "Corps Alice"
    )
    id_bob = deposer_courrier(
        db_path, "bob", "systeme", "Sujet Bob", "Corps Bob"
    )

    tous_les_non_lus = lister_courrier(db_path, destinataire=None, statut="non_lu")
    assert len(tous_les_non_lus) == 2
    
    ids_recuperes = [msg["id"] for msg in tous_les_non_lus]
    assert id_alice in ids_recuperes
    assert id_bob in ids_recuperes


def test_archiver_courrier_liste_ids_vide(db_path):
    """Vérifie qu'appeler archiver_courrier avec une liste d'IDs vide ne lève pas d'exception et ne modifie rien."""
    msg_id = deposer_courrier(
        db_path, "alice", "bob", "Sujet Test", "Corps Test"
    )

    # Appel avec une liste d'IDs vide
    archiver_courrier(db_path, destinataire="alice", ids=[])

    # Le message doit rester inchangé avec le statut 'non_lu'
    messages = lister_courrier(db_path, destinataire="alice", statut="non_lu")
    assert len(messages) == 1
    assert messages[0]["id"] == msg_id
