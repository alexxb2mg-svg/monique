"""Carte de contexte : le prompt de mission ne porte plus plan.md ENTIER + la mémoire ENTIÈRE du
rôle (~9 700 caractères par mission, en croissance à chaque vague) mais un extrait borné plus un
renvoi vers les fichiers complets, que l'agent lit lui-même avec Read.

Ces tests pinnent l'INVARIANT (ce que la carte doit porter), pas le découpage : si l'injection
intégrale revenait, ou si un tri reclassait les sections devant la vague en cours, ils tombent.
"""

import beecham


def _atelier(tmp_path, monkeypatch, plan="", memoire=""):
    """Atelier jetable : ne patche QUE `beecham.ATELIER` (les autres chemins en découlent, C3)."""
    atelier = tmp_path / "atelier"
    (atelier / "memoire").mkdir(parents=True)
    monkeypatch.setattr(beecham, "ATELIER", atelier)
    (atelier / "plan.md").write_text(plan, encoding="utf-8")
    if memoire:
        (atelier / "memoire" / "developpeur.md").write_text(memoire, encoding="utf-8")
    return atelier


def test_carte_bornee_et_bien_plus_courte_que_les_fichiers(tmp_path, monkeypatch):
    """Borne DURE respectée même sur des fichiers énormes — c'est le point : la carte ne grossit
    pas avec l'atelier."""
    plan = "## Ordre global\n" + "une ligne de plan bien remplie.\n" * 2000
    memoire = "- une lecon deja apprise par le role.\n" * 2000
    _atelier(tmp_path, monkeypatch, plan=plan, memoire=memoire)

    carte = beecham._carte_contexte("developpeur")

    assert len(carte) <= beecham.BORNE_CARTE
    assert len(carte) < len(plan) / 10
    assert carte.count("\n\n")  # le découpage garde des blocs lisibles


def test_carte_donne_les_chemins_absolus_des_fichiers_entiers(tmp_path, monkeypatch):
    """Tronquer sans dire où lire la suite, c'est perdre l'information."""
    atelier = _atelier(tmp_path, monkeypatch, plan="## Ordre global\ndetail.\n", memoire="- x\n")

    carte = beecham._carte_contexte("developpeur")

    assert str((atelier / "plan.md").resolve()) in carte
    assert str((atelier / "memoire" / "developpeur.md").resolve()) in carte
    assert "Read" in carte


def test_les_sections_closes_sont_ecartees(tmp_path, monkeypatch):
    """`## Clos` est de l'historique : il n'a rien à faire dans un budget de 2 000 caractères."""
    _atelier(
        tmp_path,
        monkeypatch,
        plan=(
            "## Clos — ne plus rechercher\nMARQUEUR-HISTORIQUE : deja fait.\n\n"
            "## Ordre global\nMARQUEUR-VAGUE : mission en cours.\n"
        ),
    )

    carte = beecham._carte_contexte("developpeur")

    assert "MARQUEUR-VAGUE" in carte
    assert "MARQUEUR-HISTORIQUE" not in carte


def test_plan_sans_section_est_rendu_tel_quel(tmp_path, monkeypatch):
    """Un plan encore vierge (pas de `## `) ne doit pas disparaître du prompt."""
    _atelier(tmp_path, monkeypatch, plan="PLAN-BRUT : contenu sans titre\n")

    assert "PLAN-BRUT" in beecham._carte_contexte("developpeur")


def test_la_vague_survit_meme_si_une_grosse_section_nomme_le_role(tmp_path, monkeypatch):
    """Régression : une section qui NOMME le rôle ne doit pas passer devant la vague en cours et
    la faire évincer par la troncature. Cas réel : `## Départements` (1 250 c.) nomme le
    planificateur, `## Ordre global` (la vague) ne le nomme pas."""
    _atelier(
        tmp_path,
        monkeypatch,
        plan=(
            "## Ordre global\nMARQUEUR-VAGUE : mission en cours.\n"
            + "detail de vague.\n" * 40
            + "\n## Departements\nPilotage : un planificateur par vague.\n"
            + "ligne de departement pour le planificateur.\n" * 40
        ),
    )

    assert "MARQUEUR-VAGUE" in beecham._carte_contexte("planificateur")


def test_la_memoire_garde_ses_dernieres_lignes(tmp_path, monkeypatch):
    """La mémoire est append-only : tronquée, c'est la FIN qui vaut (les leçons récentes)."""
    memoire = (
        "- VIEILLE-LECON\n"
        + "- une lecon intermediaire sans interet particulier.\n" * 500
        + "- LECON-RECENTE\n"
    )
    _atelier(tmp_path, monkeypatch, plan="## Ordre global\ndetail.\n", memoire=memoire)

    carte = beecham._carte_contexte("developpeur")

    assert "LECON-RECENTE" in carte
    assert "VIEILLE-LECON" not in carte


def test_fail_soft_un_fichier_illisible_ne_tue_pas_la_carte(tmp_path, monkeypatch):
    """Un atelier abîmé dégrade la carte, jamais la mission."""
    atelier = _atelier(tmp_path, monkeypatch, plan="")
    (atelier / "plan.md").unlink()
    (atelier / "plan.md").mkdir()  # read_text -> OSError (IsADirectory / Permission selon l'OS)
    def memoire_illisible(role):
        raise OSError("illisible")

    monkeypatch.setattr(beecham, "chemin_memoire", memoire_illisible)

    assert beecham._carte_contexte("developpeur") == ""


def test_le_prompt_envoye_porte_la_carte_et_pas_le_plan_entier(tmp_path, monkeypatch):
    """Filet du bout en bout, sur le prompt RÉELLEMENT écrit sur stdin : consignes fixes en tête,
    vague présente, section close absente. Si l'injection intégrale revenait, ce test tombe."""
    _atelier(
        tmp_path,
        monkeypatch,
        plan=(
            "## Clos — historique\nMARQUEUR-HISTORIQUE : deja fait.\n"
            + "vieille ligne close.\n" * 200
            + "\n## Ordre global\nMARQUEUR-VAGUE : mission en cours.\n"
        ),
    )
    monkeypatch.setattr(beecham, "_relever_canal", lambda role: ([], []))

    import superviseur

    monkeypatch.setattr(superviseur, "enregistrer", lambda *a, **k: None)
    monkeypatch.setattr(superviseur, "finir", lambda *a, **k: None)

    envoyes = []

    def faux_popen(cmd, **kwargs):
        class FauxProc:
            pid = 424242
            returncode = 0

            def communicate(self, input=None, timeout=None):
                if cmd[0] == "claude":  # le superviseur peut lancer d'autres Popen
                    envoyes.append(input or "")
                return ("", "")

            def kill(self):
                pass

        return FauxProc()

    monkeypatch.setattr(beecham.subprocess, "Popen", faux_popen)

    beecham._lancer_agent("developpeur", "CONSIGNE-DU-JOUR", tmp_path)

    assert len(envoyes) == 1
    prompt = envoyes[0]
    assert prompt.startswith("Tu travailles dans une COPIE ISOLÉE")  # invariant en tête
    assert "CONSIGNE-DU-JOUR" in prompt
    assert "MARQUEUR-VAGUE" in prompt
    assert "MARQUEUR-HISTORIQUE" not in prompt
    assert "vieille ligne close." not in prompt
