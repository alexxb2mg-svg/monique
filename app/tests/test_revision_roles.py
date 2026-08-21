"""D-15 Phase 2 : outillage de révision des prompts d'agent.

Portée volontairement bornée (Ponytail) : le dossier prévoyait un « Bot HR » méta-agent plus un
évaluateur sandbox. Le vrai frein constaté à l'usage n'est pas là — c'est que chaque rôle vit en
DEUX exemplaires (`beecham.ROLES` et `agents/<nom>/ROLE.md`) qu'il faut éditer à l'identique, ce
qui rend toute révision pénible et fautive (un anglicisme est passé le 21/08 en révisant les 8 à
la main). On outille donc ce geste-là, rien de plus.
"""

import roles


def test_audit_liste_les_roles_du_plus_mince_au_plus_etoffe():
    resultat = roles.auditer()
    assert resultat, "l'audit ne doit pas être vide"
    tailles = [r["caracteres"] for r in resultat]
    assert tailles == sorted(tailles)


def test_audit_expose_les_champs_utiles():
    premier = roles.auditer()[0]
    assert set(premier) == {"nom", "departement", "caracteres", "mince"}


def test_audit_marque_les_prompts_sous_le_seuil():
    """Teste le MÉCANISME, pas l'état d'un rôle nommé.

    Première version de ce test : elle affirmait que `chercheur` était mince (c'était vrai, et
    c'est le cas réel qui a motivé l'outil). Elle a cassé dès qu'on a étoffé ce prompt — un test
    ne doit pas se briser parce qu'on a fait le travail qu'il désignait.
    """
    resultat = roles.auditer()
    tailles = sorted(r["caracteres"] for r in resultat)
    seuil = (tailles[0] + tailles[-1]) // 2  # entre le plus court et le plus long

    for r in roles.auditer(seuil=seuil):
        assert r["mince"] is (r["caracteres"] < seuil)


def test_seuil_ajustable():
    assert all(r["mince"] for r in roles.auditer(seuil=100000))
    assert not any(r["mince"] for r in roles.auditer(seuil=1))
