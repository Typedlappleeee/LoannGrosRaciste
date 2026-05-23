# LoanGrosRaciste

Agent automatise de veille pour le trading de memecoins sur Solana.

**Pipeline (Phase 1)** : surveille X (Twitter) en continu → un classificateur Claude
juge si une actu est un buzz "tradeable" → recherche les coins Solana lies
(en priorisant le plus vieux / les devs connus) → ping un bot Discord.

> ⚠️ **Outil de recherche/veille personnel.** Le scraping de X est contre ses CGU ;
> utilise des comptes jetables. Aucune de ces données n'est un conseil financier.

## Architecture

```
sources/  -> collecte (X via twscrape, enfichable)
analysis/ -> scoring de buzz (Claude, sinon heuristique) + extraction tickers/keywords
solana/   -> DexScreener (recherche) + Helius (holders/supply/dev) + matcher
bot/      -> bot Discord + boucle de surveillance
store.py  -> deduplication (sqlite)
```

## Installation

```bash
pip install -r requirements.txt
cp .env.example .env          # puis remplis les valeurs
cp known_devs.example.json known_devs.json   # optionnel
```

### Ce qu'il faut fournir

| Variable | Obligatoire | Comment l'obtenir |
|----------|-------------|-------------------|
| `DISCORD_TOKEN` | oui | discord.com/developers → application → Bot → Reset Token. Active l'intent **MESSAGE CONTENT**. |
| `DISCORD_CHANNEL_ID` | oui | Mode dev Discord → clic droit sur le salon → Copier l'ID. |
| `accounts.txt` | oui (sinon X muet) | Comptes X **jetables**, format `user:pass:email:email_pass` (un par ligne). |
| `HELIUS_API_KEY` | non | dev.helius.xyz (free tier). Sans elle : pas d'analyse holders/dev. |
| `ANTHROPIC_API_KEY` | non (recommande) | Sans elle : scoring heuristique au lieu de l'IA. |

Le bot doit etre invite sur ton serveur avec les permissions *Send Messages* + *Embed Links*.

## Lancement

```bash
python main.py
```

Commandes Discord : `!status`, `!scan <mot-cle>` (recherche manuelle de coins).

## Limites connues / Phase 2

- Le scraping X depend de comptes valides ; ils peuvent etre bannis.
- L'analyse anti-rug / anti-bundle complete (wallets en commun, supply bundle)
  est prevue en Phase 2 ; la Phase 1 ne fait qu'un controle leger (top holders,
  mint authority).
