"""Source de vérité unique de la nav à 2 niveaux (département -> onglets).

Scaffold pur : ce module ne dépend ni de serveur.py ni d'aucun template.
Il n'est pas encore branché à une route ni à app/templates/coquille.html —
ça viendra dans une mission future séparée (cf. plan.md, Informatique).

Recopié tel quel depuis la structure réelle de app/templates/coquille.html
(balise <nav class="onglets" id="onglets">) au moment de l'écriture de ce
fichier. En cas de divergence future avec le template, ce fichier doit
suivre coquille.html, pas l'inverse.

"La brigade" (/vue/agents) est une page transverse, pas un département —
elle n'apparaît pas dans DEPARTEMENTS.
"""

from typing import TypedDict


class Onglet(TypedDict):
    route: str
    label: str
    avatar: str
    agent: str


class Departement(TypedDict):
    slug: str
    nom: str
    onglets: list[Onglet]


DEPARTEMENTS: list[Departement] = [
    {
        "slug": "direction",
        "nom": "Direction",
        "onglets": [
            {
                "route": "/vue/beecham",
                "label": "Beecham",
                "avatar": "orchestrateur.jpg",
                "agent": "Beecham",
            },
        ],
    },
    {
        "slug": "secretariat",
        "nom": "Secrétariat",
        "onglets": [
            {
                "route": "/vue/jour",
                "label": "Aujourd'hui",
                "avatar": "secretaire.png",
                "agent": "Secrétaire",
            },
            {
                "route": "/vue/boite",
                "label": "La boîte",
                "avatar": "secretaire.png",
                "agent": "Secrétaire",
            },
            {
                "route": "/vue/faire",
                "label": "À faire",
                "avatar": "maitre_oeuvre.jpg",
                "agent": "Maître d'œuvre",
            },
        ],
    },
    {
        "slug": "comptabilite",
        "nom": "Comptabilité",
        "onglets": [
            {
                "route": "/vue/relances",
                "label": "Relances",
                "avatar": "comptable.jpg",
                "agent": "Comptable",
            },
        ],
    },
    {
        "slug": "informatique",
        "nom": "Informatique",
        "onglets": [
            {
                "route": "/vue/monitoring",
                "label": "Monitoring",
                "avatar": "veilleur.jpg",
                "agent": "Veilleur",
            },
            {
                "route": "/vue/reglages",
                "label": "Réglages",
                "avatar": "developpeur.jpg",
                "agent": "Développeur",
            },
            {
                "route": "/vue/usage",
                "label": "Coût",
                "avatar": "veilleur.jpg",
                "agent": "Veilleur",
            },
            {
                "route": "/vue/fournisseurs",
                "label": "Fournisseurs",
                "avatar": "documentaliste.jpg",
                "agent": "Documentaliste",
            },
        ],
    },
    {
        "slug": "approvisionnement",
        "nom": "Approvisionnement",
        "onglets": [
            {
                "route": "/vue/fournisseurs-materiel",
                "label": "Fournisseurs matériel",
                "avatar": "technicien.jpg",
                "agent": "Approvisionnement",
            },
        ],
    },
    {
        "slug": "pilotage",
        "nom": "Pilotage",
        "onglets": [
            {
                "route": "/vue/planif",
                "label": "Planificateur",
                "avatar": "technicien.jpg",
                "agent": "Technicien",
            },
        ],
    },
    {
        "slug": "infra_surveillance_systeme",
        "nom": "Infra & Surveillance Système",
        "onglets": [
            {
                "route": "/vue/processus",
                "label": "Système",
                "avatar": "veilleur.jpg",
                "agent": "Veilleur",
            },
        ],
    },
    {
        "slug": "recherche_veille",
        "nom": "Recherche / Veille",
        "onglets": [
            {
                "route": "/vue/recherche",
                "label": "Recherche",
                "avatar": "chercheur.jpg",
                "agent": "Chercheur",
            },
        ],
    },
]
