from pathlib import Path

import fournisseurs_materiel as FM


def test_lister_fournisseurs_vide_par_defaut():
    assert FM.lister_fournisseurs() == []


def test_registre_est_une_liste_independante_de_fournisseurs_py():
    assert isinstance(FM.REGISTRE, list)

    source_fournisseurs = (Path(__file__).parent.parent / "fournisseurs.py").read_text(encoding="utf-8")
    assert "fournisseurs_materiel" not in source_fournisseurs
