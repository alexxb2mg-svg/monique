import logging
import sqlite3

import store


def _fixture(tmp_path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.executescript("""
    CREATE TABLE sec_taches(
      id INTEGER PRIMARY KEY, cree_le TEXT, maj_le TEXT, type TEXT, titre TEXT NOT NULL,
      detail TEXT, contact TEXT, chantier TEXT, source TEXT, dolibarr_ref TEXT,
      echeance TEXT, statut TEXT DEFAULT 'a_faire', confiance INTEGER DEFAULT 3);
    INSERT INTO sec_taches(id,type,titre,statut,confiance) VALUES
      (1,'a_faire','Rappeler Consuel','a_faire',5),
      (2,'a_faire','Commander disjoncteurs','a_faire',3),
      (3,'a_faire','Tache reglee','regle',4),
      (4,'relance','Relancer EFFICIENCE','a_faire',3);
    """)
    con.commit()
    con.close()
    return str(db)


def test_lire_taches_exclut_reglees_et_trie(tmp_path):
    rows = store.lire_taches("a_faire", _fixture(tmp_path))
    assert [r["titre"] for r in rows] == ["Rappeler Consuel", "Commander disjoncteurs"]


def test_lire_taches_relance(tmp_path):
    rows = store.lire_taches("relance", _fixture(tmp_path))
    assert len(rows) == 1 and rows[0]["titre"] == "Relancer EFFICIENCE"


def test_lire_taches_verrou_est_signale(monkeypatch, caplog):
    def _lever_verrou(_chemin):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(store, "connexion_ro", _lever_verrou)
    with caplog.at_level(logging.WARNING):
        rows = store.lire_taches("a_faire")
    assert rows == []
    assert "verrouillée" in caplog.text


def test_lire_taches_fichier_absent_reste_silencieux(monkeypatch, caplog):
    def _lever_absence(_chemin):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr(store, "connexion_ro", _lever_absence)
    with caplog.at_level(logging.WARNING):
        rows = store.lire_taches("a_faire")
    assert rows == []
    assert caplog.records == []
