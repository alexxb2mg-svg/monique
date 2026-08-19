import sqlite3
import decouverte


def _fixture(tmp_path):
    db = tmp_path / "reel.db"
    con = sqlite3.connect(db)
    con.executescript("""
      CREATE TABLE sys_incoming_events(id INTEGER PRIMARY KEY, source TEXT, raw_content TEXT);
      CREATE TABLE sec_taches(id INTEGER PRIMARY KEY, titre TEXT, statut TEXT);
    """)
    con.commit()
    con.close()
    return str(db)


def test_carte_liste_tables_et_colonnes(tmp_path):
    carte = decouverte.carte_schema(_fixture(tmp_path))
    assert "sys_incoming_events" in carte
    assert "source" in carte["sys_incoming_events"]


def test_resoudre_besoin_present(tmp_path):
    carte = decouverte.carte_schema(_fixture(tmp_path))
    assert decouverte.resoudre("evenements_entrants", carte) == "sys_incoming_events"


def test_diagnostic_signale_manque(tmp_path):
    diag = decouverte.diagnostic(_fixture(tmp_path))
    assert "synthese" not in diag["manques"]  # besoin retiré de BESOINS (jamais consommé)
    assert "constantes" in diag["manques"]  # sys_constants absente de la fixture
    assert "taches" not in diag["manques"]
