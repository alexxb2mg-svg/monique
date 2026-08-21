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


def test_coherence_financiere_ok():
    assert contrats.valider({"total_ht": 100.0, "taux_tva": 0.2, "total_ttc": 120.0}) == (True, "")


def test_coherence_financiere_tolerance_arrondi_ok():
    # écart d'arrondi réel (flottant), doit passer sous la tolérance de 0.01
    assert contrats.valider({"total_ht": 33.33, "taux_tva": 0.2, "total_ttc": 39.996})[0] is True


def test_coherence_financiere_ecart_reel_refuse():
    res, raison = contrats.valider({"total_ht": 100.0, "taux_tva": 0.2, "total_ttc": 150.0})
    assert res is False
    assert "Incohérence financière" in raison


def test_coherence_financiere_champs_absents_ignore_le_controle():
    # ni verrou d'envoi ni cle financiere -> passe (rien a valider sous cet angle)
    assert contrats.valider({"total_ht": 100.0}) == (True, "")


def test_coherence_financiere_bool_ne_compte_pas_comme_numerique():
    # piege Python : isinstance(True, int) est True -- ne doit pas etre traite comme un nombre
    assert contrats.valider({"total_ht": True, "taux_tva": 0.2, "total_ttc": 1.2}) == (True, "")


def test_coherence_financiere_et_verrou_envoi_combines():
    # un devis envoye par email : verrou d'envoi respecte (is_draft=True), mais chiffres faux
    # -> doit quand meme etre refuse, sur le controle financier cette fois
    res, raison = contrats.valider(
        {"type": "email", "is_draft": True, "total_ht": 100.0, "taux_tva": 0.2, "total_ttc": 150.0}
    )
    assert res is False
    assert "Incohérence financière" in raison


def test_verrou_envoi_verifie_avant_coherence_financiere():
    # sans verrou d'envoi ET avec des chiffres faux : le verrou d'envoi doit bloquer en premier
    res, raison = contrats.valider(
        {"type": "email", "total_ht": 100.0, "taux_tva": 0.2, "total_ttc": 150.0}
    )
    assert res is False
    assert "envoi externe" in raison
