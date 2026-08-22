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


def _bloquer_a_la_main(repo, db, consigne):
    """Mission `bloque` posée sans lancer d'agent, mais avec une branche qui porte UN commit
    au-delà du tronc — comme le fait le blocage réel depuis la mission 9. Sans ce commit,
    `reprendre_mission` refuse (mission 15) et il n'y a plus de consigne à observer."""
    mid = beecham.demarrer_mission(consigne, db)
    beecham._maj(mid, db, statut="bloque")
    c = _git(repo, "commit-tree", "HEAD^{tree}", "-p", "HEAD", "-m", "passe 1").stdout
    _git(repo, "update-ref", f"refs/heads/beecham/{mid}", c.strip())
    return mid


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
    repo, db = _monde(tmp_path, monkeypatch)
    mid = _bloquer_a_la_main(repo, db, "consigne d'origine")  # sans verdict sur disque

    mid2 = beecham.reprendre_mission(mid, "ajoute le test manquant", chemin=db)
    assert mid2
    consigne = beecham.lire_mission(mid2, db)["consigne"]
    assert "ajoute le test manquant" in consigne
    assert "consigne d'origine" in consigne


def test_la_reprise_prend_le_dernier_verdict_pas_les_precedents(tmp_path, monkeypatch):
    """Le fichier de verdicts est append-only : c'est le DERNIER bloc (celui qui a bloqué) qui
    sert de consigne de correction, pas un tour antérieur déjà traité."""
    repo, db = _monde(tmp_path, monkeypatch)
    mid = _bloquer_a_la_main(repo, db, "consigne d'origine")
    beecham.ecrire_verdict(mid, "developpeur", "corriger", "PREMIER tour, déjà traité")
    beecham.ecrire_verdict(mid, "developpeur", "corriger", "DERNIER tour, celui qui bloque")

    mid2 = beecham.reprendre_mission(mid, chemin=db)
    consigne = beecham.lire_mission(mid2, db)["consigne"]
    assert "DERNIER tour, celui qui bloque" in consigne
    assert "PREMIER tour" not in consigne


def test_la_cloture_remonte_toute_la_chaine_de_reprises(tmp_path, monkeypatch):
    """mid1 -> mid2 -> mid3 : à la fusion de mid3, les DEUX ancêtres sont `repris` et leurs
    branches ont disparu. En ne remontant que d'un niveau, mid1 restait `bloque` pour toujours,
    avec sa branche sur le disque — et la chaîne de reprises est le régime normal du harnais
    (mission 8 : trois passes)."""
    repo, db = _monde(tmp_path, monkeypatch)
    mid1 = _bloquer(db)
    b1 = beecham.lire_mission(mid1, db)["branche"]

    mid2 = beecham.reprendre_mission(mid1, chemin=db)
    beecham.executer_mission(  # la 1re reprise bloque à son tour
        mid2,
        chemin=db,
        _agent=_dev_qui_ecrit("correction.py", "CORRIGE = 2\n"),
        _controleur=lambda *a: {"verdict": "corriger", "raison": "encore un défaut"},
        max_tours=1,
    )
    b2 = beecham.lire_mission(mid2, db)["branche"]

    mid3 = beecham.reprendre_mission(mid2, chemin=db)
    r = beecham.executer_mission(
        mid3,
        chemin=db,
        _agent=_dev_qui_ecrit("correction2.py", "CORRIGE = 3\n"),
        _controleur=lambda *a: {"verdict": "accepte", "raison": "ok"},
    )

    assert r["statut"] == "valide"
    assert beecham.lire_mission(mid2, db)["statut"] == "repris"
    assert beecham.lire_mission(mid1, db)["statut"] == "repris"  # le grand-parent AUSSI
    for b in (b1, b2):
        assert b not in _git(repo, "branch", "--list", b).stdout
        assert not (beecham.WORKTREES / b.replace("/", "_")).exists()


def test_une_chaine_circulaire_ne_fait_pas_boucler_la_cloture(tmp_path, monkeypatch):
    """Filet de la remontée : deux missions qui se désignent l'une l'autre (base incohérent, base
    qui pointe sur lui-même) doivent terminer, pas tourner à l'infini."""
    _repo_, db = _monde(tmp_path, monkeypatch)
    a = beecham.demarrer_mission("A", db)
    b = beecham.demarrer_mission("B", db)
    beecham._maj(a, db, statut="bloque", base=f"beecham/{b}")
    beecham._maj(b, db, statut="bloque", base=f"beecham/{a}")

    beecham._clore_origine(f"beecham/{a}", db)  # boucle infinie sans le garde-fou

    assert beecham.lire_mission(a, db)["statut"] == "repris"
    assert beecham.lire_mission(b, db)["statut"] == "repris"


def _bloquer_avec_longue_consigne(repo, db, avec_verdict):
    """Mission bloquée dont la consigne porte un marqueur au DÉBUT et un autre à la FIN, séparés
    par plus de 5 000 caractères de cadrage."""
    consigne = (
        "## Objectif\nMARQUEUR_TETE\n\n"
        + "## Détails\nblabla de cadrage.\n" * 300
        + "\n## Annexe\nMARQUEUR_FIN\n"
    )
    assert len(consigne) > 5000
    mid = _bloquer_a_la_main(repo, db, consigne)
    if avec_verdict:
        beecham.ecrire_verdict(mid, "developpeur", "corriger", "il manque le test")
    return mid, consigne


def test_avec_verdict_la_reprise_ne_recopie_pas_tout_le_cadrage(tmp_path, monkeypatch):
    """Anti-patron d'Hermes (#11996) : recopier le cadrage d'origine dans la relance le fossilise.
    Le travail est déjà dans la copie de l'agent et le verdict porte la correction — on ne garde
    qu'un rappel en tête, assez pour que l'agent sache ce qu'on lui demandait."""
    repo, db = _monde(tmp_path, monkeypatch)
    mid, origine = _bloquer_avec_longue_consigne(repo, db, avec_verdict=True)

    consigne = beecham.lire_mission(beecham.reprendre_mission(mid, chemin=db), db)[
        "consigne"
    ]
    assert "MARQUEUR_FIN" not in consigne  # le cadrage n'est PAS recopié en entier
    assert "MARQUEUR_TETE" in consigne  # ...mais l'agent reste orienté
    assert "il manque le test" in consigne
    assert len(consigne) < len(origine)  # bien plus courte que l'ancienne


def test_sans_verdict_la_consigne_d_origine_est_transmise_entiere(tmp_path, monkeypatch):
    """Sans verdict, la consigne d'origine est le SEUL contexte disponible : la couper serait le
    contraire du but."""
    repo, db = _monde(tmp_path, monkeypatch)
    mid, _origine = _bloquer_avec_longue_consigne(repo, db, avec_verdict=False)

    consigne = beecham.lire_mission(beecham.reprendre_mission(mid, chemin=db), db)[
        "consigne"
    ]
    assert "MARQUEUR_TETE" in consigne
    assert "MARQUEUR_FIN" in consigne


def _journal(tmp_path):
    return (tmp_path / "atelier" / "journal.md").read_text(encoding="utf-8")


def test_une_base_sans_commit_est_refusee_sans_rien_creer(tmp_path, monkeypatch):
    """Reproduction EXACTE de l'incident du 22/08 22h32 : la branche de la mission bloquée existe
    mais ne porte aucun commit au-delà du tronc (avant la mission 9, le blocage ne commitait pas).
    La consigne jurait « ton travail est DÉJÀ dans ta copie » à un agent devant une copie vide —
    il a reconstruit de mémoire. Ici : refus, aucun worktree, aucune mission en base, raison
    nommant la branche. Retire le contrôle dans `reprendre_mission` : ce test tombe."""
    repo, db = _monde(tmp_path, monkeypatch)
    mid = beecham.demarrer_mission("consigne d'origine", db)
    beecham._maj(mid, db, statut="bloque")
    branche = beecham.lire_mission(mid, db)["branche"]
    _git(repo, "branch", branche, "main")  # branche posée sur le tronc, sans travail
    avant = len(beecham.lister_missions(db))

    assert beecham.reprendre_mission(mid, chemin=db) is None
    assert len(beecham.lister_missions(db)) == avant
    assert not (beecham.WORKTREES / branche.replace("/", "_")).exists()
    assert not beecham.WORKTREES.exists()
    j = _journal(tmp_path)
    assert branche in j and "0 trouvé" in j and "reprise refusée" in j


def test_la_consigne_chiffre_le_travail_quand_il_est_la(tmp_path, monkeypatch):
    """Le harnais n'affirme jamais ce qu'il n'a pas vérifié : avec des commits sur la branche,
    la consigne le dit ET le chiffre (commits, fichiers) — vérifiable par l'agent."""
    _repo_, db = _monde(tmp_path, monkeypatch)
    mid = _bloquer(db)  # 1 commit (travail.py) figé au blocage
    consigne = beecham.lire_mission(beecham.reprendre_mission(mid, chemin=db), db)[
        "consigne"
    ]
    assert "DÉJÀ dans ta copie" in consigne
    assert "1 commit(s)" in consigne
    assert "app/travail.py" in consigne


def test_une_branche_absente_du_depot_est_refusee(tmp_path, monkeypatch):
    """Même règle que la base vide : pas de travail, pas de reprise. Laisser passer créerait
    une mission fantôme vouée à `echec` dès `_creer_worktree`, avec une consigne que personne
    ne lirait."""
    _repo_, db = _monde(tmp_path, monkeypatch)
    mid = beecham.demarrer_mission("sans branche", db)
    beecham._maj(mid, db, statut="bloque")
    avant = len(beecham.lister_missions(db))

    assert beecham.reprendre_mission(mid, chemin=db) is None
    assert len(beecham.lister_missions(db)) == avant
    j = _journal(tmp_path)
    assert f"beecham/{mid}" in j and "absente du dépôt" in j and "reprise refusée" in j


def test_une_base_en_retard_sur_le_tronc_est_signalee_pas_refusee(tmp_path, monkeypatch):
    """Deux fusions ont fait avancer le tronc depuis le blocage : l'écart figure au journal et
    dans la consigne (l'agent sait qu'il travaille sur une base ancienne), la reprise passe."""
    repo, db = _monde(tmp_path, monkeypatch)
    mid = _bloquer(db)
    _fusionner_autre_mission(repo, "A = 1\n")
    _fusionner_autre_mission(repo, "A = 2\n")

    mid2 = beecham.reprendre_mission(mid, chemin=db)
    assert mid2
    consigne = beecham.lire_mission(mid2, db)["consigne"]
    assert "retard de 2 commit(s)" in consigne
    assert "retard de 2 commit(s)" in _journal(tmp_path)

    # base à jour : pas d'avertissement parasite
    mid_b = _bloquer(db)
    consigne = beecham.lire_mission(beecham.reprendre_mission(mid_b, chemin=db), db)[
        "consigne"
    ]
    assert "retard" not in consigne


def test_un_verdict_qui_contient_des_titres_markdown_nest_pas_tronque(
    tmp_path, monkeypatch
):
    """La raison d'un verdict est du markdown de contrôleur, avec ses propres `## `. Découper sur
    le dernier `## ` venu perdrait la TÊTE du dernier bloc — c'est-à-dire le début de la consigne
    de correction, la valeur même que la reprise existe pour récupérer. L'ancre est la date ISO."""
    repo, db = _monde(tmp_path, monkeypatch)
    mid = _bloquer_a_la_main(repo, db, "consigne d'origine")
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
