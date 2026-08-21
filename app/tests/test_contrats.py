import contrats


def test_valider_action_non_externe_ou_vide():
    # Cas nominal : action vide ou sans type d'envoi externe
    assert contrats.valider({}) == (True, "")
    assert contrats.valider({"type": "lecture_fichier", "payload": "data"}) == (True, "")


def test_valider_envoi_externe_avec_verrou_valide():
    # Cas nominal : type d'envoi externe avec au moins un verrou actif (is_draft ou requires_human_validation)
    types_externes = ["email", "sms", "whatsapp", "telegram", "envoi_externe"]

    for t in types_externes:
        assert contrats.valider({"type": t, "is_draft": True}) == (True, "")
        assert contrats.valider({"type": t, "requires_human_validation": True}) == (True, "")
        assert contrats.valider(
            {"type": t, "is_draft": True, "requires_human_validation": True}
        ) == (True, "")


def test_valider_envoi_externe_sans_verrou_refuse():
    # Cas limite : type d'envoi externe mais aucun verrou (clés absentes ou explicitement à False)
    res_absent, raison_absent = contrats.valider({"type": "email"})
    assert res_absent is False
    assert "is_draft" in raison_absent or "requires_human_validation" in raison_absent

    res_false, raison_false = contrats.valider(
        {"type": "whatsapp", "is_draft": False, "requires_human_validation": False}
    )
    assert res_false is False
    assert "is_draft" in raison_false or "requires_human_validation" in raison_false


def test_valider_envoi_externe_valeurs_non_booleennes_refuse():
    # Cas limite : présence des clés mais avec des valeurs non booléennes (truthy/falsy ambiguës)
    # Traité comme absent/refusé par prudence
    res_str, raison_str = contrats.valider({"type": "sms", "is_draft": "true"})
    assert res_str is False
    assert "is_draft" in raison_str or "requires_human_validation" in raison_str

    res_int, raison_int = contrats.valider({"type": "telegram", "requires_human_validation": 1})
    assert res_int is False
    assert "is_draft" in raison_int or "requires_human_validation" in raison_int


def test_valider_action_non_dict_refuse():
    res, raison = contrats.valider("pas un dict")
    assert res is False
    assert "dictionnaire" in raison
