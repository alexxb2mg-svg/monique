"""Extracteur de code NATIF (lecture PASSIVE du DOM d'un pont, via CDP) : récupère le code source
propre des blocs `pre` du DERNIER message assistant, sans le chrome du composant (label langage,
boutons Copier/Télécharger) et sans les déformations du markdown aplati. Aucune frappe, aucun clic,
aucun signal réseau vers le fournisseur → zéro motif de détection ajouté.

Appelé en sous-processus par ponts.extraire_code() (Python 3.14, l'env où Playwright est installé).
Sortie stdout : les blocs de code concaténés (séparés par une ligne vide). Codes : 0 OK, 2 cdp_down,
4 page/playwright absente."""
from __future__ import annotations

import argparse
import sys

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--message-sel", required=True, help="Sélecteur du conteneur de message assistant")
    ap.add_argument("--host-hint", default="", help="Fragment d'URL pour retrouver la bonne page")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERR] playwright non installe pour cet interpreteur.", file=sys.stderr)
        return 4

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{args.port}")
        except Exception as e:
            print(f"[ERR] cdp_down : {e}", file=sys.stderr)
            return 2
        ctx = browser.contexts[0]
        page = next(
            (pg for pg in ctx.pages if args.host_hint in (pg.url or "")),
            ctx.pages[0] if ctx.pages else None,
        )
        if page is None:
            print("[ERR] aucune page trouvee.", file=sys.stderr)
            return 4
        dernier = page.locator(args.message_sel).last
        blocs = dernier.locator("pre")  # les <pre> portent le code source propre (sans header)
        n = blocs.count()
        codes = [blocs.nth(i).inner_text().strip() for i in range(n)]
        print("\n\n".join(c for c in codes if c))
        return 0


if __name__ == "__main__":
    sys.exit(main())
