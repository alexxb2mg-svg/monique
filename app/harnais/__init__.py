"""Harnais modulaire de Beecham.

Un PIPELINE est une donnée (liste d'étapes nommées), pas du code figé. Le MOTEUR
(`moteur.executer_pipeline`) exécute une liste d'étapes sur un contexte partagé ; chaque
ÉTAPE est une BRIQUE à contrat uniforme `(ctx) -> Decision`. On assemble les briques
différemment selon la mission — c'est ce qui rend le harnais reconfigurable sans le réécrire.

Répartition (décision Alex 21:39) : Alex donne les grandes orientations (pipelines-types),
Beecham les met en place et choisit/adapte le pipeline d'une mission intelligemment.
"""
