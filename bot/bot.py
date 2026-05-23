"""Bot Discord : orchestre collecte -> analyse -> recherche de coins -> alerte.

La boucle de surveillance tourne dans la loop asyncio du bot (discord.ext.tasks),
ce qui evite tout probleme de threads/event-loops multiples.
"""
from __future__ import annotations

import logging

import discord
import httpx
from discord.ext import commands, tasks

from analysis import Analyzer, LLMAnalyzer
from config import Config
from models import Alert, Coin, Signal
from solana import DexScreener, Helius, CoinMatcher
from sources import XSource
from store import SeenStore

log = logging.getLogger("bot")


class MemeBot(commands.Bot):
    def __init__(self, cfg: Config, store: SeenStore) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.cfg = cfg
        self.store = store
        self.http_client: httpx.AsyncClient | None = None
        self.sources: list = []
        self.matcher: CoinMatcher | None = None
        self.analyzer: Analyzer | None = None
        self._register_commands()

    async def setup_hook(self) -> None:
        self.http_client = httpx.AsyncClient(headers={"User-Agent": "LoanGrosRaciste/1.0"})

        dex = DexScreener(self.http_client)
        helius = Helius(self.http_client, self.cfg.helius_api_key)
        self.matcher = CoinMatcher(
            dex, helius,
            min_liquidity_usd=self.cfg.min_liquidity_usd,
            known_devs_file=self.cfg.known_devs_file,
        )

        llm = (
            LLMAnalyzer(self.cfg.anthropic_api_key, self.cfg.anthropic_model)
            if self.cfg.anthropic_api_key
            else None
        )
        self.analyzer = Analyzer(llm)
        if llm is None:
            log.warning("Pas de cle Anthropic : scoring heuristique uniquement.")

        x = XSource(self.cfg.x_accounts_file, self.cfg.x_queries)
        await x.setup()
        self.sources = [x]

        self.monitor.change_interval(seconds=self.cfg.poll_interval)
        self.monitor.start()

    async def close(self) -> None:
        if self.http_client:
            await self.http_client.aclose()
        await super().close()

    async def on_ready(self) -> None:
        log.info("Connecte en tant que %s", self.user)

    # ----- boucle de surveillance ------------------------------------------
    @tasks.loop(seconds=30)
    async def monitor(self) -> None:
        for source in self.sources:
            try:
                async for signal in source.fetch():
                    await self._process(signal, source.name)
            except Exception:
                log.exception("Erreur dans la source %s", source.name)

    @monitor.before_loop
    async def _before_monitor(self) -> None:
        await self.wait_until_ready()

    async def _process(self, signal: Signal, source_name: str) -> None:
        if not self.store.is_new("signal", f"{source_name}:{signal.raw_id}"):
            return
        await self.analyzer.analyze(signal)
        if signal.buzz_score < self.cfg.min_buzz_score:
            return
        coins = await self.matcher.find(signal)
        fresh = [c for c in coins if self.store.is_new("coin", c.mint)]
        await self._send_alert(Alert(signal=signal, coins=fresh[:5]))

    async def _send_alert(self, alert: Alert) -> None:
        channel = self.get_channel(self.cfg.discord_channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(self.cfg.discord_channel_id)
            except Exception as exc:
                log.error("Salon Discord %s introuvable: %s", self.cfg.discord_channel_id, exc)
                return
        try:
            await channel.send(embed=self._build_embed(alert))
        except Exception:
            log.exception("Envoi de l'alerte echoue")

    @staticmethod
    def _build_embed(alert: Alert) -> discord.Embed:
        s = alert.signal
        color = 0x2ECC71 if s.buzz_score >= 75 else 0xF1C40F
        embed = discord.Embed(
            title=f"Buzz detecte (score {s.buzz_score}/100)",
            description=(s.text[:500] + ("..." if len(s.text) > 500 else "")),
            color=color,
            url=s.url or None,
        )
        embed.add_field(name="Source", value=f"{s.source} · @{s.author}", inline=True)
        embed.add_field(name="Engagement", value=str(s.engagement), inline=True)
        if s.reason:
            embed.add_field(name="Analyse", value=s.reason[:200], inline=False)
        if s.tickers:
            embed.add_field(name="Tickers", value=", ".join(f"${t}" for t in s.tickers), inline=False)

        if not alert.coins:
            embed.add_field(
                name="Coins Solana",
                value="Aucun coin correspondant trouve (ou liquidite trop faible).",
                inline=False,
            )
        for coin in alert.coins:
            embed.add_field(name="​", value=MemeBot._coin_block(coin), inline=False)
        return embed

    @staticmethod
    def _coin_block(c: Coin) -> str:
        age = c.age_minutes()
        age_str = f"{age:.0f} min" if age is not None else "?"
        lines = [
            f"**{c.symbol or '?'}** — {c.name or '?'}",
            f"`{c.mint}`",
            f"Liq ${c.liquidity_usd:,.0f} · FDV ${c.fdv:,.0f} · age {age_str}",
        ]
        if c.is_known_dev:
            lines.append(f"⭐ Dev connu : {c.known_dev_label}")
        if c.top10_holder_pct:
            flag = " ⚠️" if c.top10_holder_pct > 50 else ""
            lines.append(f"Top10 holders : {c.top10_holder_pct}%{flag}")
        if c.mint_authority:
            lines.append("⚠️ mint authority active")
        if c.dex_url:
            lines.append(f"[DexScreener]({c.dex_url})")
        return "\n".join(lines)

    # ----- commandes manuelles ---------------------------------------------
    def _register_commands(self) -> None:
        @self.command(name="status")
        async def status(ctx: commands.Context) -> None:
            await ctx.send(
                f"En ligne. Sources: {len(self.sources)} · "
                f"seuil buzz: {self.cfg.min_buzz_score} · "
                f"intervalle: {self.cfg.poll_interval}s"
            )

        @self.command(name="scan")
        async def scan(ctx: commands.Context, *, query: str) -> None:
            """Recherche manuelle de coins pour un mot-cle : !scan <query>"""
            signal = Signal(
                source="manual", raw_id=f"manual:{query}", text=query,
                author=str(ctx.author), url="", created_at=discord.utils.utcnow(),
                keywords=[query],
            )
            coins = await self.matcher.find(signal)
            signal.buzz_score = 100
            signal.reason = "recherche manuelle"
            await ctx.send(embed=self._build_embed(Alert(signal=signal, coins=coins[:5])))
