import jsonutil


def test_extraire_json_simple():
    resultat = jsonutil.extraire('{"a": 1}')

    assert resultat == {"a": 1}


def test_extraire_json_entoure_de_prose():
    resultat = jsonutil.extraire('Voici le resultat : {"a": 1} merci')

    assert resultat == {"a": 1}


def test_extraire_objet_imbrique():
    resultat = jsonutil.extraire('{"a": {"b": 2}}')

    assert resultat == {"a": {"b": 2}}


def test_extraire_accolade_dans_valeur_chaine_ne_fausse_pas_la_profondeur():
    texte = '{"texte": "une { accolade } dans une chaine", "ok": true}'

    resultat = jsonutil.extraire(texte)

    assert resultat is not None
    assert resultat["ok"] is True
    assert resultat["texte"] == "une { accolade } dans une chaine"


def test_extraire_guillemet_echappe_ne_termine_pas_prematurement_la_chaine():
    texte = '{"texte": "une citation \\"echappee\\" ici", "ok": true}'

    resultat = jsonutil.extraire(texte)

    assert resultat == {"texte": 'une citation "echappee" ici', "ok": True}


def test_extraire_sans_json_renvoie_none():
    resultat = jsonutil.extraire("pas de json ici")

    assert resultat is None


def test_extraire_entree_vide_renvoie_none():
    resultat = jsonutil.extraire("")

    assert resultat is None


def test_extraire_entree_none_renvoie_none():
    resultat = jsonutil.extraire(None)  # type: ignore[arg-type] — None géré explicitement par `if not texte`

    assert resultat is None


def test_extraire_saute_premier_objet_invalide_et_prend_le_suivant():
    texte = "bad: {invalid json here} good: {\"a\": 2}"

    resultat = jsonutil.extraire(texte)

    assert resultat == {"a": 2}
