import entrepot
import blueprint
import planif


def _db(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return db


def test_jours_ouvres():
    p = blueprint.remplir("jours_ouvres", {"heure": "07:00"})
    assert p == {
        "kind": "weekly",
        "jours": ["MON", "TUE", "WED", "THU", "FRI"],
        "heure": "07:00",
    }
    # doit être traduisible
    assert planif.cron_vers_schtasks(p)[:2] == ["/SC", "WEEKLY"]


def test_creer_job_ecrit_shadow(tmp_path):
    db = _db(tmp_path)
    jid = blueprint.creer_job(
        "chercheur", "veille nocturne", {"kind": "daily", "heure": "23:00"}, chemin=db
    )
    con = entrepot.connexion_ecriture(db)
    try:
        r = con.execute(
            "SELECT module, enabled FROM secw_jobs WHERE id=?", (jid,)
        ).fetchone()
    finally:
        con.close()
    assert r["module"] == "chercheur" and r["enabled"] == 1


def test_creer_job_idempotent_preserve_etat(tmp_path):
    db = _db(tmp_path)
    jid = blueprint.creer_job(
        "chercheur", "veille", {"kind": "daily", "heure": "23:00"}, chemin=db
    )
    con = entrepot.connexion_ecriture(db)
    try:
        con.execute(
            "UPDATE secw_jobs SET enabled=0, failure_streak=3, last_status='failed' WHERE id=?",
            (jid,),
        )
        con.commit()
    finally:
        con.close()
    # re-déclaration au redémarrage (même id) : la définition se met à jour,
    # l'état opérationnel est PRÉSERVÉ (revue F3 — pas de reset via INSERT OR REPLACE).
    jid2 = blueprint.creer_job(
        "chercheur", "veille", {"kind": "daily", "heure": "22:00"}, chemin=db
    )
    assert jid2 == jid
    con = entrepot.connexion_ecriture(db)
    try:
        r = con.execute(
            "SELECT enabled, failure_streak, last_status, planning_json "
            "FROM secw_jobs WHERE id=?",
            (jid,),
        ).fetchone()
    finally:
        con.close()
    assert (
        r["enabled"] == 0 and r["failure_streak"] == 3 and r["last_status"] == "failed"
    )
    assert (
        '"heure": "22:00"' in r["planning_json"]
    )  # la définition, elle, est bien à jour
