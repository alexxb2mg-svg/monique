import orchestrateur as O

AGENTS = {
    "secretaire": {"triggers": ["canal=email", "tag=relance"]},
    "chercheur": {"triggers": ["tag=veille"]},
}


def test_route_par_canal():
    assert O.router_deterministe({"canal": "email"}, AGENTS) == "secretaire"


def test_route_par_tag():
    assert (
        O.router_deterministe({"canal": "web", "tags": ["veille"]}, AGENTS)
        == "chercheur"
    )


def test_specificite_gagne():
    # email + relance => secrétaire matche 2 triggers, gagne
    a = O.router_deterministe({"canal": "email", "tags": ["relance", "veille"]}, AGENTS)
    assert a == "secretaire"


def test_aucun_match():
    assert O.router_deterministe({"canal": "inconnu"}, AGENTS) is None


def test_egalite_de_score_defere():
    # revue M1 : deux agents à score égal => None (defer au LLM), JAMAIS l'ordre disque
    deux = {"a": {"triggers": ["canal=email"]}, "b": {"triggers": ["canal=email"]}}
    assert O.router_deterministe({"canal": "email"}, deux) is None


def test_match_insensible_a_la_casse():
    # revue MINEUR-7 : tags/canaux normalisés
    ag = {"chercheur": {"triggers": ["tag=Veille"]}}
    assert (
        O.router_deterministe({"canal": "web", "tags": ["VEILLE"]}, ag) == "chercheur"
    )
