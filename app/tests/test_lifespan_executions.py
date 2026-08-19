import entrepot
import executions
from fastapi.testclient import TestClient

from serveur import app


def test_lifespan_reprend_executions_interrompues(monkeypatch):
    entrepot.init_fondations()  # même DB (chemin_ecriture() par défaut) que celle relue au boot
    executions.creer("e_test_lifespan", "secretaire")
    executions.marquer_en_cours("e_test_lifespan")
    monkeypatch.setattr(executions, "_process_vivant", lambda pid, s: False)
    try:
        with TestClient(app):
            pass  # entrée/sortie du context manager déclenche lifespan (startup)
        con = entrepot.connexion_lecture()
        try:
            row = con.execute(
                "SELECT statut FROM secw_executions WHERE id='e_test_lifespan'"
            ).fetchone()
        finally:
            con.close()
        assert row is not None and row["statut"] == "unknown"
    finally:
        con2 = entrepot.connexion_ecriture()
        try:
            con2.execute("DELETE FROM secw_executions WHERE id='e_test_lifespan'")
            con2.commit()
        finally:
            con2.close()
