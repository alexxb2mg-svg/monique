"""Module de parsing de rapport de sonde pour la vérification des sélecteurs."""


def interpreter_rapport(sortie: str) -> dict:
    """Parse un rapport texte et classe les sélecteurs selon leur présence.

    Args:
        sortie: Chaîne de caractères contenant une ligne par sélecteur
          au format "NOM=N".

    Returns:
        Un dictionnaire contenant deux listes dans l'ordre d'apparition:
        - "noms_ok": liste des noms dont N > 0
        - "noms_manquants": liste des noms dont N == 0
    """
    noms_ok = []
    noms_manquants = []

    if not sortie:
        return {"noms_ok": noms_ok, "noms_manquants": noms_manquants}

    for ligne in sortie.splitlines():
        ligne_nettoyee = ligne.strip()
        if not ligne_nettoyee or "=" not in ligne_nettoyee:
            continue

        # Séparation sur le premier symbole '=' uniquement
        parties = ligne_nettoyee.split("=", 1)
        nom = parties[0].strip()
        valeur_str = parties[1].strip()

        if not nom:
            continue

        try:
            valeur = int(valeur_str)
            if valeur < 0:
                continue
        except ValueError:
            continue

        if valeur > 0:
            noms_ok.append(nom)
        else:
            noms_manquants.append(nom)

    return {"noms_ok": noms_ok, "noms_manquants": noms_manquants}
