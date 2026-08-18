import subprocess
from pathlib import Path

import beecham
import entrepot


def _git(cwd, *args):
    subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


def _repo(tmp_path):
    """Un petit dépôt git jetable façon Monique (app/ + un test qui passe)."""
    repo = tmp_path / "monique"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "test_smoke.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    return repo


def test_beecham_machinerie_bout_en_bout(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setattr(beecham, "RACINE", repo)
    monkeypatch.setattr(beecham, "WORKTREES", tmp_path / "wt")
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)

    mid = beecham.demarrer_mission("ajouter un module bonjour", db)

    def faux_agent(role, consigne, worktree):
        # l'agent (ici factice) n'écrit QUE dans la branche isolée
        (Path(worktree) / "app" / "bonjour.py").write_text(
            "VALEUR = 42\n", encoding="utf-8"
        )
        return {"ok": True, "journal": [f"{role} · Write bonjour.py"], "texte": "fait"}

    r = beecham.executer_mission(mid, chemin=db, _agent=faux_agent)
    assert r["ok"] and r["tests_ok"]  # harnais a lancé les tests, verts
    assert any(
        "bonjour.py" in f for f in r["fichiers"]
    )  # nouveau fichier capté dans le diff

    m = beecham.lire_mission(mid, db)
    assert m["statut"] == "propose"  # gardé : en attente de validation
    assert "bonjour.py" in m["diff"] and "VALEUR = 42" in m["diff"]

    # isolation : le dépôt principal n'a PAS encore le fichier (tant qu'on n'a pas validé)
    assert not (repo / "app" / "bonjour.py").exists()

    v = beecham.valider(mid, db)  # l'utilisateur valide -> fusion dans main
    assert v["ok"]
    assert (repo / "app" / "bonjour.py").exists()  # maintenant fusionné
    assert beecham.lire_mission(mid, db)["statut"] == "valide"


def test_beecham_rejet_ne_touche_pas_main(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    monkeypatch.setattr(beecham, "RACINE", repo)
    monkeypatch.setattr(beecham, "WORKTREES", tmp_path / "wt")
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)

    mid = beecham.demarrer_mission("changement à jeter", db)

    def faux_agent(role, consigne, worktree):
        (Path(worktree) / "app" / "jetable.py").write_text("X = 1\n", encoding="utf-8")
        return {"ok": True, "journal": [], "texte": ""}

    beecham.executer_mission(mid, chemin=db, _agent=faux_agent)
    assert beecham.rejeter(mid, db)["ok"]
    assert beecham.lire_mission(mid, db)["statut"] == "rejete"
    assert not (repo / "app" / "jetable.py").exists()  # rien n'a fui dans main


def test_lister_missions_recentes_d_abord(tmp_path):
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)

    m1 = beecham.demarrer_mission("première mission", db)
    m2 = beecham.demarrer_mission("deuxième mission", db)

    missions = beecham.lister_missions(db)
    ids = [m["id"] for m in missions]
    assert ids.index(m2) < ids.index(
        m1
    )  # la plus récente (cree_le DESC) sort en premier
    assert len(missions) == 2

    # limit respecté
    assert len(beecham.lister_missions(db, limit=1)) == 1


def test_atelier_page_blanche(tmp_path, monkeypatch):
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")
    beecham.init_atelier()
    assert (tmp_path / "atelier" / "LISEZMOI.md").exists()
    # un agent y écrit une note ; on l'observe
    (tmp_path / "atelier" / "note_chercheur.md").write_text(
        "trouvaille", encoding="utf-8"
    )
    contenu = beecham.lister_atelier()
    noms = [f["chemin"] for f in contenu]
    assert "LISEZMOI.md" in noms and "note_chercheur.md" in noms
