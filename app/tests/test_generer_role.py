import pytest

from generer_role import contenu_role_md, ecrire_role


def test_contenu_role_md_structure():
    texte = contenu_role_md(
        "mon_agent",
        "Interface",
        ["tag=front", "canal=web"],
        "s'occupe de la vitrine",
        "Tu es l'agent de test.",
    )
    assert texte.startswith("---")
    assert "name: mon_agent\n" in texte
    assert "departement: Interface\n" in texte
    assert "triggers_deterministes: [tag=front, canal=web]\n" in texte
    assert "description_routage: s'occupe de la vitrine\n" in texte
    assert texte.strip().endswith("Tu es l'agent de test.")


def test_ecrire_role_cree_le_fichier(tmp_path):
    fichier = ecrire_role(
        "mon_agent",
        "Interface",
        ["tag=front"],
        "s'occupe de la vitrine",
        "Tu es l'agent de test.",
        racine=tmp_path,
    )
    assert fichier == tmp_path / "mon_agent" / "ROLE.md"
    assert fichier.exists()
    contenu = fichier.read_text(encoding="utf-8")
    assert "name: mon_agent" in contenu
    assert "Tu es l'agent de test." in contenu


def test_ecrire_role_refuse_ecrasement_sans_flag(tmp_path):
    ecrire_role(
        "mon_agent", "Interface", ["tag=front"], "desc", "corps", racine=tmp_path
    )
    with pytest.raises(FileExistsError):
        ecrire_role(
            "mon_agent",
            "Interface",
            ["tag=front"],
            "desc",
            "corps modifié",
            racine=tmp_path,
        )
    # le contenu d'origine n'a pas été écrasé
    contenu = (tmp_path / "mon_agent" / "ROLE.md").read_text(encoding="utf-8")
    assert "corps modifié" not in contenu


def test_ecrire_role_nom_invalide_ne_touche_pas_le_disque(tmp_path):
    with pytest.raises(ValueError):
        ecrire_role(
            "../evil", "Interface", ["tag=front"], "desc", "corps", racine=tmp_path
        )
    with pytest.raises(ValueError):
        ecrire_role(
            "Nom Avec Espaces",
            "Interface",
            ["tag=front"],
            "desc",
            "corps",
            racine=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []
