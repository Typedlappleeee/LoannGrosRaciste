"""Scoring de buzz et extraction de termes.

Deux modes :
- si un LLMAnalyzer est fourni, on l'utilise pour juger l'importance ;
- sinon, heuristique simple basee sur l'engagement et les motifs du texte.
"""
from __future__ import annotations

import logging
import re

from analysis.llm import LLMAnalyzer
from models import Signal

log = logging.getLogger("analysis.buzz")

_CASHTAG = re.compile(r"\$([A-Za-z]{2,10})\b")
_HASHTAG = re.compile(r"#(\w{2,30})")
# Suites de mots capitalises (noms propres / memes), ex: "Donald Trump", "Pepe"
_PROPER = re.compile(r"\b([A-Z][a-zA-Z0-9]{2,}(?:\s+[A-Z][a-zA-Z0-9]{2,}){0,2})\b")


def extract_tickers(text: str) -> list[str]:
    return _dedup(m.group(1).upper() for m in _CASHTAG.finditer(text))


def extract_keywords(text: str) -> list[str]:
    tags = [m.group(1) for m in _HASHTAG.finditer(text)]
    propers = [m.group(1) for m in _PROPER.finditer(text)]
    return _dedup(tags + propers)[:5]


def _dedup(items) -> list[str]:
    out, seen = [], set()
    for it in items:
        key = it.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(it.strip())
    return out


def heuristic_score(signal: Signal) -> int:
    """Score grossier 0-100 a partir de l'engagement et de la fraicheur."""
    eng = signal.engagement
    # engagement -> 0..70 (echelle log approximative)
    if eng >= 5000:
        base = 70
    elif eng >= 1000:
        base = 55
    elif eng >= 200:
        base = 40
    elif eng >= 50:
        base = 25
    else:
        base = 10
    # fraicheur : un post de moins de 10 min vaut plus
    if signal.age_seconds() < 600:
        base += 15
    # presence d'un cashtag = signal fort
    if _CASHTAG.search(signal.text):
        base += 10
    return max(0, min(100, base))


class Analyzer:
    def __init__(self, llm: LLMAnalyzer | None = None) -> None:
        self.llm = llm

    async def analyze(self, signal: Signal) -> None:
        used_llm = False
        if self.llm is not None:
            used_llm = await self.llm.analyze(signal)
        if not used_llm:
            signal.buzz_score = heuristic_score(signal)
            signal.tickers = extract_tickers(signal.text)
            signal.keywords = extract_keywords(signal.text)
            signal.reason = f"heuristique (engagement={signal.engagement})"
        else:
            # complete avec les cashtags du texte que le LLM aurait rates
            for t in extract_tickers(signal.text):
                if t not in signal.tickers:
                    signal.tickers.append(t)
