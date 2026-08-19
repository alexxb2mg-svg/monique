import pytest

from codemod_roles import inserer_entree_dict


def test_insertion_reussie_prealables_intacts():
    texte_source = (
        "ROLES = {\n"
        '    "alpha": "Rôle alpha",\n'
        '    "beta": "Rôle beta",\n'
        "}\n"
    )

    resultat = inserer_entree_dict(
        texte_source, "ROLES", '    "gamma": "Rôle gamma",\n'
    )

    assert '"alpha": "Rôle alpha",' in resultat
    assert '"beta": "Rôle beta",' in resultat
    assert '"gamma": "Rôle gamma",' in resultat
    # les entrées existantes n'ont pas été réécrites — comparaison exacte du bloc
    assert (
        '    "alpha": "Rôle alpha",\n'
        '    "beta": "Rôle beta",\n'
        '    "gamma": "Rôle gamma",\n'
    ) in resultat

    import ast

    ast.parse(resultat)  # ne lève rien


def test_insertion_cible_la_fermeture_racine_pas_une_fermeture_interne():
    texte_source = (
        "ROLES = {\n"
        '    "alpha": "texte avec {accolades internes} dedans",\n'
        '    "beta": {\n'
        '        "imbrique": "valeur",\n'
        "    },\n"
        "}\n"
    )

    resultat = inserer_entree_dict(
        texte_source, "ROLES", '    "gamma": "Rôle gamma",\n'
    )

    # la nouvelle entrée est juste avant la toute dernière accolade fermante,
    # pas injectée au milieu du dict imbriqué de "beta"
    assert resultat.rstrip().endswith(
        '    "gamma": "Rôle gamma",\n}'
    )
    # le contenu imbriqué et les accolades internes restent intacts
    assert '"alpha": "texte avec {accolades internes} dedans",' in resultat
    assert '"imbrique": "valeur",' in resultat

    import ast

    ast.parse(resultat)


def test_dict_introuvable_leve_valueerror():
    texte_source = "AUTRE_DICT = {\n}\n"

    with pytest.raises(ValueError):
        inserer_entree_dict(texte_source, "ROLES", '    "gamma": "x",\n')


def test_ligne_entree_invalide_leve_valueerror_et_ne_modifie_rien():
    texte_source = 'ROLES = {\n    "alpha": "Rôle alpha",\n}\n'
    texte_source_origine = texte_source

    with pytest.raises(ValueError):
        # chaîne non fermée => syntaxe cassée après insertion
        inserer_entree_dict(texte_source, "ROLES", '    "gamma": "non fermee,\n')

    # l'appelant garde son texte source intact — la fonction ne mute rien en place
    assert texte_source == texte_source_origine
