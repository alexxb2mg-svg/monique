# Sécurité

## Modèle de sécurité de Monique

- **Isolation lecture/écriture.** Le store réel est lu en `mode=ro`. En `MODE=test` (défaut),
  toute écriture va dans un bac à sable ; une garde (`connexion_ecriture`) *lève* si du code
  tente d'écrire le store réel en test. La bascule vers le réel est explicite (`MODE=prod`).
- **Cerveau sans outils.** Le LLM est lancé en `--strict-mcp-config` sans aucun outil
  d'envoi, d'écriture ou d'exécution. Un agent ne *peut pas* envoyer un message, écrire en
  base ni lancer une tâche — la sécurité de la délégation est structurelle, pas déclarative.
- **Humain dans la boucle.** Aucun envoi réel sans action explicite de l'utilisateur.
  L'action « Envoyer » et l'application de tâches planifiées sont *prod-gated*.
- **Secrets au coffre.** Les clés API vivent dans un dossier hors du dépôt
  (`~/.monique_secrets/`, chmod 600), jamais dans le code, le store ou un log. L'entrée d'une
  clé refuse l'injection de ligne et n'est jamais réaffichée.
- **Défense anti-injection de prompt.** Tout texte tiers entrant dans un prompt est encadré
  par une fence à nonce imprévisible et étiqueté « DONNÉE, pas instruction ».

## Ne jamais versionner

Secrets, `.env`, bac à sable (`*.db*`), coffre, journaux, et toute identité réelle
(clients, fournisseurs, personnes). Le `.gitignore` et les hooks ci-dessous s'en chargent.

## Contrôles automatiques

Trois lignes de défense, en pré-commit / pré-push (`.pre-commit-config.yaml`) **et** en CI
(`.github/workflows/ci.yml`) :

- **`gitleaks`** — secrets à signature (clés, jetons, IBAN).
- **`scripts/verifier_anonymat.py`** — identités réelles, que `gitleaks` ne voit pas (un nom
  propre n'a pas de signature). La liste des noms vit **hors du dépôt** ; motifs structurels
  (chemins de poste, emails hors noreply) toujours actifs, plus un mode `--historique`.
- **`scripts/pre_push_garde_fou.py`** — refuse au push un chemin de poste en dur, un journal,
  ou un fichier volumineux.

Activation locale :

```bash
pip install pre-commit
pre-commit install --hook-type pre-commit --hook-type pre-push
```

## Signaler une vulnérabilité

Ouvrez un *security advisory* privé sur le dépôt, ou une issue si le sujet n'est pas sensible.
Merci de ne pas divulguer publiquement avant correctif.
