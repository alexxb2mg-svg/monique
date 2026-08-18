# Monique

**Une coquille agentique locale et supervisée : des agents IA au-dessus de vos propres
données, qui lisent le vrai et n'écrivent que du bac à sable tant que vous n'avez pas basculé.**

Monique est un harnais léger (FastAPI + HTMX, aucun build) pour faire tourner des agents IA
sur les données d'une petite structure, avec quatre garanties de conception :

1. **Isolation par conception** — Monique *lit le store réel en lecture seule* et *écrit tout
   dans un bac à sable*. Un seul interrupteur (`SECRETAIRE_MODE=prod`) bascule les écritures
   vers le réel, le jour où vous le décidez. C'est le cœur.
2. **Cerveau confiné et interchangeable** — le LLM est appelé **sans aucun outil** (il ne
   *peut pas* envoyer, écrire ni supprimer de lui-même). Claude via `claude -p` aujourd'hui,
   une autre API demain (transport interchangeable, clés au coffre).
3. **Un orchestrateur** — il aiguille chaque demande vers le bon agent-persona (déterministe
   par provenance → classifieur LLM contraint → défaut sûr), suggère de nouveaux agents quand
   un motif revient, et délègue des sous-tâches sans risque.
4. **Humain dans la boucle** — *rien ne part sans votre clic*. Le premier module est une
   **secrétaire** : tri des messages entrants, brouillons de réponse proposés, relances,
   rappels, monitoring.

> Ce que Monique n'est **pas** : ni un chatbot, ni un système autonome qui agit seul, ni
> verrouillé à un fournisseur. Par défaut, elle tourne en `MODE=test` et ne touche rien.

## Démarrer

```bash
pip install -r app/requirements.txt
cp .env.example .env          # (optionnel) ajustez les chemins ; sinon défauts sûrs
cd app && python -m pytest -q # 106 tests
python -m uvicorn serveur:app --host 127.0.0.1 --port 8770
```

Ouvrez `http://127.0.0.1:8770`. En `MODE=test`, Monique écrit dans un bac à sable
(`monique_shadow.db`) et n'envoie rien.

## Onglets

Secrétariat — **Aujourd'hui · La boîte · À faire · Relances · Monitoring** ·
Services — **Réglages · Planificateur · Fournisseurs & Clés** · **Agents** (la brigade).

## Configuration

Tout se règle par variables d'environnement, avec des défauts sûrs — voir `.env.example`.
Aucun chemin de poste n'est codé en dur : chaque installation pointe le sien.

## Sécurité

Voir [`SECURITY.md`](SECURITY.md). En bref : les secrets vont dans un **coffre hors du
dépôt** (jamais dans le code ni un log), le LLM tourne **sans outils**, et le dépôt est
protégé par `gitleaks` + deux contrôles maison (identités, chemins de poste) en pré-commit
et en CI.

## Licence

MIT — voir [`LICENSE`](LICENSE).
