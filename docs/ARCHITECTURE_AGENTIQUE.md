# Architecture agentique — ce que la brigade doit savoir

Rappel bref du terrain, pour que Beecham et chaque agent sachent où ils mettent les pieds.
Court volontairement : le détail se lit dans le code, ceci est la carte.

## Le harnais — comment le travail est encadré
- Chaque mission tourne dans un **worktree git jetable** : une copie isolée du dépôt. On y écrit
  sans jamais toucher la production.
- L'agent codeur n'a **pas de shell** (pas de Bash) : il lit et édite du code, rien d'autre. Le
  harnais — déterministe, pas l'agent — lance les **tests + le diff** après lui.
- **Rien n'est fusionné sans validation humaine.** Beecham propose, Alex tranche. La branche reste
  **locale** tant qu'elle n'est pas validée.
- Un **garde-fou d'écriture** (hook, hors dépôt) refuse toute écriture hors du worktree et de
  l'atelier. La production se **lit** (inspiration), ne s'écrit **jamais**. Règle inviolable.

## Les contextes — ce que chaque agent voit
- Chaque agent reçoit un **rôle** (system prompt, `agents/<nom>/ROLE.md`) + une **consigne** (la
  mission). Il ne voit que son périmètre.
- Le cerveau LLM tourne **sans outils** (texte seul) : un message piégé ne peut rien déclencher.
- Le contexte est limité : aller à l'essentiel, ne pas recharger ce qui est déjà établi.

## La mémoire d'agent
- Ce qui doit survivre à une mission se **grave dans l'atelier**, pas dans une tête volatile.
- Bonne mémoire = **une info = une note**, datée, retrouvable. On **relit avant d'agir**.

## Le journal
- Chaque mission laisse une **trace append-only** : qui a fait quoi, quand, avec quel résultat.
- Le journal est la vérité chaude : on ne devine pas ce qui s'est passé, on le **lit**.

## La communication entre agents
- L'**atelier** est le tableau blanc partagé : notes, plans, messages, trouvailles. C'est là qu'on
  se parle. Un message clair et **adressé** vaut mieux que supposer que l'autre « sait ».

## Faire grandir l'organisation
- Beecham peut **proposer de nouveaux agents** (nommés dans l'esprit de la brigade), rattachés à un
  département existant ou à un nouveau département.
- Un agent = **un rôle clair, un périmètre, un mandat d'une ligne**. On n'en crée pas sans besoin
  démontré ni validation d'Alex.
