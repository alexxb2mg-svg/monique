import sqlite3
import threading
import time

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


# --- Contention SQLite (même patron que test_contention_sqlite.py, cf. beecham.lire_mission) ---
#
# Avant le patch, lire_event/lire_boite ne protégeaient QUE l'ouverture de connexion
# (try/except Exception autour de connexion_ro) — la requête con.execute() qui suit
# était dans un second bloc try qui n'avait qu'un `finally: con.close()`, aucun except.
# Sous contention SQLite (écriture concurrente qui tient le verrou), sqlite3.OperationalError
# levée PENDANT l'exécution de la requête remontait donc non interceptée jusqu'à la route
# FastAPI (500 au lieu d'un fail-soft) — bug de fiabilité D-9.

DUREE_VERROU = 0.4  # secondes tenues par l'écrivain concurrent (réduit si CI lent)


def _tenir_verrou_ecriture(chemin: str, duree: float, pret: threading.Event) -> None:
    """Ouvre une transaction d'écriture bloquante sur `chemin` et la tient `duree` secondes.

    BEGIN EXCLUSIVE (et non BEGIN IMMEDIATE) : seul mode qui pose le verrou EXCLUSIVE dès
    le BEGIN, cf. le commentaire détaillé de test_contention_sqlite._tenir_verrou_ecriture.
    """
    con = sqlite3.connect(chemin, timeout=30)
    con.execute("BEGIN EXCLUSIVE")
    con.execute(
        "INSERT INTO sys_incoming_events(source,raw_content,status,timestamp) "
        "VALUES ('gmail','écrit pendant verrou','UNCATEGORIZED','2026-08-19 00:00')"
    )
    pret.set()
    time.sleep(duree)
    con.commit()
    con.close()


def test_lire_boite_attend_le_verrou_puis_reussit(tmp_path):
    """DUREE_VERROU (0.4s) reste sous le busy_timeout=8000ms de connexion_ro : la lecture
    attend que l'écrivain libère son verrou plutôt que d'échouer — chemin normal, pas
    encore le cas d'erreur (couvert par le test suivant).
    """
    chemin = _fixture(tmp_path)
    pret = threading.Event()
    ecrivain = threading.Thread(
        target=_tenir_verrou_ecriture, args=(chemin, DUREE_VERROU, pret)
    )
    ecrivain.start()
    assert pret.wait(timeout=5), "l'écrivain n'a pas posé son verrou à temps"

    debut = time.perf_counter()
    rows = boite.lire_boite(chemin)
    ecoule = time.perf_counter() - debut

    ecrivain.join()

    assert ecoule >= DUREE_VERROU * 0.75
    assert any(r["apercu"] == "vieux message" for r in rows)


def _connexion_qui_echoue_a_execute(_chemin):
    """Simule une connexion ouverte avec succès mais dont la requête échoue en cours
    d'exécution (OperationalError('database is locked')) — le cas RÉEL du bug D-9, que
    reproduire par une vraie contention obligerait à dépasser busy_timeout=8000ms (trop
    lent et non déterministe pour un test). Même stratégie que
    test_contention_sqlite.test_lire_taches_verrou_qui_depasse_busy_timeout_echoue_silencieusement.
    """

    class _ConnexionVerrouillee:
        def execute(self, *_args, **_kwargs):
            raise sqlite3.OperationalError("database is locked")

        def close(self):
            pass

    return _ConnexionVerrouillee()


def test_lire_event_verrou_qui_depasse_busy_timeout_echoue_silencieusement(
    tmp_path, monkeypatch
):
    chemin = _fixture(tmp_path)
    monkeypatch.setattr(boite, "connexion_ro", _connexion_qui_echoue_a_execute)

    assert boite.lire_event(1, chemin) is None


def test_lire_boite_verrou_qui_depasse_busy_timeout_echoue_silencieusement(
    tmp_path, monkeypatch
):
    chemin = _fixture(tmp_path)
    monkeypatch.setattr(boite, "connexion_ro", _connexion_qui_echoue_a_execute)

    assert boite.lire_boite(chemin) == []
