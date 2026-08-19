import digest


def test_digest_texte_vide():
    resultat = digest.digest_texte("")

    assert resultat == {"total": 0, "compte": {}, "entrees": []}


def test_digest_texte_une_entree_simple():
    texte = "- 2026-08-19T09:18:30.320993 · developpeur · accepté + fusionné (local) · valide\n"

    resultat = digest.digest_texte(texte)

    assert resultat["total"] == 1
    assert resultat["compte"] == {"valide": 1}
    assert resultat["entrees"] == [{"agent": "developpeur", "statut": "valide"}]


def test_digest_texte_entree_multiligne_comptee_une_seule_fois():
    texte = (
        "- 2026-08-19T09:20:07.221314 · chercheur · corriger: VERDICT: À CORRIGER\n"
        "**Le bilan n'est pas rejouable — les chiffres présentés comme des faits sont fabriqués.**\n"
        "\n"
        "Vérification externe (pas seulement lecture du diff) confirme le rejet\n"
        "des chiffres avancés · rejete\n"
    )

    resultat = digest.digest_texte(texte)

    assert resultat["total"] == 1
    assert resultat["compte"] == {"rejete": 1}
    assert resultat["entrees"] == [{"agent": "chercheur", "statut": "rejete"}]


def test_digest_texte_plusieurs_entrees_melangees_avec_n_dernieres():
    texte = (
        "- 2026-08-19T08:00:00.000000 · developpeur · première entrée · valide\n"
        "- 2026-08-19T08:10:00.000000 · chercheur · deuxième entrée\n"
        "sur plusieurs lignes\n"
        "avec un texte long · rejete\n"
        "- 2026-08-19T08:20:00.000000 · controleur · troisième entrée · valide\n"
        "- 2026-08-19T08:30:00.000000 · developpeur · quatrième entrée · en_cours\n"
    )

    resultat = digest.digest_texte(texte, n_dernieres=2)

    assert resultat["total"] == 2
    assert resultat["compte"] == {"valide": 1, "en_cours": 1}
    assert resultat["entrees"] == [
        {"agent": "controleur", "statut": "valide"},
        {"agent": "developpeur", "statut": "en_cours"},
    ]
