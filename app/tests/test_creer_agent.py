import pytest

from creer_agent import creer
from generer_role import ecrire_role


def test_creer_produit_le_meme_fichier_que_ecrire_role(tmp_path):
    racine_creer = tmp_path / "via_creer"
    racine_direct = tmp_path / "via_direct"

    fichier_creer = creer(
        "mon_agent",
        "Interface",
        ["tag=front", "canal=web"],
        "s'occupe de la vitrine",
        "Tu es l'agent de test.",
        racine=racine_creer,
    )
    fichier_direct = ecrire_role(
        "mon_agent",
        "Interface",
        ["tag=front", "canal=web"],
        "s'occupe de la vitrine",
        "Tu es l'agent de test.",
        racine=racine_direct,
    )

    assert fichier_creer.read_text(encoding="utf-8") == fichier_direct.read_text(
        encoding="utf-8"
    )


def test_creer_nom_invalide_leve_erreur_de_generer_role(tmp_path):
    with pytest.raises(ValueError):
        creer(
            "../evil",
            "Interface",
            ["tag=front"],
            "desc",
            "corps",
            racine=tmp_path,
        )
    assert list(tmp_path.iterdir()) == []
