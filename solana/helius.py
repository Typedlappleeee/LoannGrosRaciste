"""Client Helius (RPC Solana + DAS).

Phase 1 : enrichissement leger d'un coin -> autorite de mint/freeze,
deployeur (creator) et concentration des plus gros holders.
L'analyse anti-rug / anti-bundle complete est prevue en Phase 2.
"""
from __future__ import annotations

import logging

import httpx

from models import Coin

log = logging.getLogger("solana.helius")


class Helius:
    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        self.client = client
        self.api_key = api_key
        self.enabled = bool(api_key)
        self.url = f"https://mainnet.helius-rpc.com/?api-key={api_key}"

    async def _rpc(self, method: str, params) -> dict | None:
        try:
            r = await self.client.post(
                self.url,
                json={"jsonrpc": "2.0", "id": "1", "method": method, "params": params},
                timeout=15,
            )
            r.raise_for_status()
            return r.json().get("result")
        except Exception as exc:
            log.warning("Helius %s a echoue: %s", method, exc)
            return None

    async def enrich(self, coin: Coin) -> Coin:
        """Complete les champs on-chain d'un coin (best-effort)."""
        if not self.enabled or not coin.mint:
            return coin
        await self._fill_authorities(coin)
        await self._fill_creator(coin)
        await self._fill_holder_concentration(coin)
        return coin

    async def _fill_authorities(self, coin: Coin) -> None:
        res = await self._rpc(
            "getAccountInfo", [coin.mint, {"encoding": "jsonParsed"}]
        )
        info = (((res or {}).get("value") or {}).get("data") or {}).get("parsed", {})
        mint_info = info.get("info", {}) if info.get("type") == "mint" else {}
        coin.mint_authority = mint_info.get("mintAuthority")
        coin.freeze_authority = mint_info.get("freezeAuthority")

    async def _fill_creator(self, coin: Coin) -> None:
        res = await self._rpc("getAsset", {"id": coin.mint})
        if not res:
            return
        creators = res.get("creators") or []
        if creators:
            coin.creator = creators[0].get("address", "")
        elif res.get("authorities"):
            coin.creator = res["authorities"][0].get("address", "")

    async def _fill_holder_concentration(self, coin: Coin) -> None:
        res = await self._rpc("getTokenLargestAccounts", [coin.mint])
        values = (res or {}).get("value") or []
        if not values:
            return
        supply_res = await self._rpc("getTokenSupply", [coin.mint])
        total = float((((supply_res or {}).get("value") or {}).get("uiAmount")) or 0)
        if total <= 0:
            return
        top10 = sum(float(v.get("uiAmount") or 0) for v in values[:10])
        coin.top10_holder_pct = round(100 * top10 / total, 2)
