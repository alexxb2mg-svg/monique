"""Modèle par rôle : on paie selon la difficulté réelle de la tâche.

Avant, `--model sonnet` était codé en dur pour tous : même prix pour trier un fichier que pour
arbitrer une architecture. La table est une DONNÉE lisible et modifiable, pas un jugement d'un LLM
au moment de l'exécution — même logique que partout ailleurs dans ce harnais.
"""

import beecham


def test_le_chef_arbitre_avec_le_modele_le_plus_capable():
    """Le chef fait la revue générale et tranche : c'est lui qui engage tout le reste."""
    assert beecham.modele_pour("chef") == "claude-fable-5"


def test_les_roles_exigeants_ont_un_modele_haut_de_gamme():
    for role in ("stratege", "auditeur", "developpeur", "chef_dev", "controleur"):
        assert beecham.modele_pour(role) == "claude-opus-5", role


def test_les_roles_de_lecture_restent_sur_le_defaut():
    """Veille, mise en forme, surveillance : pas la peine de payer le prix fort."""
    for role in ("chercheur", "vitrine", "veilleur", "documentaliste"):
        assert beecham.modele_pour(role) == "sonnet", role


def test_role_inconnu_retombe_sur_le_defaut():
    assert beecham.modele_pour("agent_qui_nexiste_pas") == "sonnet"
    assert beecham.modele_pour("") == "sonnet"


def test_chaque_role_declare_a_un_modele_resoluble():
    """Aucun rôle ne doit se retrouver sans modèle utilisable."""
    for role in beecham.ROLES:
        assert beecham.modele_pour(role)


def test_les_alias_utilises_sont_ceux_acceptes_par_le_cli():
    """`--model` accepte un alias court (fable/opus/sonnet) ou un nom complet (claude-*).
    « opus-4-8 » n'est NI l'un NI l'autre — piège vérifié contre `claude --help` avant livraison."""
    alias_courts = {"fable", "opus", "sonnet", "haiku"}
    for role in beecham.ROLES:
        modele = beecham.modele_pour(role)
        assert modele in alias_courts or modele.startswith("claude-"), (
            f"{role} : {modele!r} n'est ni un alias court ni un nom complet"
        )


def test_le_modele_est_bien_passe_a_la_commande(monkeypatch, tmp_path):
    """Vérifie le branchement réel : le modèle du rôle arrive dans l'argv de `claude`.

    On collecte TOUS les Popen puis on cherche celui de `claude` : le superviseur en lance un
    autre (PowerShell, pour lire l'heure de démarrage du process) juste après, qui écraserait une
    capture à valeur unique. Piège rencontré en écrivant ce test.
    """
    appels = []

    class _FauxPopen:
        def __init__(self, cmd, **kw):
            appels.append(cmd)

        def communicate(self, input=None, timeout=None):
            return "", ""

        @property
        def returncode(self):
            return 0

        @property
        def pid(self):
            return 0

    monkeypatch.setattr(beecham.subprocess, "Popen", _FauxPopen)
    monkeypatch.setattr(beecham, "_ecrire_garde", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(beecham, "_relever_canal", lambda role: ([], []))
    monkeypatch.setattr(beecham, "_archiver_canal", lambda role, m: None)
    monkeypatch.setattr(beecham, "_collecter_canal", lambda role, wt: {"deposes": 0, "fil": 0, "rejetes": 0})

    def _modele_utilise(role, **kw):
        appels.clear()
        beecham._lancer_agent(role, "une consigne", str(tmp_path), **kw)
        claude = next(c for c in appels if c and c[0] == "claude")
        return claude[claude.index("--model") + 1]

    assert _modele_utilise("chef") == "claude-fable-5"
    assert _modele_utilise("developpeur") == "claude-opus-5"
    assert _modele_utilise("chercheur") == "sonnet"
    # choix d'Alex sur l'accueil : il prime sur la table...
    assert _modele_utilise("chef", modele="claude-haiku-4-5-20251001") == "claude-haiku-4-5-20251001"
    # ...mais l'absence de choix ne doit surtout pas vider `--model`.
    assert _modele_utilise("chef", modele=None) == "claude-fable-5"


# --- le choix d'Alex ne se perd pas en route ----------------------------------------------------


def test_les_modeles_offerts_sur_l_accueil_sont_lancables():
    """Le menu d'Alex ne doit proposer que des valeurs que `claude --model` accepte."""
    for valeur, libelle in beecham.MODELES_OFFERTS.items():
        assert valeur.startswith("claude-"), valeur
        assert libelle.strip(), valeur


def test_la_relance_du_rapport_garde_le_modele_choisi(monkeypatch):
    """La porte de sortie renvoie l'agent à SA session : elle doit le rallumer sur le modèle qu'Alex
    a choisi, sinon le rapport repart sur un autre modèle que le travail."""
    vus = []

    def faux_lancer(role, consigne, worktree, reprendre=None, _relancer_rapport=True, modele=None):
        vus.append(modele)
        return {"ok": True, "journal": [], "texte": "prose", "session_id": reprendre}

    monkeypatch.setattr(beecham, "_lancer_agent", faux_lancer)
    beecham._porte_rapport(
        "chef", "un rapport non conforme", "/wt", "sess-9", [], True, "claude-opus-5"
    )
    assert vus == ["claude-opus-5"]
