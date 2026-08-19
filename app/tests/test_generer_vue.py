import pytest

from generer_vue import generer


def test_generer_cree_les_trois_fichiers(tmp_path):
    fichiers = generer("commandes", "Commandes fournisseurs", racine=tmp_path)

    assert fichiers["vue_py"] == tmp_path / "vue_commandes.py"
    assert fichiers["template"] == tmp_path / "templates" / "vue_commandes.html"
    assert fichiers["test"] == tmp_path / "tests" / "test_vue_commandes.py"

    contenu_py = fichiers["vue_py"].read_text(encoding="utf-8")
    assert "def contexte_commandes(" in contenu_py

    contenu_html = fichiers["template"].read_text(encoding="utf-8")
    assert "Commandes fournisseurs" in contenu_html
    assert "{% for" in contenu_html
    assert "{% else %}" in contenu_html

    contenu_test = fichiers["test"].read_text(encoding="utf-8")
    assert "contexte_commandes" in contenu_test
    assert "import vue_commandes" in contenu_test


def test_generer_nom_invalide_ne_touche_pas_le_disque(tmp_path):
    with pytest.raises(ValueError):
        generer("../evil", "Mauvais nom", racine=tmp_path)
    with pytest.raises(ValueError):
        generer("Nom Avec Espaces", "Mauvais nom", racine=tmp_path)

    assert list(tmp_path.iterdir()) == []


def test_generer_refuse_ecrasement_sans_flag(tmp_path):
    generer("commandes", "Commandes fournisseurs", racine=tmp_path)
    contenu_py_origine = (tmp_path / "vue_commandes.py").read_text(encoding="utf-8")
    contenu_html_origine = (tmp_path / "templates" / "vue_commandes.html").read_text(
        encoding="utf-8"
    )
    contenu_test_origine = (tmp_path / "tests" / "test_vue_commandes.py").read_text(
        encoding="utf-8"
    )

    with pytest.raises(FileExistsError):
        generer("commandes", "Libellé modifié", racine=tmp_path)

    # aucun des 3 fichiers déjà écrits n'a été touché par la tentative refusée
    assert (tmp_path / "vue_commandes.py").read_text(encoding="utf-8") == contenu_py_origine
    assert (tmp_path / "templates" / "vue_commandes.html").read_text(
        encoding="utf-8"
    ) == contenu_html_origine
    assert (tmp_path / "tests" / "test_vue_commandes.py").read_text(
        encoding="utf-8"
    ) == contenu_test_origine


def test_generer_ecrase_si_flag_explicite(tmp_path):
    generer("commandes", "Commandes fournisseurs", racine=tmp_path)

    fichiers = generer("commandes", "Libellé modifié", racine=tmp_path, ecraser=True)

    contenu_html = fichiers["template"].read_text(encoding="utf-8")
    assert "Libellé modifié" in contenu_html
    assert "Commandes fournisseurs" not in contenu_html
