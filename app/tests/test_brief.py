import sqlite3

import brief
import monitoring


def _fixture(tmp_path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.executescript("""
    CREATE TABLE sys_constants(id INTEGER PRIMARY KEY, key TEXT UNIQUE, value TEXT,
      type TEXT DEFAULT 'froide', description TEXT, updated_at TEXT, updated_by TEXT);
    CREATE TABLE sys_incoming_events(id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT,
      target TEXT, raw_content TEXT, status TEXT, timestamp DATETIME, processed_at DATETIME);
    CREATE TABLE sec_taches(id INTEGER PRIMARY KEY, type TEXT, titre TEXT, statut TEXT,
      echeance TEXT, confiance INTEGER DEFAULT 3, cree_le TEXT, maj_le TEXT, detail TEXT,
      contact TEXT, chantier TEXT, source TEXT, dolibarr_ref TEXT);
    INSERT INTO sys_constants(key,value) VALUES ('collector_last_run','2026-08-17 19:03');
    INSERT INTO sys_incoming_events(raw_content,processed_at) VALUES ('a',NULL),('b',NULL),('c','2026-08-17');
    INSERT INTO sec_taches(type,titre,statut,echeance) VALUES ('a_faire','en retard','a_faire','2026-08-14');
    """)
    con.commit()
    con.close()
    return str(db)


def test_monitoring(tmp_path):
    e = monitoring.etat_moteur(_fixture(tmp_path))
    assert e["dernier_passage"] == "2026-08-17 19:03"
    assert e["a_traiter"] == 2


def test_brief_phrase(tmp_path):
    b = brief.construire(_fixture(tmp_path))
    assert b["mails_a_traiter"] == 2
    assert isinstance(b["phrase"], str) and "2" in b["phrase"]
