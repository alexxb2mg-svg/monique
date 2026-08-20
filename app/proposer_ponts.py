"""Module pour générer une proposition de revue humaine sous forme de fichier Markdown."""

from datetime import datetime
import os


def proposer_a_alex(resultat: dict, dossier: str) -> str:
    """Écrit un fichier Markdown résumant un résultat de construction pour revue humaine.

    Args:
        resultat: Dictionnaire contenant les informations de construction :
            - "brique" (str) : Nom de la brique
            - "ok" (bool) : Succès ou échec
            - "essais" (int) : Nombre d'essais
            - "dernier_test" (str) : Sortie du dernier test
            - "chemin_module" (str, optionnel) : Chemin vers le module
            - "chemin_test" (str, optionnel) : Chemin vers le fichier de test
        dossier: Répertoire dans lequel enregistrer le fichier Markdown.

    Returns:
        Le chemin complet du fichier Markdown créé.
    """
    os.makedirs(dossier, exist_ok=True)

    brique = resultat.get("brique", "inconnue")
    ok = resultat.get("ok", False)
    essais = resultat.get("essais", 0)
    dernier_test = resultat.get("dernier_test", "")
    chemin_module = resultat.get("chemin_module")
    chemin_test = resultat.get("chemin_test")

    statut_str = "succes" if ok else "echec"
    maintenant = datetime.now()
    horodatage_nom = maintenant.strftime("%Y%Y%m%d_%H%M%S")
    horodatage_lisible = maintenant.strftime("%Y-%m-%d %H:%M:%S")

    # Nettoyage du nom de brique pour le nom de fichier
    brique_slug = "".join(
        c if c.isalnum() or c in ("-", "_") else "_" for c in brique
    )
    nom_fichier = f"revue_{horodatage_nom}_{brique_slug}_{statut_str}.md"
    chemin_complet = os.path.abspath(os.path.join(dossier, nom_fichier))

    statut_affiche = "SUCCÈS" if ok else "ÉCHEC"

    lignes = [
        f"# Rapport de Revue Humaine - {brique}",
        "",
        f"- **Horodatage** : {horodatage_lisible}",
        f"- **Nom de la brique** : `{brique}`",
        f"- **Statut** : {statut_affiche}",
        f"- **Nombre d'essais** : {essais}",
    ]

    if chemin_module:
        lignes.append(f"- **Chemin du module** : `{chemin_module}`")

    if chemin_test:
        lignes.append(f"- **Chemin du test** : `{chemin_test}`")

    lignes.extend(
        [
            "",
            "## Sortie du dernier test",
            "",
            "```",
            str(dernier_test),
            "```",
            "",
        ]
    )

    contenu = "\n".join(lignes)

    with open(chemin_complet, "w", encoding="utf-8") as f:
        f.write(contenu)

    return chemin_complet
