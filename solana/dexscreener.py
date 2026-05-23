"""Client DexScreener (gratuit, sans cle).

Sert a chercher les coins Solana correspondant a un mot-cle / ticker et a
recuperer liquidite, FDV, volume et date de creation du pair.
Docs: https://docs.dexscreener.com/api/reference
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from models import Coin

log = logging.getLogger("solana.dexscreener")

BASE = "https://api.dexscreener.com"


class DexScreener:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def search(self, query: str, limit: int = 30) -> list[Coin]:
        """Cherche des pairs Solana correspondant a la requete."""
        try:
            r = await self.client.get(
                f"{BASE}/latest/dex/search", params={"q": query}, timeout=15
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            log.warning("DexScreener search('%s') a echoue: %s", query, exc)
            return []

        coins: list[Coin] = []
        for pair in (data.get("pairs") or [])[:limit]:
            if pair.get("chainId") != "solana":
                continue
            coins.append(self._to_coin(pair))
        return coins

    @staticmethod
    def _to_coin(pair: dict) -> Coin:
        base = pair.get("baseToken", {}) or {}
        created_ms = pair.get("pairCreatedAt")
        created_at = (
            datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
            if created_ms
            else None
        )
        liq = (pair.get("liquidity") or {}).get("usd") or 0.0
        vol = (pair.get("volume") or {}).get("h24") or 0.0
        return Coin(
            mint=base.get("address", ""),
            name=base.get("name", ""),
            symbol=base.get("symbol", ""),
            dex_url=pair.get("url", ""),
            price_usd=float(pair.get("priceUsd") or 0),
            liquidity_usd=float(liq),
            fdv=float(pair.get("fdv") or 0),
            volume_24h=float(vol),
            created_at=created_at,
        )
