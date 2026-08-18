import entrepot
import executions


def _db(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return db


def test_cycle_terminal_immuable(tmp_path):
    db = _db(tmp_path)
    executions.creer("e1", "secretaire", db)
    executions.marquer_en_cours("e1", db)
    executions.finir("e1", "completed", "ok", "delivered", db)
    executions.finir(
        "e1", "failed", "x", None, db
    )  # doit être ignoré (terminal immuable)
    con = entrepot.connexion_ecriture(db)
    try:
        r = con.execute(
            "SELECT statut, delivery_outcome FROM secw_executions WHERE id='e1'"
        ).fetchone()
    finally:
        con.close()
    assert r["statut"] == "completed" and r["delivery_outcome"] == "delivered"


def test_reprise_marque_unknown_si_mort(tmp_path, monkeypatch):
    db = _db(tmp_path)
    executions.creer("e2", "secretaire", db)
    executions.marquer_en_cours("e2", db)
    monkeypatch.setattr(executions, "_process_vivant", lambda pid, s: False)
    n = executions.reprendre_interrompues(db)
    con = entrepot.connexion_ecriture(db)
    try:
        assert (
            con.execute("SELECT statut FROM secw_executions WHERE id='e2'").fetchone()[
                0
            ]
            == "unknown"
        )
    finally:
        con.close()
    assert n == 1
