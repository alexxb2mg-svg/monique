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
    # comme le vrai dépôt : ignorer le bruit pytest, sinon `git add -A` du harnais capte les
    # __pycache__ et un « rien codé » n'aurait pas un diff vide.
    (repo / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "base")
    return repo


def _agent_ecrit(nom, contenu="VALEUR = 42\n"):
    def faux_agent(role, consigne, worktree, reprendre=None):
        (Path(worktree) / "app" / nom).write_text(contenu, encoding="utf-8")
        return {"ok": True, "journal": [f"{role} · Write {nom}"], "texte": "fait"}

    return faux_agent


def _execution(db, mission_id):
    """Relit la ligne secw_executions de la mission (registre D-16, câblé dans executer_mission)."""
    con = entrepot.connexion_ecriture(db)
    try:
        return con.execute(
            "SELECT statut, delivery_outcome FROM secw_executions WHERE id=?",
            (mission_id,),
        ).fetchone()
    finally:
        con.close()


def _controleur_qui_dit(texte):
    """Agent factice : le contrôleur renvoie EXACTEMENT `texte` — pour tester le parse du verdict."""

    def faux(role, consigne, worktree, reprendre=None):
        return {"ok": True, "journal": [], "texte": texte}

    return faux


def test_verdict_accepte_hors_premiere_ligne(tmp_path):
    """Régression 2026-08-19 : le contrôleur raisonne d'abord, « VERDICT: ACCEPTÉ » en L3 — ne doit
    PLUS être jeté. L'ancien parse « 1re ligne non vide seule » ratait le verdict et rejetait par
    défaut, gâchant du code accepté."""
    texte = "Le statut git confirme le scope exact.\n\nVERDICT: ACCEPTÉ\n\nVérifs effectuées : ok."
    v = beecham._lancer_controleur(
        "scope", "diff", "1 passed", str(tmp_path), _agent=_controleur_qui_dit(texte)
    )
    assert v["verdict"] == "accepte"


def test_verdict_citation_trompeuse_reste_rejete(tmp_path):
    """Anti-citation : une mention « ACCEPTÉ » en milieu de phrase ne prime pas sur la ligne
    « VERDICT: REJETÉ ». L'ancrage sur une ligne qui DÉBUTE par VERDICT protège l'incident passé."""
    texte = "Je pourrais dire ACCEPTÉ vu le vert, mais non.\nVERDICT: REJETÉ\nl'approche casse X."
    v = beecham._lancer_controleur(
        "scope", "diff", "1 passed", str(tmp_path), _agent=_controleur_qui_dit(texte)
    )
    assert v["verdict"] == "rejeter"


def test_verdict_absent_defaut_corriger(tmp_path):
    """Aucune ligne « VERDICT: » => défaut SÛR « corriger » (récupérable), jamais « rejeter »."""
    texte = "Analyse en vrac, aucune conclusion formelle."
    v = beecham._lancer_controleur(
        "scope", "diff", "1 passed", str(tmp_path), _agent=_controleur_qui_dit(texte)
    )
    assert v["verdict"] == "corriger"


def test_correction_reprend_la_session_du_dev(tmp_path, monkeypatch):
    """--resume : au tour 2, le dev est relancé avec reprendre=<session_id du tour 1> (pas à froid)."""
    repo = _repo(tmp_path)
    monkeypatch.setattr(beecham, "RACINE", repo)
    monkeypatch.setattr(beecham, "WORKTREES", tmp_path / "wt")
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    mid = beecham.demarrer_mission("code à corriger une fois", db)

    reprises = []

    def dev(role, consigne, worktree, reprendre=None):
        reprises.append(reprendre)
        (Path(worktree) / "app" / "x.py").write_text("Y = 1\n", encoding="utf-8")
        return {"ok": True, "journal": [], "texte": "fait", "session_id": "SID-123"}

    verdicts = iter(["corriger", "accepte"])

    def ctrl(scope, diff, tests_resume, worktree):
        return {"verdict": next(verdicts), "raison": "revois X"}

    r = beecham.executer_mission(
        mid, chemin=db, _agent=dev, _controleur=ctrl, max_tours=3
    )
    assert r["statut"] == "valide"
    assert reprises[0] is None  # tour 1 : session fraîche
    assert reprises[1] == "SID-123"  # tour 2 : reprend la session du tour 1


def test_traitement_auto_accepte_fusionne(tmp_path, monkeypatch):
    """Traitement AUTOMATIQUE : le contrôleur accepte -> fusion locale, aucune action d'Alex."""
    repo = _repo(tmp_path)
    monkeypatch.setattr(beecham, "RACINE", repo)
    monkeypatch.setattr(beecham, "WORKTREES", tmp_path / "wt")
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")  # journal isolé
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    mid = beecham.demarrer_mission("ajouter un module bonjour", db)

    def controleur_ok(scope, diff, tests_resume, worktree):
        assert "VALEUR = 42" in diff  # revue ancrée sur le diff réel
        return {"verdict": "accepte", "raison": "conforme au scope"}

    r = beecham.executer_mission(
        mid, chemin=db, _agent=_agent_ecrit("bonjour.py"), _controleur=controleur_ok
    )
    assert r["statut"] == "valide"
    assert (repo / "app" / "bonjour.py").exists()  # fusionné dans main, tout seul
    assert beecham.lire_mission(mid, db)["statut"] == "valide"
    exe = _execution(db, mid)  # registre D-16 : accepté + fusionné -> completed/delivered
    assert exe["statut"] == "completed"
    assert exe["delivery_outcome"] == "delivered"


def test_traitement_auto_rejete_abandonne(tmp_path, monkeypatch):
    """Rejet PUR (approche mauvaise) : abandon automatique, rien ne fuit dans main."""
    repo = _repo(tmp_path)
    monkeypatch.setattr(beecham, "RACINE", repo)
    monkeypatch.setattr(beecham, "WORKTREES", tmp_path / "wt")
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")
    monkeypatch.setattr(beecham, "MEMOIRE", tmp_path / "atelier" / "memoire")
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    mid = beecham.demarrer_mission("changement à jeter", db)

    def controleur_rejette(scope, diff, tests_resume, worktree):
        return {"verdict": "rejeter", "raison": "approche mauvaise"}

    r = beecham.executer_mission(
        mid,
        chemin=db,
        _agent=_agent_ecrit("jetable.py", "X = 1\n"),
        _controleur=controleur_rejette,
    )
    assert r["statut"] == "rejete"
    assert not (repo / "app" / "jetable.py").exists()
    assert beecham.lire_mission(mid, db)["statut"] == "rejete"
    exe = _execution(db, mid)  # registre D-16 : rejeté -> failed, jamais delivered
    assert exe["statut"] == "failed"
    assert exe["delivery_outcome"] is None


def test_rejet_grave_la_lecon_dans_memoire_developpeur(tmp_path, monkeypatch):
    """Un rejet DÉFINITIF du contrôleur laisse une trace datée dans memoire/developpeur.md
    (consigne + raison) — pour que la même approche mauvaise ne revienne pas à zéro."""
    repo = _repo(tmp_path)
    monkeypatch.setattr(beecham, "RACINE", repo)
    monkeypatch.setattr(beecham, "WORKTREES", tmp_path / "wt")
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")
    monkeypatch.setattr(beecham, "MEMOIRE", tmp_path / "atelier" / "memoire")
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    mid = beecham.demarrer_mission("changement à jeter", db)

    def controleur_rejette(scope, diff, tests_resume, worktree):
        return {"verdict": "rejeter", "raison": "approche mauvaise, à éviter"}

    r = beecham.executer_mission(
        mid,
        chemin=db,
        _agent=_agent_ecrit("jetable.py", "X = 1\n"),
        _controleur=controleur_rejette,
    )
    assert r["statut"] == "rejete"

    contenu = beecham.chemin_memoire("developpeur").read_text(encoding="utf-8")
    assert "rejet" in contenu
    assert "changement à jeter" in contenu
    assert "approche mauvaise, à éviter" in contenu


def test_mission_atelier_auto_livree(tmp_path, monkeypatch):
    """Mission sans diff de code (atelier) -> `livre`, jamais `propose` en attente."""
    repo = _repo(tmp_path)
    monkeypatch.setattr(beecham, "RACINE", repo)
    monkeypatch.setattr(beecham, "WORKTREES", tmp_path / "wt")
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    mid = beecham.demarrer_mission("juste réfléchir, rien coder", db)

    def agent_sans_code(role, consigne, worktree, reprendre=None):
        return {"ok": True, "journal": [], "texte": "réflexion faite"}

    r = beecham.executer_mission(mid, chemin=db, _agent=agent_sans_code)
    assert r["statut"] == "livre"
    assert beecham.lire_mission(mid, db)["statut"] == "livre"
    exe = _execution(db, mid)  # registre D-16 : livré sans code -> completed, pas de livraison
    assert exe["statut"] == "completed"
    assert exe["delivery_outcome"] is None


def test_corriger_puis_bloque_au_plafond(tmp_path, monkeypatch):
    """« À corriger » en boucle : borné à max_tours, puis `bloque` (remonté à Alex) — jamais infini."""
    repo = _repo(tmp_path)
    monkeypatch.setattr(beecham, "RACINE", repo)
    monkeypatch.setattr(beecham, "WORKTREES", tmp_path / "wt")
    monkeypatch.setattr(beecham, "ATELIER", tmp_path / "atelier")
    db = str(tmp_path / "shadow.db")
    entrepot.init_fondations(db)
    mid = beecham.demarrer_mission("code toujours à corriger", db)

    tours = {"n": 0}

    def controleur_corrige_toujours(scope, diff, tests_resume, worktree):
        tours["n"] += 1
        return {"verdict": "corriger", "raison": "encore un point à revoir"}

    r = beecham.executer_mission(
        mid,
        chemin=db,
        _agent=_agent_ecrit("wip.py"),
        _controleur=controleur_corrige_toujours,
        max_tours=2,
    )
    assert r["statut"] == "bloque"
    assert tours["n"] == 2  # exactement max_tours, pas de boucle infinie
    assert beecham.lire_mission(mid, db)["statut"] == "bloque"
    exe = _execution(db, mid)  # registre D-16 : bloqué au plafond -> failed, pas de livraison
    assert exe["statut"] == "failed"
    assert exe["delivery_outcome"] is None


def test_lancer_controleur_trois_verdicts(tmp_path):
    """Parsing robuste : 1re ligne seule, accents (ACCEPTÉ==ACCEPTE), et le piège de l'incident."""

    def controleur(texte):
        return lambda role, consigne, worktree: {
            "ok": True,
            "journal": [],
            "texte": texte,
        }

    a = beecham._lancer_controleur(
        "s", "d", "t", tmp_path, _agent=controleur("VERDICT: ACCEPTÉ\nok")
    )
    assert a["verdict"] == "accepte"  # accent normalisé
    c = beecham._lancer_controleur(
        "s", "d", "t", tmp_path, _agent=controleur("VERDICT: À CORRIGER\nrevois X")
    )
    assert c["verdict"] == "corriger"
    rj = beecham._lancer_controleur(
        "s", "d", "t", tmp_path, _agent=controleur("VERDICT: REJETÉ\nnon")
    )
    assert rj["verdict"] == "rejeter"
    # piège incident : 1re ligne REJETÉ mais le corps cite « ACCEPTE » -> reste rejeter
    piege = beecham._lancer_controleur(
        "s",
        "d",
        "t",
        tmp_path,
        _agent=controleur("VERDICT: REJETÉ\nà l'inverse d'un 'VERDICT: ACCEPTE', non."),
    )
    assert piege["verdict"] == "rejeter"


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


def _atelier_isole(tmp_path, monkeypatch):
    """Redirige toutes les constantes de l'atelier vers tmp_path — jamais le vrai atelier."""
    atelier = tmp_path / "atelier"
    monkeypatch.setattr(beecham, "ATELIER", atelier)
    monkeypatch.setattr(beecham, "MEMOIRE", atelier / "memoire")
    monkeypatch.setattr(beecham, "JOURNAL", atelier / "journal.md")
    monkeypatch.setattr(beecham, "PLAN", atelier / "plan.md")
    return atelier


def test_init_atelier_cree_memoire_journal_plan(tmp_path, monkeypatch):
    atelier = _atelier_isole(tmp_path, monkeypatch)
    beecham.init_atelier()
    assert (atelier / "memoire").is_dir()
    assert (atelier / "journal.md").exists()
    assert (atelier / "plan.md").exists()


def test_journal_ajouter_est_append_only(tmp_path, monkeypatch):
    _atelier_isole(tmp_path, monkeypatch)
    beecham.journal_ajouter("developpeur", "première mission", "propose")
    contenu_1 = beecham.JOURNAL.read_text(encoding="utf-8")
    assert "première mission" in contenu_1

    beecham.journal_ajouter("controleur", "deuxième mission", "valide")
    contenu_2 = beecham.JOURNAL.read_text(encoding="utf-8")
    # la ligne précédente n'est jamais écrasée, la nouvelle s'ajoute
    assert "première mission" in contenu_2
    assert "deuxième mission" in contenu_2
    assert contenu_2.index("première mission") < contenu_2.index("deuxième mission")


def test_chemin_memoire_cree_le_fichier_avec_en_tete(tmp_path, monkeypatch):
    atelier = _atelier_isole(tmp_path, monkeypatch)
    chemin = beecham.chemin_memoire("chercheur")
    assert chemin == atelier / "memoire" / "chercheur.md"
    assert chemin.exists()
    assert "chercheur" in chemin.read_text(encoding="utf-8")


def _subprocess_popen_capture(appels):
    """Remplace beecham.subprocess.Popen : capture `cmd` sans lancer de vrai process."""

    def faux_popen(cmd, **kwargs):
        appels.append(cmd)

        class FauxProc:
            pid = 424242
            returncode = 0

            def communicate(self, timeout=None):
                return ("", "")

            def kill(self):
                pass

        return FauxProc()

    return faux_popen


def test_lancer_agent_injecte_plan_et_memoire(tmp_path, monkeypatch):
    """Le prompt est précédé du contenu de plan.md et de la mémoire du rôle."""
    atelier = _atelier_isole(tmp_path, monkeypatch)
    atelier.mkdir(parents=True, exist_ok=True)
    (atelier / "memoire").mkdir(parents=True, exist_ok=True)
    beecham.PLAN.write_text("PLAN-CONNU : refonte du module X\n", encoding="utf-8")
    (atelier / "memoire" / "developpeur.md").write_text(
        "MEMOIRE-CONNUE : piège déjà rencontré Y\n", encoding="utf-8"
    )

    import superviseur

    monkeypatch.setattr(superviseur, "enregistrer", lambda *a, **k: None)
    monkeypatch.setattr(superviseur, "finir", lambda *a, **k: None)
    appels = []
    monkeypatch.setattr(beecham.subprocess, "Popen", _subprocess_popen_capture(appels))

    beecham._lancer_agent("developpeur", "fais X", tmp_path)

    assert len(appels) == 1
    cmd = appels[0]
    prompt = cmd[cmd.index("-p") + 1]
    assert "PLAN-CONNU : refonte du module X" in prompt
    assert "MEMOIRE-CONNUE : piège déjà rencontré Y" in prompt
    assert "fais X" in prompt


def test_lancer_agent_sans_plan_ni_memoire_ne_casse_pas(tmp_path, monkeypatch):
    """Fichiers plan.md/mémoire absents : le prompt reste construit sans erreur."""
    _atelier_isole(tmp_path, monkeypatch)
    # aucun atelier écrit au préalable : plan.md et memoire/developpeur.md n'existent pas

    import superviseur

    monkeypatch.setattr(superviseur, "enregistrer", lambda *a, **k: None)
    monkeypatch.setattr(superviseur, "finir", lambda *a, **k: None)
    appels = []
    monkeypatch.setattr(beecham.subprocess, "Popen", _subprocess_popen_capture(appels))

    beecham._lancer_agent("developpeur", "fais X", tmp_path)

    assert len(appels) == 1
    cmd = appels[0]
    prompt = cmd[cmd.index("-p") + 1]
    assert "fais X" in prompt


def test_lancer_agent_indique_chemin_absolu_atelier(tmp_path, monkeypatch):
    """Le prompt indique le chemin ABSOLU de l'atelier partagé — jamais un chemin relatif,
    qui écrirait dans un dossier jetable du worktree isolé (invisible du diff git, détruit
    en fin de mission)."""
    atelier = _atelier_isole(tmp_path, monkeypatch)
    atelier.mkdir(parents=True, exist_ok=True)
    (atelier / "memoire").mkdir(parents=True, exist_ok=True)

    import superviseur

    monkeypatch.setattr(superviseur, "enregistrer", lambda *a, **k: None)
    monkeypatch.setattr(superviseur, "finir", lambda *a, **k: None)
    appels = []
    monkeypatch.setattr(beecham.subprocess, "Popen", _subprocess_popen_capture(appels))

    beecham._lancer_agent("developpeur", "fais X", tmp_path)

    assert len(appels) == 1
    cmd = appels[0]
    prompt = cmd[cmd.index("-p") + 1]
    assert str(atelier.resolve()) in prompt


def test_garde_fou_ecriture_deny_by_default(tmp_path):
    wt = tmp_path / "worktree"
    atelier = tmp_path / "atelier"
    prod = tmp_path / "production"
    for d in (wt, atelier, prod):
        (d / "app").mkdir(parents=True)
    zones = [str(wt), str(atelier)]

    # AUTORISÉ : sous le worktree ou l'atelier
    assert beecham.zone_ecriture_autorisee(str(wt / "app" / "x.py"), zones)
    assert beecham.zone_ecriture_autorisee(str(atelier / "note.md"), zones)
    assert beecham.zone_ecriture_autorisee(str(wt / "app" / "sous" / "y.py"), zones)

    # REFUSÉ : la production, ailleurs, la racine
    assert not beecham.zone_ecriture_autorisee(str(prod / "app" / "devis.txt"), zones)
    assert not beecham.zone_ecriture_autorisee(str(tmp_path / "hors.txt"), zones)
    assert not beecham.zone_ecriture_autorisee("C:/ailleurs/x.txt", zones)

    # REFUSÉ : évasion par .. (realpath résout la remontée)
    assert not beecham.zone_ecriture_autorisee(
        str(wt / "app" / ".." / ".." / "production" / "y"), zones
    )

    # deny-by-default : zones vides => tout refusé
    assert not beecham.zone_ecriture_autorisee(str(wt / "x"), [])


def test_role_planificateur_existe_et_est_scope():
    assert "planificateur" in beecham.ROLES
    texte = beecham.ROLES["planificateur"]
    assert "plan" in texte or "planifi" in texte

    outils = beecham._OUTILS["planificateur"]
    assert "Bash" not in outils
    assert "Edit" not in outils


def test_role_vitrine_existe_et_est_scope():
    assert "vitrine" in beecham.ROLES
    texte = beecham.ROLES["vitrine"]
    assert "Interface" in texte or "lisible" in texte

    outils = beecham._OUTILS["vitrine"]
    assert "Bash" not in outils


def test_role_chef_dev_existe_et_est_scope():
    assert "chef_dev" in beecham.ROLES
    texte = beecham.ROLES["chef_dev"]
    assert "Informatique" in texte or "scope" in texte

    outils = beecham._OUTILS["chef_dev"]
    assert "Bash" not in outils
    assert "Edit" not in outils


def test_role_vision_existe_et_est_scope():
    assert "vision" in beecham.ROLES
    texte = beecham.ROLES["vision"]
    assert "Qualité" in texte or "constats" in texte

    outils = beecham._OUTILS["vision"]
    assert outils.strip() == "Read"


def test_role_fournisseurs_materiel_existe_et_est_scope():
    assert "fournisseurs_materiel" in beecham.ROLES
    assert "Approvisionnement" in beecham.ROLES["fournisseurs_materiel"]

    assert beecham._OUTILS["fournisseurs_materiel"] == "Read,Glob,Grep,Write,WebFetch"
