"""Source de vérité unique de la nav à 3 niveaux (département -> persona -> onglets).

Scaffold pur : ce module ne dépend ni de serveur.py ni d'aucun template.
Il n'est pas encore branché à une route ni à app/templates/coquille.html —
ça viendra dans une mission future séparée (cf. plan.md, Informatique).

Recopié tel quel depuis la structure réelle de app/templates/coquille.html
(bloc `{% set arbre = [...] %}` du panneau départements slide-in) au moment
de l'écriture de ce fichier. En cas de divergence future avec le template,
ce fichier doit suivre coquille.html, pas l'inverse.

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
                    {"route": "/vue/relances", "label": "Relances"},
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
