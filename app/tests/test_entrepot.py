import entrepot


def test_init_cree_les_tables(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    con = entrepot.connexion_ecriture(db)
    try:
        noms = {
            r[0]
            for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        con.close()
    attendues = {
        "secw_model_usage",
        "secw_turn_lease",
        "secw_delivery_obligations",
        "secw_pending_writes",
        "secw_executions",
    }
    assert attendues <= noms


def test_journal_selon_version(
    tmp_path,
):  # revue §13.1 : WAL si SQLite corrigé, sinon TRUNCATE
    import sqlite3

    db = str(tmp_path / "shadow.db")
    con = entrepot.connexion_ecriture(db)
    try:
        mode = con.execute("PRAGMA journal_mode").fetchone()[0].lower()
    finally:
        con.close()
    attendu = "wal" if sqlite3.sqlite_version_info >= (3, 51, 3) else "truncate"
    assert mode == attendu
