"""D-9 (perf) : la contention SQLite RÉELLE, pas la mesure in-process.

`test_bench_latence.py` documente déjà (commentaire en fin de fichier) que sa mesure
tourne IN-PROCESS et ne reproduit PAS la contention réelle évoquée en D-9 (une mission
qui écrit le store pendant qu'une vue le lit, cf. store.connexion_ro : PRAGMA
busy_timeout=8000). Ce fichier vérifie CONCRÈTEMENT ce que fait `store.lire_taches`
(la vraie fonction, jamais mockée) quand une écriture concurrente tient un verrou.
"""

import sqlite3
import threading
import time

import store


def _fixture(tmp_path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.executescript("""
    CREATE TABLE sec_taches(
      id INTEGER PRIMARY KEY, cree_le TEXT, maj_le TEXT, type TEXT, titre TEXT NOT NULL,
      detail TEXT, contact TEXT, chantier TEXT, source TEXT, dolibarr_ref TEXT,
      echeance TEXT, statut TEXT DEFAULT 'a_faire', confiance INTEGER DEFAULT 3);
    INSERT INTO sec_taches(id,type,titre,statut,confiance) VALUES
      (1,'a_faire','Rappeler Consuel','a_faire',5),
      (2,'a_faire','Commander disjoncteurs','a_faire',3);
    """)
    con.commit()
    con.close()
    return str(db)


DUREE_VERROU = 0.4  # secondes tenues par l'écrivain concurrent (réduit si CI lent, cf. consigne)


def _tenir_verrou_ecriture(chemin: str, duree: float, pret: threading.Event) -> None:
    """Ouvre une transaction d'écriture bloquante sur `chemin` et la tient `duree` secondes.

    BEGIN EXCLUSIVE, et non BEGIN IMMEDIATE : vérifié sur la doc SQLite (locking v3 +
    lang_transaction) — en mode journal par défaut (pas WAL, celui du store), BEGIN
    IMMEDIATE ne pose qu'un verrou RESERVED, qui n'empêche PAS un nouveau lecteur
    d'ouvrir une connexion SHARED (« RESERVED differs from PENDING in that new SHARED
    locks can be acquired while there is a RESERVED lock »). L'escalade vers
    PENDING/EXCLUSIVE (celle qui bloque les lecteurs) n'a lieu qu'au COMMIT ou en cas de
    débordement du cache pages — jamais pendant un simple sleep avant COMMIT. Un test
    bâti sur BEGIN IMMEDIATE + sleep + COMMIT ne bloquerait donc PAS le lecteur pendant
    le sleep et l'assertion de timing serait fausse. BEGIN EXCLUSIVE, lui, pose le verrou
    EXCLUSIVE dès le BEGIN — c'est le seul qui reproduit fidèlement le scénario D-9
    (écriture concurrente qui bloque une lecture) de façon déterministe.
    """
    con = sqlite3.connect(chemin, timeout=30)
    con.execute("BEGIN EXCLUSIVE")
    con.execute(
        "INSERT INTO sec_taches(id,type,titre,statut,confiance) "
        "VALUES (99,'a_faire','Ecrite pendant verrou','a_faire',1)"
    )
    pret.set()
    time.sleep(duree)
    con.commit()
    con.close()


def test_lire_taches_attend_le_verrou_puis_reussit(tmp_path):
    chemin = _fixture(tmp_path)
    pret = threading.Event()
    ecrivain = threading.Thread(
        target=_tenir_verrou_ecriture, args=(chemin, DUREE_VERROU, pret)
    )
    ecrivain.start()
    assert pret.wait(timeout=5), "l'écrivain n'a pas posé son verrou à temps"

    debut = time.perf_counter()
    rows = store.lire_taches("a_faire", chemin)
    ecoule = time.perf_counter() - debut

    ecrivain.join()

    # PRAGMA busy_timeout=8000 (store.connexion_ro) fait ATTENDRE la lecture le temps
    # que l'écrivain libère son verrou, plutôt que d'échouer immédiatement — marge
    # 75% pour absorber le jitter de l'ordonnanceur sans rendre le test flaky.
    assert ecoule >= DUREE_VERROU * 0.75
    titres = [r["titre"] for r in rows]
    assert "Rappeler Consuel" in titres
    assert "Commander disjoncteurs" in titres


# Le verrou dépasse busy_timeout : l'échec est-il silencieux ?
#
# Quand la contention dure plus longtemps que busy_timeout (8s), sqlite3 lève
# OperationalError('database is locked'). Le `except Exception: return []` de
# store.lire_taches AVALE cette erreur sans la distinguer d'un « aucune tâche »
# légitime. Conséquence concrète : en cas de vraie contention prolongée (brigade
# active + dashboard consulté en même temps), la vue affichera silencieusement
# « aucune tâche » pendant ~8s sans qu'aucun signal ne dise que c'est un timeout et
# pas un état réel — un candidat sérieux à l'explication du « ça met quinze ans à
# réagir, c'est innavigable » d'Alex.
def test_lire_taches_verrou_qui_depasse_busy_timeout_echoue_silencieusement(
    tmp_path, monkeypatch
):
    chemin = _fixture(tmp_path)

    def _connexion_verrouillee(_chemin):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(store, "connexion_ro", _connexion_verrouillee)

    assert store.lire_taches("a_faire", chemin) == []
