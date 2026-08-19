"""Source de vérité unique de la nav à 3 niveaux (département -> persona -> onglets).

Ce module EST la source de vérité, déjà branchée : app/serveur.py::racine()
lit DEPARTEMENTS ici et le passe au contexte, et app/templates/coquille.html
n'a plus aucun bloc `{% set arbre = [...] %}` codé en dur — il rend
`departements` reçu du contexte. Ce n'est plus un scaffold en attente.

"La brigade" (/vue/agents) est un département à part entière dans
coquille.html — un seul groupe, une seule persona, un seul onglet — pas une
page transverse exclue de DEPARTEMENTS.
"""

from typing import TypedDict


class Onglet(TypedDict):
    route: str
    label: str


class Persona(TypedDict):
    nom: str
    avatar: str
    onglets: list[Onglet]


class Departement(TypedDict):
    slug: str
    nom: str
    couleur: str
    personas: list[Persona]


DEPARTEMENTS: list[Departement] = [
    {
        "slug": "direction",
        "nom": "Direction",
        "couleur": "#7a4f86",
        "personas": [
            {
                "nom": "Beecham",
                "avatar": "orchestrateur.jpg",
                "onglets": [
                    {"route": "/vue/beecham", "label": "Beecham"},
                ],
            },
        ],
    },
    {
        "slug": "secretariat",
        "nom": "Secrétariat",
        "couleur": "#c56a3a",
        "personas": [
            {
                "nom": "Secrétaire",
                "avatar": "secretaire.png",
                "onglets": [
                    {"route": "/vue/jour", "label": "Aujourd'hui"},
                    {"route": "/vue/boite", "label": "La boîte"},
                ],
            },
            {
                "nom": "Maître d'œuvre",
                "avatar": "maitre_oeuvre.jpg",
                "onglets": [
                    {"route": "/vue/faire", "label": "À faire"},
                ],
            },
        ],
    },
    {
        "slug": "comptabilite",
        "nom": "Comptabilité",
        "couleur": "#1f8a4c",
        "personas": [
            {
                "nom": "Comptable",
                "avatar": "comptable.jpg",
                "onglets": [
                    {"route": "/vue/relances", "label": "Relances & factures"},
                ],
            },
        ],
    },
    {
        "slug": "informatique",
        "nom": "Informatique",
        "couleur": "#3f6d8a",
        "personas": [
            {
                "nom": "Développeur",
                "avatar": "developpeur.jpg",
                "onglets": [
                    {"route": "/vue/reglages", "label": "Réglages"},
                ],
            },
            {
                "nom": "Documentaliste",
                "avatar": "documentaliste.jpg",
                "onglets": [
                    {"route": "/vue/fournisseurs", "label": "Fournisseurs modèles IA"},
                ],
            },
        ],
    },
    {
        "slug": "approvisionnement",
        "nom": "Approvisionnement",
        "couleur": "#d2691e",
        "personas": [
            {
                "nom": "Approvisionnement",
                "avatar": "fournisseurs_materiel.jpg",
                "onglets": [
                    {"route": "/vue/fournisseurs-materiel", "label": "Fournisseurs matériel"},
                ],
            },
        ],
    },
    {
        "slug": "pilotage",
        "nom": "Pilotage",
        "couleur": "#b3803a",
        "personas": [
            {
                "nom": "Technicien",
                "avatar": "technicien.jpg",
                "onglets": [
                    {"route": "/vue/planif", "label": "Planificateur"},
                ],
            },
        ],
    },
    {
        "slug": "infra_surveillance_systeme",
        "nom": "Infra & Surveillance Système",
        "couleur": "#557089",
        "personas": [
            {
                "nom": "Veilleur",
                "avatar": "veilleur.jpg",
                "onglets": [
                    {"route": "/vue/monitoring", "label": "Monitoring"},
                    {"route": "/vue/processus", "label": "Système"},
                    {"route": "/vue/usage", "label": "Coût"},
                    {"route": "/vue/missions-actives", "label": "Missions actives"},
                ],
            },
        ],
    },
    {
        "slug": "recherche_veille",
        "nom": "Recherche / Veille",
        "couleur": "#2c8a8a",
        "personas": [
            {
                "nom": "Chercheur",
                "avatar": "chercheur.jpg",
                "onglets": [
                    {"route": "/vue/recherche", "label": "Recherche"},
                ],
            },
        ],
    },
    {
        "slug": "qualite",
        "nom": "Qualité",
        "couleur": "#8a3f6e",
        "personas": [
            {
                "nom": "Vision",
                "avatar": "vision.jpg",
                "onglets": [
                    {"route": "/vue/qualite", "label": "Qualité"},
                ],
            },
        ],
    },
    {
        "slug": "interface",
        "nom": "Interface",
        "couleur": "#7a8a3f",
        "personas": [
            {
                "nom": "Vitrine",
                "avatar": "vitrine.jpg",
                "onglets": [
                    {"route": "/vue/interface", "label": "Interface"},
                ],
            },
        ],
    },
    {
        "slug": "la_brigade",
        "nom": "La brigade",
        "couleur": "#9a5b3f",
        "personas": [
            {
                "nom": "La brigade",
                "avatar": "orchestrateur.jpg",
                "onglets": [
                    {"route": "/vue/agents", "label": "Agents"},
                ],
            },
        ],
    },
]
