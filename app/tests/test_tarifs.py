import tarifs


def test_estimer_cout_usd_sonnet():
    assert tarifs.estimer_cout_usd("sonnet", 1_000_000, 1_000_000) == 12.0


def test_estimer_cout_usd_modele_inconnu():
    assert tarifs.estimer_cout_usd("modele_inconnu", 100, 100) is None
