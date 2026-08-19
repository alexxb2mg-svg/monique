import os
import subprocess
import sys
import time

import entrepot
import superviseur


def test_enregistrer_voit_le_process_vivant(tmp_path):
    db = str(tmp_path / "s.db")
    entrepot.init_fondations(db)
    rid = superviseur.enregistrer(
        os.getpid(), nom="moi-test", proprietaire="test", but="prouver etat", chemin=db
    )
    board = [e for e in superviseur.etat(db) if e["id"] == rid]
    assert board and board[0]["vivant"] is True
    assert board[0]["nom"] == "moi-test" and board[0]["but"] == "prouver etat"


def test_finir_retire_du_tableau(tmp_path):
    db = str(tmp_path / "s.db")
    entrepot.init_fondations(db)
    rid = superviseur.enregistrer(
        os.getpid(), nom="x", proprietaire="test", but="b", chemin=db
    )
    superviseur.finir(rid, chemin=db)
    assert not [e for e in superviseur.etat(db) if e["id"] == rid]


def test_balayer_nettoie_un_pid_mort(tmp_path):
    db = str(tmp_path / "s.db")
    entrepot.init_fondations(db)
    p = subprocess.Popen([sys.executable, "-c", "pass"])  # meurt aussitôt
    p.wait()
    time.sleep(0.3)
    rid = superviseur.enregistrer(
        p.pid, nom="mort", proprietaire="test", but="b", chemin=db
    )
    res = superviseur.balayer(chemin=db)
    assert res["records_morts_nettoyes"] >= 1
    assert not [e for e in superviseur.etat(db) if e["id"] == rid]  # nettoyé du tableau


def test_tuer_id_inconnu_ne_plante_pas(tmp_path):
    db = str(tmp_path / "s.db")
    entrepot.init_fondations(db)
    r = superviseur.tuer("p_inexistant", chemin=db)
    assert r["ok"] is False and "inconnu" in r["erreur"]
