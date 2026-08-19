import sqlite3

import pytest

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


def test_connexion_lecture_lit_ce_que_connexion_ecriture_a_ecrit(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)

    con = entrepot.connexion_ecriture(db)
    try:
        con.execute(
            "INSERT INTO secw_beecham_missions(id, consigne, statut, cree_le, maj_le) "
            "VALUES(?,?,?,?,?)",
            ("m_test", "consigne de test", "en_cours", "2026-08-19", "2026-08-19"),
        )
        con.commit()
    finally:
        con.close()

    con_ro = entrepot.connexion_lecture(db)
    try:
        r = con_ro.execute(
            "SELECT * FROM secw_beecham_missions WHERE id=?", ("m_test",)
        ).fetchone()
    finally:
        con_ro.close()
    assert r is not None
    assert r["consigne"] == "consigne de test"


def test_connexion_lecture_leve_si_le_fichier_n_existe_pas(tmp_path):
    # mode=ro standard : pas de création implicite, contrairement à connexion_ecriture.
    db_absente = str(tmp_path / "n_existe_pas.db")
    with pytest.raises(sqlite3.OperationalError):
        entrepot.connexion_lecture(db_absente)
