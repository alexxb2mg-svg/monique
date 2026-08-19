import beecham
import entrepot
import vue_missions


def test_contexte_missions_actives_filtre_le_statut(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    id_a = beecham.demarrer_mission("mission A", db)
    id_b = beecham.demarrer_mission("mission B", db)
    con = entrepot.connexion_ecriture(db)
    con.execute("UPDATE secw_beecham_missions SET statut=? WHERE id=?", ("valide", id_b))
    con.commit()
    con.close()

    actives = vue_missions.contexte_missions_actives(db)

    assert len(actives) == 1
    assert actives[0]["consigne"] == "mission A"


def test_contexte_missions_actives_journal_fail_soft(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    mid = beecham.demarrer_mission("mission C", db)
    con = entrepot.connexion_ecriture(db)
    con.execute("UPDATE secw_beecham_missions SET journal=? WHERE id=?", ("PAS_DU_JSON{{{", mid))
    con.commit()
    con.close()

    actives = vue_missions.contexte_missions_actives(db)

    assert len(actives) == 1
    assert actives[0]["journal_liste"] == []
