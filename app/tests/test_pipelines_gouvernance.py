"""D-15 Phase 1 : gouvernance de pipelines.py.

Deux protections distinctes :
- BORNES sur les paramètres d'orchestration (2e trou de sécurité du dossier : pipelines.py est un
  fichier ordinaire de la zone d'écriture développeur, modifiable par une mission).
- RÈGLE DES 3 CRITÈRES avant parallélisation (le file-lock d'origine ne vérifiait que les fichiers).
"""

from harnais import pipelines


def _m(nom, **kw):
    return {"consigne": nom, **kw}


# --- bornes sur les paramètres ------------------------------------------------------------------


def test_valeurs_normales_passent(monkeypatch):
    monkeypatch.setattr(pipelines, "CONCURRENCE", 4)
    monkeypatch.setattr(pipelines, "MAX_VAGUES", 25)
    assert pipelines.concurrence() == 4
    assert pipelines.max_vagues() == 25


def test_valeur_aberrante_retombe_sur_le_defaut_sur(monkeypatch):
    """Le scenario reel : un diff mal relu met CONCURRENCE=500, la machine se ferait noyer."""
    monkeypatch.setattr(pipelines, "CONCURRENCE", 500)
    assert pipelines.concurrence() == 4
    monkeypatch.setattr(pipelines, "MAX_VAGUES", 99999)
    assert pipelines.max_vagues() == 25


def test_valeur_nulle_ou_negative_bornee(monkeypatch):
    monkeypatch.setattr(pipelines, "CONCURRENCE", 0)
    assert pipelines.concurrence() == 4
    monkeypatch.setattr(pipelines, "CONCURRENCE", -3)
    assert pipelines.concurrence() == 4


def test_type_invalide_borne(monkeypatch):
    for mauvaise in ["4", 4.5, None, True]:
        monkeypatch.setattr(pipelines, "CONCURRENCE", mauvaise)
        assert pipelines.concurrence() == 4, f"aurait du borner : {mauvaise!r}"


def test_limite_haute_acceptee(monkeypatch):
    monkeypatch.setattr(pipelines, "CONCURRENCE", 8)  # borne haute exacte
    assert pipelines.concurrence() == 8


# --- règle des 3 critères -----------------------------------------------------------------------


def test_missions_disjointes_partent_ensemble():
    ret, rep = pipelines.filtrer_vague(
        [_m("a", fichiers=["x.py"]), _m("b", fichiers=["y.py"])], 4
    )
    assert len(ret) == 2 and rep == []


def test_collision_de_fichiers_reportee():
    ret, rep = pipelines.filtrer_vague(
        [_m("a", fichiers=["x.py"]), _m("b", fichiers=["x.py"])], 4
    )
    assert len(ret) == 1 and len(rep) == 1


def test_le_cas_cle_fichiers_disjoints_mais_dependance():
    """Contre-exemple qui motive toute la regle : le schema et la page qui le consomme ont des
    fichiers DIFFERENTS, donc l'ancien file-lock les parallelisait — et la page cassait."""
    ret, rep = pipelines.filtrer_vague(
        [
            _m("cree le schema", fichiers=["app/db.py"]),
            _m("ecrit la page", fichiers=["app/page.py"], depend_de=["cree le schema"]),
        ],
        4,
    )
    assert len(ret) == 1
    assert ret[0]["consigne"] == "cree le schema"
    assert len(rep) == 1


def test_etat_partage_force_le_sequentiel():
    ret, rep = pipelines.filtrer_vague(
        [_m("migration", fichiers=["m.py"], etat_partage=True), _m("b", fichiers=["y.py"])], 4
    )
    assert len(ret) == 1 and len(rep) == 1


def test_mission_sequentielle_en_tete_passe_seule():
    ret, _ = pipelines.filtrer_vague(
        [_m("seule", fichiers=["a.py"], depend_de=["x"]), _m("b", fichiers=["b.py"])], 4
    )
    assert len(ret) == 1


def test_limite_de_concurrence_respectee():
    missions = [_m(str(i), fichiers=[f"{i}.py"]) for i in range(6)]
    ret, rep = pipelines.filtrer_vague(missions, 2)
    assert len(ret) == 2 and len(rep) == 4


def test_perimetre_non_declare_ne_partage_pas_la_vague():
    """Sans cle fichiers (ou avec '*'), une mission touche potentiellement tout : elle ne peut pas
    cohabiter avec une autre."""
    for premiere in (_m("a"), _m("a", fichiers=["*"])):
        ret, rep = pipelines.filtrer_vague([premiere, _m("b", fichiers=["y.py"])], 4)
        assert len(ret) == 1 and len(rep) == 1


def test_ordre_preserve_pour_les_reportees():
    """Anti-famine : une mission reportee garde sa place et passera a la vague suivante."""
    missions = [_m("a", fichiers=["x"]), _m("b", fichiers=["x"]), _m("c", fichiers=["x"])]
    _, rep = pipelines.filtrer_vague(missions, 4)
    assert [m["consigne"] for m in rep] == ["b", "c"]


def test_liste_vide():
    assert pipelines.filtrer_vague([], 4) == ([], [])


def test_le_chef_est_informe_des_champs_de_dependance():
    """Garde-fou contre la regle morte : si le chef ignore que depend_de/etat_partage existent, il
    ne les declarera jamais et la regle ne servira a rien."""
    import inspect

    from harnais import boucle

    source = inspect.getsource(boucle.planifier)
    assert "depend_de" in source
    assert "etat_partage" in source
