"""Relie une actu (Signal) a des coins Solana et les classe.

Regle metier (Phase 1) : parmi les coins lies a l'actu, on privilegie
  - ceux crees par un dev CONNU (watchlist), et
  - le coin le PLUS VIEUX (premier sur le narratif = first mover).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from models import Coin, Signal
from solana.dexscreener import DexScreener
from solana.helius import Helius

log = logging.getLogger("solana.matcher")


class CoinMatcher:
    def __init__(
        self,
        dexscreener: DexScreener,
        helius: Helius,
        min_liquidity_usd: float = 2000.0,
        known_devs_file: str = "known_devs.json",
        enrich_top_n: int = 5,
    ) -> None:
        self.dex = dexscreener
        self.helius = helius
        self.min_liquidity_usd = min_liquidity_usd
        self.enrich_top_n = enrich_top_n
        self.known_wallets, self.known_handles = self._load_known(known_devs_file)

    @staticmethod
    def _load_known(path_str: str) -> tuple[dict[str, str], dict[str, str]]:
        path = Path(path_str)
        if not path.exists():
            return {}, {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            wallets = {k: v for k, v in (data.get("wallets") or {}).items()}
            handles = {k.lower().lstrip("@"): v for k, v in (data.get("handles") or {}).items()}
            return wallets, handles
        except Exception as exc:
            log.warning("Lecture de %s impossible: %s", path, exc)
            return {}, {}

    async def find(self, signal: Signal) -> list[Coin]:
        terms = self._search_terms(signal)
        seen: dict[str, Coin] = {}
        for term in terms:
            for coin in await self.dex.search(term):
                if not coin.mint or coin.mint in seen:
                    continue
                if coin.liquidity_usd < self.min_liquidity_usd:
                    continue
                seen[coin.mint] = coin

        candidates = list(seen.values())
        candidates.sort(key=self._age_key)  # plus vieux d'abord

        for coin in candidates[: self.enrich_top_n]:
            await self.helius.enrich(coin)
            self._flag_known_dev(coin)

        # Re-tri final : dev connu d'abord, puis le plus vieux.
        candidates.sort(key=lambda c: (not c.is_known_dev, self._age_key(c)))
        return candidates

    @staticmethod
    def _search_terms(signal: Signal) -> list[str]:
        terms: list[str] = []
        for t in signal.tickers:
            terms.append(t.lstrip("$"))
        terms.extend(signal.keywords)
        # dedup en conservant l'ordre
        out, seen = [], set()
        for t in terms:
            key = t.lower().strip()
            if key and key not in seen:
                seen.add(key)
                out.append(t.strip())
        return out

    @staticmethod
    def _age_key(coin: Coin) -> float:
        if coin.created_at is None:
            return float("inf")  # date inconnue -> tout en bas
        return coin.created_at.timestamp()

    def _flag_known_dev(self, coin: Coin) -> None:
        if coin.creator and coin.creator in self.known_wallets:
            coin.is_known_dev = True
            coin.known_dev_label = self.known_wallets[coin.creator]
