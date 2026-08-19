"""Contention SQLite RÉELLE sur `beecham.lire_mission`/`lister_missions`.

Même patron que `test_contention_sqlite.py` (celui de `store.lire_taches`) : ces deux
fonctions ouvrent une connexion ET exécutent leur requête (diagnostic chercheur, cf.
`atelier/connaissances/diagnostic_d9_latence_reelle.md` §3.3) — la route `/vue/beecham`
qu'elles alimentent est la PLUS consultée de l'appli (page d'accueil de Beecham, poll HTMX
toutes les 3s). Un `sqlite3.OperationalError` non intercepté y remontait en 500 au lieu
d'un fail-soft.
"""

import sqlite3
import threading
import time

import beecham
import entrepot

DUREE_VERROU = 0.4  # secondes tenues par l'écrivain concurrent (réduit si CI lent)


def _fixture(tmp_path):
    """Base de missions jetable, schéma réel via `entrepot.init_fondations`, une mission."""
    db = str(tmp_path / "missions.db")
    entrepot.init_fondations(db)
    mid = beecham.demarrer_mission("mission de test contention", db)
    return db, mid


def _tenir_verrou_ecriture(chemin: str, duree: float, pret: threading.Event) -> None:
    """BEGIN EXCLUSIVE (pas BEGIN IMMEDIATE) — voir la doc de la fonction homonyme dans
    `test_contention_sqlite.py` pour le pourquoi : seul BEGIN EXCLUSIVE pose le verrou
    EXCLUSIVE dès le BEGIN, de façon déterministe."""
    con = sqlite3.connect(chemin, timeout=30)
    con.execute("BEGIN EXCLUSIVE")
    con.execute("UPDATE secw_beecham_missions SET journal=journal")
    pret.set()
    time.sleep(duree)
    con.commit()
    con.close()


def test_lire_mission_et_lister_missions_survivent_a_la_contention_reelle(tmp_path):
    """Contention réelle transitoire (0.4s, largement sous busy_timeout=8s) : les deux
    fonctions doivent réussir sans lever, qu'elles attendent le verrou ou lisent une version
    déjà cohérente (selon le mode journal appliqué par `entrepot._appliquer_journal`)."""
    db, mid = _fixture(tmp_path)
    pret = threading.Event()
    ecrivain = threading.Thread(
        target=_tenir_verrou_ecriture, args=(db, DUREE_VERROU, pret)
    )
    ecrivain.start()
    assert pret.wait(timeout=5), "l'écrivain n'a pas posé son verrou à temps"

    m = beecham.lire_mission(mid, db)
    missions = beecham.lister_missions(db)

    ecrivain.join()

    assert m is not None and m["id"] == mid
    assert any(x["id"] == mid for x in missions)


# Le verrou dépasse busy_timeout : l'échec est-il silencieux ?
#
# Reproduire un verrou qui dépasse réellement busy_timeout (8s) rendrait la suite lente et
# flaky (même remarque que store.py) : on force directement l'erreur que produirait ce
# scénario, en mockant `connexion_ecriture`. AVANT le patch, `lire_mission`/`lister_missions`
# n'avaient aucun bloc try/except : l'exception remontait telle quelle jusqu'à la route
# `/vue/beecham` (500). APRÈS le patch : fail-soft, None/[] sans lever.
def test_lire_mission_verrou_qui_depasse_busy_timeout_echoue_silencieusement(
    tmp_path, monkeypatch
):
    db, mid = _fixture(tmp_path)

    def _connexion_verrouillee(_chemin):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(beecham, "connexion_ecriture", _connexion_verrouillee)

    assert beecham.lire_mission(mid, db) is None


def test_lister_missions_verrou_qui_depasse_busy_timeout_echoue_silencieusement(
    tmp_path, monkeypatch
):
    db, _mid = _fixture(tmp_path)

    def _connexion_verrouillee(_chemin=None):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(beecham, "connexion_ecriture", _connexion_verrouillee)

    assert beecham.lister_missions(db) == []
