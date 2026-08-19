import catalogue_prix


def test_prix_connu():
    assert catalogue_prix.prix("anthropic", "claude-sonnet-5") == {"entree": 2.0, "sortie": 10.0}


def test_prix_inconnu_renvoie_none():
    assert catalogue_prix.prix("anthropic", "modele-qui-n-existe-pas") is None
    assert catalogue_prix.prix("fournisseur-inconnu", "x") is None


def test_deepseek_absent_du_catalogue():
    """DeepSeek volontairement exclu : tarif dépendant de l'heure UTC et du ratio cache
    hit/miss, deux critères non déterminables ici — hors scope (question de modélisation
    ouverte), pas juste 'palier de contexte'."""
    assert "deepseek" not in catalogue_prix.CATALOGUE_PRIX_USD


def test_xai_present_avec_structure_a_paliers():
    """xAI/Grok est désormais couvert : son tarif dépend d'un unique critère déterministe
    (le volume d'input_tokens), transcrit en structure 'paliers' plutôt qu'exclu."""
    p = catalogue_prix.prix("xai", "grok-4.6")
    assert p is not None
    assert "paliers" in p


def test_estimer_cout_usd():
    cout = catalogue_prix.estimer_cout_usd("mistral", "mistral-small-4", 1_000_000, 1_000_000)
    assert cout == 0.15 + 0.60


def test_estimer_cout_usd_anthropic_non_regression():
    """Non-régression : un fournisseur déjà présent (format simple entree/sortie) doit
    renvoyer exactement le même résultat qu'avant l'introduction du format à paliers."""
    cout = catalogue_prix.estimer_cout_usd("anthropic", "claude-sonnet-5", 500_000, 200_000)
    assert cout == 500_000 / 1_000_000 * 2.0 + 200_000 / 1_000_000 * 10.0


def test_estimer_cout_usd_grok_tarif_standard_sous_200k():
    """Sous le seuil de 200 000 tokens d'entrée : tarif standard."""
    cout = catalogue_prix.estimer_cout_usd("xai", "grok-4.6", 100_000, 50_000)
    assert cout == 100_000 / 1_000_000 * 2.0 + 50_000 / 1_000_000 * 6.0


def test_estimer_cout_usd_grok_tarif_majore_a_200k_applique_a_lintegralite():
    """À 200 000 tokens d'entrée ou au-dessus : tarif majoré appliqué à l'INTÉGRALITÉ de la
    requête (entrée ET sortie), pas seulement au dépassement."""
    cout = catalogue_prix.estimer_cout_usd("xai", "grok-4.6", 200_000, 50_000)
    assert cout == 200_000 / 1_000_000 * 4.0 + 50_000 / 1_000_000 * 12.0


def test_estimer_cout_usd_modele_inconnu():
    assert catalogue_prix.estimer_cout_usd("anthropic", "inconnu", 100, 100) is None


def test_comparer_fournisseurs_trie_par_cout_croissant():
    nb_modeles_total = sum(len(modeles) for modeles in catalogue_prix.CATALOGUE_PRIX_USD.values())
    resultats = catalogue_prix.comparer_fournisseurs(1_000_000, 1_000_000)
    assert len(resultats) == nb_modeles_total
    for actuel, suivant in zip(resultats, resultats[1:]):
        assert actuel["cout_usd"] <= suivant["cout_usd"]
