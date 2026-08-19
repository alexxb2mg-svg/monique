"""Monitoring : fail-soft du moteur de collecte + panneau « Chantier de Beecham »."""

import sqlite3

import monitoring


def test_etat_moteur_failsoft_db_absente(tmp_path):
    """Régression : un store inexistant ne doit PLUS lever (la page rendait un HTTP 500) —
    on renvoie un état « inactif » propre."""
    absent = str(tmp_path / "nexiste_pas.db")
    e = monitoring.etat_moteur(absent)
    assert e == {
        "collecte_active": False,
        "dernier_passage": None,
        "entrees_jour": 0,
        "a_traiter": 0,
        "tables_manquantes": [],
    }


def test_etat_moteur_tables_manquantes_vide_quand_tout_trouve(tmp_path):
    """Observabilité (decouverte.diagnostic branché en plus, pas à la place) : quand toutes les
    tables attendues par BESOINS existent, tables_manquantes est vide."""
    db = tmp_path / "reel.db"
    con = sqlite3.connect(db)
    con.executescript("""
      CREATE TABLE sys_constants(key TEXT PRIMARY KEY, value TEXT);
      CREATE TABLE sys_incoming_events(id INTEGER PRIMARY KEY, processed_at TEXT, timestamp TEXT);
      CREATE TABLE sec_taches(id INTEGER PRIMARY KEY, titre TEXT, statut TEXT);
    """)
    con.commit()
    con.close()
    e = monitoring.etat_moteur(str(db))
    assert e["tables_manquantes"] == []


def test_sujet_nettoie_le_prefixe_fichiers_touches():
    """Le libellé affiché retire le préfixe technique « Fichiers touches : … — » et garde l'intention."""
    c = "Fichiers touches : app/x.py, app/tests/test_x.py — brancher la vue Coût déjà testée"
    assert monitoring._sujet(c) == "brancher la vue Coût déjà testée"


def test_sujet_planif_beecham_est_lisible():
    assert monitoring._sujet("Tu es Beecham, tu diriges la brigade…") == (
        "Beecham — état des lieux et décision"
    )


def test_chantier_brigade_structure(monkeypatch):
    """chantier_brigade agrège les missions par statut et masque la planif Beecham des « en cours »."""
    faux = [
        {"consigne": "Tu es Beecham, planifie", "statut": "en_cours", "maj_le": "2026-08-19 16:00:00"},
        {"consigne": "Fichiers touches : app/a.py — pose la nav par département", "statut": "en_cours", "maj_le": "2026-08-19 16:01:00"},
        {"consigne": "Fichiers touches : app/b.py — réglages par agent", "statut": "valide", "maj_le": "2026-08-19 16:02:00"},
        {"consigne": "Fichiers touches : app/c.py — truc", "statut": "rejete", "maj_le": "2026-08-19 16:03:00"},
    ]
    import beecham

    monkeypatch.setattr(beecham, "lister_missions", lambda limit=60: faux)
    ch = monitoring.chantier_brigade()
    assert ch["disponible"] is True
    assert ch["compte"] == {"en_cours": 2, "fusionnes": 1, "rates": 1}
    # la planif Beecham est masquée du panneau « en cours » : 1 seul sujet reste
    assert [s["sujet"] for s in ch["en_cours"]] == ["pose la nav par département"]
    assert ch["fusionnes"][0]["sujet"] == "réglages par agent"
    assert ch["fusionnes"][0]["heure"] == "16:02"
