"""Reprise d'une mission bloquée (mission 9) : repartir de son travail au lieu de le jeter.

Vrai petit dépôt git jetable, comme test_beecham.py — les agents sont factices, mais git, le
harnais et la fusion sont RÉELS : c'est le seul moyen de prouver ce qu'on affirme ici (ce que
contient le diff soumis au contrôleur, ce que la fusion ramène, ce qui reste sur le disque)."""

import subprocess
from pathlib import Path

import beecham
import entrepot


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def _repo(tmp_path):
    repo = tmp_path / "monique"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "test_smoke.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    (repo / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    return repo


def _monde(tmp_path, monkeypatch):
    """Dépôt + worktrees + atelier + base, tous isolés dans tmp_path."""
    repo = _repo(tmp_path)
    monkeypatch.setattr(beecham, "RACINE", repo)
    monkeypatch.setattr(beecham, "WORKTREES", tmp_path / "wt")
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    return repo, db


def _dev_qui_ecrit(nom, contenu):
    def dev(role, consigne, worktree, reprendre=None, modele=None):
        (Path(worktree) / "app" / nom).write_text(contenu, encoding="utf-8")
        return {"ok": True, "journal": [], "texte": "fait", "session_id": "SID-1"}

    return dev


def _bloquer(db, raison="il manque le test de non-régression"):
    """Mène une mission jusqu'au statut `bloque` (max_tours=1 + verdict « corriger »)."""
    mid = beecham.demarrer_mission("consigne d'origine", db)
    r = beecham.executer_mission(
        mid,
        chemin=db,
        _agent=_dev_qui_ecrit("travail.py", "PASSE1 = 1\n"),
        _controleur=lambda *a: {"verdict": "corriger", "raison": raison},
        max_tours=1,
    )
    assert r["statut"] == "bloque"
    return mid


def test_la_reprise_part_du_travail_de_la_passe_bloquee(tmp_path, monkeypatch):
    """Le travail de la 1re passe est présent dans le worktree AVANT que l'agent ne commence —
    sinon la reprise refait tout depuis le tronc, ce qu'on cherche justement à éviter."""
    _repo_, db = _monde(tmp_path, monkeypatch)
    mid = _bloquer(db)

    mid2 = beecham.reprendre_mission(mid, chemin=db)
    assert mid2

    vu = {}

    def dev(role, consigne, worktree, reprendre=None, modele=None):
        vu["deja_la"] = (Path(worktree) / "app" / "travail.py").read_text(
            encoding="utf-8"
        )
        vu["consigne"] = consigne
        (Path(worktree) / "app" / "correction.py").write_text(
            "CORRIGE = 2\n", encoding="utf-8"
        )
        return {"ok": True, "journal": [], "texte": "fait", "session_id": "SID-2"}

    beecham.executer_mission(
        mid2,
        chemin=db,
        _agent=dev,
        _controleur=lambda *a: {"verdict": "accepte", "raison": "ok"},
    )
    assert vu["deja_la"] == "PASSE1 = 1\n"
    assert "il manque le test de non-régression" in vu["consigne"]  # verdict en tête
    assert "consigne d'origine" in vu["consigne"]


def _fusionner_autre_mission(repo, contenu="AUTRE_MISSION = 3\n"):
    """Fait AVANCER `main` : une autre mission a été acceptée pendant celle qu'on observe
    (`serveur.py` et `harnais/boucle.py` lancent les missions dans des threads concurrents)."""
    (repo / "app" / "autre.py").write_text(contenu, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "autre mission")


def _diff_vu_par_le_controleur(mid, db, dev):
    vu = {}

    def controleur(scope, diff, tests_resume, worktree):
        vu["diff"] = diff
        return {"verdict": "accepte", "raison": "ok"}

    beecham.executer_mission(mid, chemin=db, _agent=dev, _controleur=controleur)
    return vu["diff"]


def test_le_controleur_voit_le_cumul_pas_seulement_la_correction(tmp_path, monkeypatch):
    """LE test qui compte : sur une reprise, le diff soumis au contrôleur contient le travail de
    la 1re passe ET la correction, et RIEN d'autre.

    Il tombe sur les deux mauvaises références possibles :
    - `git diff --cached` seul (pointe de la branche, qui porte déjà les commits de la 1re passe) :
      « PASSE1 » manque, le contrôleur accepterait un delta greffé sur du code jamais relu ;
    - `git diff --cached main` (pointe du tronc, vivante) : « AUTRE_MISSION » apparaît — en
      SUPPRESSION, puisque absent de l'index du worktree — et le contrôleur relit le travail
      d'une autre mission comme s'il était le sien."""
    repo, db = _monde(tmp_path, monkeypatch)
    mid = _bloquer(db)
    _fusionner_autre_mission(repo)  # main avance entre le blocage et la reprise
    mid2 = beecham.reprendre_mission(mid, chemin=db)

    diff = _diff_vu_par_le_controleur(
        mid2, db, _dev_qui_ecrit("correction.py", "CORRIGE = 2\n")
    )
    assert "PASSE1 = 1" in diff  # travail de la 1re passe
    assert "CORRIGE = 2" in diff  # correction de la reprise
    assert "AUTRE_MISSION" not in diff  # jamais le travail des autres missions


def test_un_tronc_qui_avance_ne_pollue_pas_le_diff_d_une_mission_neuve(
    tmp_path, monkeypatch
):
    """Régression du CHEMIN COURANT (pas seulement des reprises) : une mission neuve dont le tronc
    avance pendant qu'elle travaille doit voir SON diff, pas celui de la mission fusionnée entre
    temps. C'est le cas normal dès que deux missions tournent en parallèle."""
    repo, db = _monde(tmp_path, monkeypatch)
    mid = beecham.demarrer_mission("mission neuve", db)

    def dev(role, consigne, worktree, reprendre=None, modele=None):
        _fusionner_autre_mission(repo)  # une autre mission fusionne pendant celle-ci
        (Path(worktree) / "app" / "travail.py").write_text(
            "PASSE1 = 1\n", encoding="utf-8"
        )
        return {"ok": True, "journal": [], "texte": "fait", "session_id": "SID-1"}

    diff = _diff_vu_par_le_controleur(mid, db, dev)
    assert "PASSE1 = 1" in diff
    assert "AUTRE_MISSION" not in diff


def test_tronc_absent_echoue_proprement_sans_lever(tmp_path, monkeypatch):
    """`_harnais` peut lever (aucun point de divergence). L'exception ne doit JAMAIS s'échapper :
    dans le thread de `serveur.py` elle laisserait la mission `en_cours` pour toujours, et dans
    `harnais/boucle.py` elle sauterait la consommation de la file — vague rejouée à l'identique."""
    _repo_, db = _monde(tmp_path, monkeypatch)
    monkeypatch.setattr(beecham, "BRANCHE_TRONC", "tronc_absent")
    mid = beecham.demarrer_mission("mission neuve", db)

    r = beecham.executer_mission(
        mid,
        chemin=db,
        _agent=_dev_qui_ecrit("travail.py", "PASSE1 = 1\n"),
        _controleur=lambda *a: {"verdict": "accepte", "raison": "ok"},
    )
    assert r["ok"] is False
    assert beecham.lire_mission(mid, db)["statut"] == "echec"


def test_la_fusion_d_une_reprise_ramene_les_deux_jeux_de_commits(tmp_path, monkeypatch):
    """`merge --no-ff` de la branche de reprise doit ramener AUSSI les commits de la branche de
    base : `travail.py` n'existe QUE sur la branche bloquée, il doit atterrir dans le tronc."""
    repo, db = _monde(tmp_path, monkeypatch)
    mid = _bloquer(db)
    mid2 = beecham.reprendre_mission(mid, chemin=db)

    r = beecham.executer_mission(
        mid2,
        chemin=db,
        _agent=_dev_qui_ecrit("correction.py", "CORRIGE = 2\n"),
        _controleur=lambda *a: {"verdict": "accepte", "raison": "ok"},
    )
    assert r["statut"] == "valide"
    assert (repo / "app" / "travail.py").read_text(encoding="utf-8") == "PASSE1 = 1\n"
    assert (repo / "app" / "correction.py").exists()


def test_apres_fusion_la_mission_d_origine_est_close_et_nettoyee(tmp_path, monkeypatch):
    """Branche ET worktree d'origine retirés, statut plus jamais `bloque` (sinon elle resterait
    éternellement dans la liste des blocages à traiter par Alex)."""
    repo, db = _monde(tmp_path, monkeypatch)
    mid = _bloquer(db)
    branche = beecham.lire_mission(mid, db)["branche"]
    wt_origine = beecham.WORKTREES / branche.replace("/", "_")
    assert wt_origine.exists()

    mid2 = beecham.reprendre_mission(mid, chemin=db)
    beecham.executer_mission(
        mid2,
        chemin=db,
        _agent=_dev_qui_ecrit("correction.py", "CORRIGE = 2\n"),
        _controleur=lambda *a: {"verdict": "accepte", "raison": "ok"},
    )

    assert not wt_origine.exists()
    assert branche not in _git(repo, "branch", "--list", branche).stdout
    assert beecham.lire_mission(mid, db)["statut"] == "repris"


def test_valider_a_la_main_clot_aussi_la_mission_d_origine(tmp_path, monkeypatch):
    """Alex fusionne une reprise BLOQUÉE à la main : l'origine doit être close comme dans le flux
    automatique. Sinon elle reste `bloque` avec sa branche sur le disque, réapparaît sans fin dans
    `missions_bloquees()`, et une seconde reprise repartirait d'une branche déjà fusionnée."""
    repo, db = _monde(tmp_path, monkeypatch)
    mid = _bloquer(db)
    branche_origine = beecham.lire_mission(mid, db)["branche"]
    mid2 = beecham.reprendre_mission(mid, chemin=db)
    beecham.executer_mission(  # la reprise bloque à son tour
        mid2,
        chemin=db,
        _agent=_dev_qui_ecrit("correction.py", "CORRIGE = 2\n"),
        _controleur=lambda *a: {"verdict": "corriger", "raison": "encore un défaut"},
        max_tours=1,
    )

    assert beecham.valider(mid2, db)["ok"] is True
    assert beecham.lire_mission(mid, db)["statut"] == "repris"
    assert branche_origine not in _git(repo, "branch", "--list", branche_origine).stdout


def test_reprendre_une_mission_non_bloquee_est_refuse(tmp_path, monkeypatch):
    """Même garde que `valider` : on ne reprend que ce qui est `bloque`."""
    _repo_, db = _monde(tmp_path, monkeypatch)
    mid = beecham.demarrer_mission("mission en cours", db)
    assert beecham.reprendre_mission(mid, chemin=db) is None
    assert beecham.reprendre_mission("m_inconnue", chemin=db) is None


def test_verdict_absent_ne_fait_pas_echouer_la_reprise(tmp_path, monkeypatch):
    """Fail-soft : sans fichier de verdict on reprend quand même, avec le seul complément fourni."""
    _repo_, db = _monde(tmp_path, monkeypatch)
    mid = beecham.demarrer_mission("consigne d'origine", db)
    beecham._maj(mid, db, statut="bloque")  # bloquée sans verdict sur disque

    mid2 = beecham.reprendre_mission(mid, "ajoute le test manquant", chemin=db)
    assert mid2
    consigne = beecham.lire_mission(mid2, db)["consigne"]
    assert "ajoute le test manquant" in consigne
    assert "consigne d'origine" in consigne


def test_la_reprise_prend_le_dernier_verdict_pas_les_precedents(tmp_path, monkeypatch):
    """Le fichier de verdicts est append-only : c'est le DERNIER bloc (celui qui a bloqué) qui
    sert de consigne de correction, pas un tour antérieur déjà traité."""
    _repo_, db = _monde(tmp_path, monkeypatch)
    mid = beecham.demarrer_mission("consigne d'origine", db)
    beecham._maj(mid, db, statut="bloque")
    beecham.ecrire_verdict(mid, "developpeur", "corriger", "PREMIER tour, déjà traité")
    beecham.ecrire_verdict(mid, "developpeur", "corriger", "DERNIER tour, celui qui bloque")

    mid2 = beecham.reprendre_mission(mid, chemin=db)
    consigne = beecham.lire_mission(mid2, db)["consigne"]
    assert "DERNIER tour, celui qui bloque" in consigne
    assert "PREMIER tour" not in consigne


def test_un_verdict_qui_contient_des_titres_markdown_nest_pas_tronque(
    tmp_path, monkeypatch
):
    """La raison d'un verdict est du markdown de contrôleur, avec ses propres `## `. Découper sur
    le dernier `## ` venu perdrait la TÊTE du dernier bloc — c'est-à-dire le début de la consigne
    de correction, la valeur même que la reprise existe pour récupérer. L'ancre est la date ISO."""
    _repo_, db = _monde(tmp_path, monkeypatch)
    mid = beecham.demarrer_mission("consigne d'origine", db)
    beecham._maj(mid, db, statut="bloque")
    beecham.ecrire_verdict(mid, "developpeur", "corriger", "PREMIER tour, déjà traité")
    beecham.ecrire_verdict(
        mid,
        "developpeur",
        "corriger",
        "DÉBUT du dernier verdict\n\n## Correction demandée\nla suite",
    )

    consigne = beecham.lire_mission(beecham.reprendre_mission(mid, chemin=db), db)[
        "consigne"
    ]
    assert "DÉBUT du dernier verdict" in consigne  # la tête du bloc, pas seulement sa fin
    assert "## Correction demandée" in consigne
    assert "PREMIER tour" not in consigne
