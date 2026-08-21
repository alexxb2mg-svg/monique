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


_ACTION_BASE = {"type": "email", "is_draft": True}


def test_vouvoiement_tutoiement_isole_refuse():
    for texte in [
        "Tu recevras le devis",
        "Ton chantier avance",
        "As-tu vu le document",
        "Je t'informe du retard",
        "C'est pour toi",
        "Voici tes documents",
        "Ta demande est prise en compte",
    ]:
        res, raison = contrats.valider({**_ACTION_BASE, "texte": texte})
        assert res is False, f"aurait du refuser : {texte!r}"
        assert "Tutoiement" in raison


def test_vouvoiement_faux_positifs_ne_sont_pas_bloques():
    for texte in [
        "Le statut de votre dossier a change",
        "Un tutoriel explicatif est joint",
        "Merci de votre vertu de patience",
        "La situation actuelle du chantier",
        "Vous recevrez le devis sous 48h",
        "Votre chantier avance bien",
    ]:
        assert contrats.valider({**_ACTION_BASE, "texte": texte}) == (
            True,
            "",
        ), f"n'aurait pas du refuser : {texte!r}"


def test_vouvoiement_ignore_hors_envoi_externe():
    # pas un envoi externe -> le controle vouvoiement ne s'applique pas
    assert contrats.valider({"type": "note_interne", "texte": "Tu dois vérifier ça"}) == (
        True,
        "",
    )


def test_iban_embarque_dans_du_texte_normal_refuse():
    # LE cas realiste : IBAN entoure de prose avec espaces -- bug reel trouve et corrige
    # (suppression globale des espaces cassait la frontiere \b sur ce cas precis)
    res, raison = contrats.valider(
        {"texte": "Voici mon IBAN FR7630006000011234567890189 merci"}
    )
    assert res is False
    assert "IBAN" in raison


def test_iban_seul_avec_espaces_internes_refuse():
    res, raison = contrats.valider({"texte": "FR76 3000 6000 0112 3456 7890 189"})
    assert res is False
    assert "IBAN" in raison


def test_iban_ne_fuite_jamais_dans_la_raison():
    res, raison = contrats.valider({"texte": "IBAN : FR7630006000011234567890189"})
    assert res is False
    assert "FR76" not in raison


def test_iban_controle_s_applique_meme_hors_envoi_externe():
    # meme un brouillon interne (pas de type d'envoi) ne doit jamais contenir d'IBAN en clair
    res, raison = contrats.valider(
        {"type": "note_interne", "texte": "IBAN client : FR7630006000011234567890189"}
    )
    assert res is False
    assert "IBAN" in raison


def test_iban_faux_positifs_metier_ne_sont_pas_bloques():
    for texte in [
        "Le devis D26050007 est prêt",
        "Référence produit NFT820 disponible",
        "Code postal 45400 Fleury-les-Aubrais",
        "Merci de votre confiance, cordialement",
    ]:
        assert contrats.valider({"texte": texte}) == (True, ""), f"faux positif sur : {texte!r}"
