import pytest

from creer_vue import creer
from generer_vue import generer


def test_creer_produit_les_memes_fichiers_que_generer(tmp_path):
    racine_creer = tmp_path / "via_creer"
    racine_direct = tmp_path / "via_direct"

    fichiers_creer = creer("mavue", "Ma Vue", racine=racine_creer)
    fichiers_direct = generer("mavue", "Ma Vue", racine=racine_direct)

    assert fichiers_creer.keys() == fichiers_direct.keys()
    for cle in fichiers_creer:
        assert fichiers_creer[cle].read_text(encoding="utf-8") == fichiers_direct[cle].read_text(
            encoding="utf-8"
        )


def test_creer_nom_invalide_leve_erreur_de_generer_vue(tmp_path):
    with pytest.raises(ValueError):
        creer("../evil", "Libellé", racine=tmp_path)
    assert list(tmp_path.iterdir()) == []
