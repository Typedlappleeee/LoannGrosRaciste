"""Classificateur d'importance des actus via Claude.

Pour chaque signal (tweet/post), Claude juge s'il s'agit d'une actu virale
"tradeable" en memecoin, attribue un score 0-100, et extrait les mots-cles
et tickers candidats pour la recherche de coins.
"""
from __future__ import annotations

import json
import logging
import re

from anthropic import AsyncAnthropic

from models import Signal

log = logging.getLogger("analysis.llm")

_JSON_OBJ = re.compile(r"\{.*\}", re.DOTALL)

SYSTEM_PROMPT = """\
Tu es un analyste specialise dans le trading de memecoins sur Solana.
On te donne le texte d'un post (tweet, etc.). Determine si c'est une ACTUALITE \
susceptible de declencher un narratif memecoin a fort buzz.

Criteres d'une actu "tradeable" :
- evenement nouveau, surprenant, ou tres viral (celebrite, politique, tech, \
crypto, culture, meme, drame, annonce...) ;
- potentiel de propagation rapide sur X ;
- presence d'un mot/nom/concept "ticker-isable" (un nom propre, un meme, un slogan).

Ce qui N'EST PAS tradeable : spam, pub generique, contenu trop ancien, opinion \
banale sans evenement, threads techniques sans nouveaute.

Reponds UNIQUEMENT avec un objet JSON valide (aucun texte autour), avec ces cles :
- "important" (bool) : true seulement si ca vaut une alerte de trading ;
- "score" (entier 0-100) : intensite du buzz potentiel ;
- "reason" (string) : 1 phrase courte expliquant pourquoi ;
- "keywords" (liste de strings) : 1 a 5 termes de recherche pour trouver un coin \
lie (noms propres, memes, concepts) ;
- "tickers" (liste de strings) : symboles plausibles SANS le $ (ex: pour "Elon \
name his dog Floki" -> ["FLOKI"]). Liste vide si rien d'evident.

Exemple : {"important": true, "score": 82, "reason": "...", "keywords": ["..."], \
"tickers": ["..."]}
"""


class LLMAnalyzer:
    def __init__(self, api_key: str, model: str) -> None:
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def analyze(self, signal: Signal) -> bool:
        """Renseigne signal.buzz_score / reason / keywords / tickers.

        Retourne True si l'analyse a abouti, False en cas d'echec (l'appelant
        retombe alors sur l'heuristique).
        """
        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=400,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": signal.text[:4000]}],
            )
        except Exception as exc:
            log.warning("Analyse LLM impossible: %s", exc)
            return False

        text = next((b.text for b in resp.content if b.type == "text"), "")
        data = self._parse_json(text)
        if data is None:
            return False

        score = int(data.get("score", 0))
        if not data.get("important"):
            score = min(score, 40)  # non important -> sous le seuil habituel
        signal.buzz_score = max(0, min(100, score))
        signal.reason = data.get("reason", "")
        signal.keywords = [k for k in data.get("keywords", []) if k]
        signal.tickers = [t.lstrip("$") for t in data.get("tickers", []) if t]
        return True

    @staticmethod
    def _parse_json(text: str) -> dict | None:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = _JSON_OBJ.search(text)  # tolere un eventuel texte autour du JSON
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        return None
