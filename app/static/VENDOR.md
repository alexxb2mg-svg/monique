# À déposer ici avant le premier lancement

- `htmx.min.js` — **HTMX 2.0.4** (fichier unique, ~48 Ko). À vendre localement
  (jamais depuis un CDN — CSP + règle supply-chain). Vérifier la taille/intégrité
  avant commit. Tant qu'il est absent, la coquille se charge mais la navigation
  par onglets ne recharge pas les fragments.
- (Optionnel) police **Archivo** en `.woff2` pour un rendu fidèle hors-ligne ;
  sinon la CSS retombe sur `Segoe UI`/system-ui.

Ces éléments sont volontairement absents à l'étape « pose de briques » (aucun
téléchargement lancé). Ils se déposent au moment de la bascule décidée.
