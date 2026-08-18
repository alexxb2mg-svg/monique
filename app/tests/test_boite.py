import sqlite3

import boite


def _fixture(tmp_path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.executescript("""
    CREATE TABLE sys_incoming_events(
      id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL,
      target TEXT DEFAULT 'secretaire', raw_content TEXT,
      status TEXT DEFAULT 'UNCATEGORIZED', timestamp DATETIME, processed_at DATETIME);
    INSERT INTO sys_incoming_events(source,raw_content,status,timestamp,processed_at) VALUES
      ('gmail','Question sur le devis D26080004','UNCATEGORIZED','2026-08-17 08:41',NULL),
      ('whatsapp','Il manque 2 disjoncteurs','UNCATEGORIZED','2026-08-17 07:58',NULL),
      ('gmail','vieux message','TRIE','2026-08-10 09:00','2026-08-10 09:05');
    """)
    con.commit()
    con.close()
    return str(db)


def test_boite_non_traite_en_tete(tmp_path):
    rows = boite.lire_boite(_fixture(tmp_path))
    assert rows[0]["traite"] is False
    assert rows[0]["source"] == "gmail"
    assert rows[0]["apercu"].startswith("Question sur le devis")


def test_boite_marque_traite(tmp_path):
    rows = boite.lire_boite(_fixture(tmp_path))
    traites = [r for r in rows if r["traite"]]
    assert len(traites) == 1 and traites[0]["apercu"] == "vieux message"
