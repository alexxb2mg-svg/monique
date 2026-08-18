import sqlite3

import entrepot
import overlays
import store


def _db(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return db


def test_cocher_tache_overlay(tmp_path):
    db = _db(tmp_path)
    assert overlays.statut_tache(1, db) is None
    overlays.cocher_tache(1, "alex", db)
    assert overlays.statut_tache(1, db) == "regle"


def test_brouillon_roundtrip(tmp_path):
    db = _db(tmp_path)
    bid = overlays.enregistrer_brouillon(
        42, "gmail", "contexte", "Bonjour…", ["valider l'envoi"], ["le Consuel"], db
    )
    b = overlays.lire_brouillon(42, db)
    assert b["brouillon"] == "Bonjour…"
    assert b["attendu"] == ["valider l'envoi"] and b["hors"] == ["le Consuel"]
    assert bid == b["id"]


def test_fusion_store_exclut_tache_cochee_overlay(tmp_path):
    # fondations (secw_taches_overlay) + table Phase 1 sec_taches dans le MÊME fichier :
    # preuve que la fusion filtre réellement quand l'overlay est présent et lisible.
    db = _db(tmp_path)
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

    assert [
        r["titre"] for r in store.lire_taches("a_faire", db, chemin_overlay=db)
    ] == ["Rappeler Consuel", "Commander disjoncteurs"]

    overlays.cocher_tache(1, "alex", db)
    rows = store.lire_taches("a_faire", db, chemin_overlay=db)
    assert [r["titre"] for r in rows] == ["Commander disjoncteurs"]
