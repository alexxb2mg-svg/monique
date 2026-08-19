import catalogue_prix


def test_prix_connu():
    assert catalogue_prix.prix("anthropic", "claude-sonnet-5") == {"entree": 2.0, "sortie": 10.0}


def test_prix_inconnu_renvoie_none():
    assert catalogue_prix.prix("anthropic", "modele-qui-n-existe-pas") is None
    assert catalogue_prix.prix("fournisseur-inconnu", "x") is None


def test_xai_absent_du_catalogue():
    """xAI/Grok volontairement exclu : tous ses modèles ont un palier de prix dans la source,
    donc aucun n'est un cas simple transcriptible ici."""
    assert "xai" not in catalogue_prix.CATALOGUE_PRIX_USD


def test_estimer_cout_usd():
    cout = catalogue_prix.estimer_cout_usd("mistral", "mistral-small-4", 1_000_000, 1_000_000)
    assert cout == 0.15 + 0.60


def test_estimer_cout_usd_modele_inconnu():
    assert catalogue_prix.estimer_cout_usd("anthropic", "inconnu", 100, 100) is None
