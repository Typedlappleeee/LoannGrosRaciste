# LoanGrosRaciste

Agent de veille pour le trading de memecoins Solana, **avec interface web**.

Surveille X (Twitter) en continu → un classificateur Claude juge si une actu est
un buzz "tradeable" → recherche les coins Solana liés (priorité au plus vieux /
aux devs connus) → affiche tout dans une interface, et peut pinger Discord.

> ⚠️ Outil de veille personnel. Le scraping de X est contre ses CGU (utilise des
> comptes jetables). Rien ici n'est un conseil financier.

## Lancer en 2 commandes

```bash
pip install -r requirements.txt
python main.py
```

Puis ouvre **http://127.0.0.1:8000** dans ton navigateur.

## Tout se passe dans l'interface

- **Réglages** : colle tes clés (Helius, Anthropic), tes comptes X, ton webhook
  Discord, règle les seuils. Clique *Enregistrer*.
- **Démarrer** (en haut) : lance l'agent. Le voyant passe au vert.
- **Flux** : les alertes arrivent en direct (score, actu, coins trouvés, liquidité,
  âge, dev connu, % top holders…), avec un panneau *Journaux*.
- **Recherche** : scan manuel d'un mot-clé / ticker — fonctionne **sans aucune clé**
  (test idéal pour vérifier que ça marche).

### Test rapide (zéro configuration)

1. `python main.py` → ouvre l'interface.
2. Onglet **Recherche** → tape `bonk` → tu vois des coins Solana réels.
   ✅ le pipeline fonctionne. Ensuite renseigne tes clés dans *Réglages*.

## Ce qu'il faut pour le mode complet

| Réglage | Pour quoi |
|---------|-----------|
| Comptes X jetables | Surveillance temps réel de X (sinon le flux reste vide). |
| Clé Anthropic | Analyse IA des actus (sinon : scoring heuristique). |
| Clé Helius | Enrichissement on-chain (dev, top holders, mint authority). |
| Webhook Discord | Recevoir aussi les alertes sur Discord (optionnel). |

## Architecture

```
webapp/    interface web (FastAPI + page statique)
engine.py  moteur de surveillance (boucle collecte -> analyse -> coins -> alerte)
sources/   collecte X (twscrape), enfichable
analysis/  scoring buzz (Claude ou heuristique) + extraction tickers/keywords
solana/    DexScreener + Helius + matcher (plus vieux / dev connu)
outputs.py webhook Discord
settings.py / store.py  config + persistance (sqlite)
```

## Phase 2 (à venir)

Analyse anti-rug / anti-bundle approfondie : wallets en commun, supply bundle,
multi-trackers. La Phase 1 ne fait qu'un contrôle léger (top holders, mint authority).
