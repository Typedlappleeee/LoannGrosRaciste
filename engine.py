"""Moteur de surveillance, independant de toute interface.

Tourne dans la loop asyncio de l'app web. Construit les composants a partir
des Settings, boucle sur les sources, analyse, cherche les coins, et pousse
chaque Alert via le callback `on_alert`.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path

import httpx

from analysis import Analyzer, LLMAnalyzer
from models import Alert, Coin, Signal
from settings import Settings
from solana import CoinMatcher, DexScreener, Helius
from sources import XSource
from store import SeenStore

log = logging.getLogger("engine")

AlertCallback = Callable[[Alert], Awaitable[None]]


class AgentEngine:
    def __init__(self, store: SeenStore, on_alert: AlertCallback) -> None:
        self.store = store
        self.on_alert = on_alert
        self._task: asyncio.Task | None = None
        self._http: httpx.AsyncClient | None = None
        self._matcher: CoinMatcher | None = None
        self._analyzer: Analyzer | None = None
        self._sources: list = []
        self.settings: Settings | None = None
        self.running = False
        self.last_error = ""
        self.source_status = "arretee"
        self.signals_seen = 0
        self.alerts_count = 0

    # ----- cycle de vie -----------------------------------------------------
    async def start(self, settings: Settings) -> None:
        if self.running:
            return
        self.settings = settings
        self.last_error = ""
        self._http = httpx.AsyncClient(headers={"User-Agent": "LoanGrosRaciste/1.0"})

        dex = DexScreener(self._http)
        helius = Helius(self._http, settings.helius_api_key)
        self._matcher = CoinMatcher(
            dex, helius,
            min_liquidity_usd=settings.min_liquidity_usd,
            known_wallets=settings.known_wallets(),
            known_handles=settings.known_handles(),
        )

        llm = (
            LLMAnalyzer(settings.anthropic_api_key, settings.anthropic_model)
            if settings.anthropic_api_key
            else None
        )
        self._analyzer = Analyzer(llm)
        log.info("Analyse: %s", "Claude (%s)" % settings.anthropic_model if llm else "heuristique")

        # ecrit les comptes X depuis les reglages, puis prepare la source
        if settings.x_accounts.strip():
            Path("accounts.txt").write_text(settings.x_accounts.strip() + "\n", encoding="utf-8")
        x = XSource("accounts.txt", settings.x_queries)
        try:
            await x.setup()
            self.source_status = "active"
        except Exception as exc:
            self.source_status = f"erreur: {exc}"
            log.warning("Setup source X: %s", exc)
        self._sources = [x]

        self.running = True
        self._task = asyncio.create_task(self._loop())
        log.info("Moteur demarre (intervalle %ss).", settings.poll_interval)

    async def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._http:
            await self._http.aclose()
            self._http = None
        self.source_status = "arretee"
        log.info("Moteur arrete.")

    def status(self) -> dict:
        return {
            "running": self.running,
            "source_status": self.source_status,
            "signals_seen": self.signals_seen,
            "alerts_count": self.alerts_count,
            "last_error": self.last_error,
            "analysis": (
                f"Claude ({self.settings.anthropic_model})"
                if self.settings and self.settings.anthropic_api_key
                else "heuristique"
            ),
        }

    # ----- boucle -----------------------------------------------------------
    async def _loop(self) -> None:
        interval = self.settings.poll_interval if self.settings else 30
        while self.running:
            for source in self._sources:
                try:
                    async for signal in source.fetch():
                        await self._process(signal, source.name)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.last_error = str(exc)
                    log.exception("Erreur source %s", source.name)
            await asyncio.sleep(interval)

    async def _process(self, signal: Signal, source_name: str) -> None:
        if not self.store.is_new("signal", f"{source_name}:{signal.raw_id}"):
            return
        self.signals_seen += 1
        await self._analyzer.analyze(signal)
        if signal.buzz_score < self.settings.min_buzz_score:
            return
        coins = await self._matcher.find(signal)
        fresh = [c for c in coins if self.store.is_new("coin", c.mint)]
        alert = Alert(signal=signal, coins=fresh[:5])
        self.alerts_count += 1
        await self.on_alert(alert)

    # ----- scan manuel ------------------------------------------------------
    async def scan(self, query: str, settings: Settings) -> list[Coin]:
        """Recherche ponctuelle, fonctionne meme moteur arrete."""
        own_http = self._http is None
        http = self._http or httpx.AsyncClient(headers={"User-Agent": "LoanGrosRaciste/1.0"})
        try:
            dex = DexScreener(http)
            helius = Helius(http, settings.helius_api_key)
            matcher = CoinMatcher(
                dex, helius,
                min_liquidity_usd=settings.min_liquidity_usd,
                known_wallets=settings.known_wallets(),
                known_handles=settings.known_handles(),
            )
            signal = Signal(
                source="manual", raw_id=f"manual:{query}", text=query,
                author="manual", url="",
                created_at=datetime.now(timezone.utc),
                keywords=[query],
            )
            return await matcher.find(signal)
        finally:
            if own_http:
                await http.aclose()
