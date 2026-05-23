"""Source X (Twitter) via twscrape.

twscrape utilise des comptes X (de preference JETABLES) pour interroger
l'API interne de X. C'est la seule voie reellement gratuite qui fonctionne
aujourd'hui ; elle est contre les CGU de X et un compte peut etre banni,
d'ou l'usage de comptes jetables.

Format du fichier de comptes (une ligne par compte) :
    username:password:email:email_password
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from pathlib import Path

from twscrape import API

from models import Signal
from sources.base import Source

log = logging.getLogger("source.x")


class XSource(Source):
    name = "x"

    def __init__(
        self,
        accounts_file: str,
        queries: list[str],
        per_query_limit: int = 20,
        db_path: str = "accounts.db",
    ) -> None:
        self.accounts_file = accounts_file
        self.queries = queries
        self.per_query_limit = per_query_limit
        self.api = API(db_path)
        self._ready = False

    async def setup(self) -> None:
        await self._load_accounts()
        await self.api.pool.login_all()
        accounts = await self.api.pool.accounts_info()
        active = [a for a in accounts if a.get("active")]
        if not active:
            log.warning(
                "Aucun compte X actif. La source X ne renverra rien tant que "
                "tu n'auras pas ajoute de comptes valides dans %s.",
                self.accounts_file,
            )
        else:
            log.info("Source X prete avec %d compte(s) actif(s).", len(active))
        self._ready = True

    async def _load_accounts(self) -> None:
        path = Path(self.accounts_file)
        if not path.exists():
            log.warning("Fichier de comptes X introuvable: %s", path)
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) < 4:
                log.warning("Ligne de compte ignoree (format invalide): %s", line)
                continue
            username, password, email, email_pw = parts[:4]
            try:
                await self.api.pool.add_account(username, password, email, email_pw)
            except Exception as exc:  # compte deja present, etc.
                log.debug("add_account(%s): %s", username, exc)

    async def fetch(self) -> AsyncIterator[Signal]:
        if not self._ready:
            return
        for query in self.queries:
            try:
                async for tw in self.api.search(
                    query, limit=self.per_query_limit, kv={"product": "Latest"}
                ):
                    yield self._to_signal(tw)
            except Exception as exc:
                log.warning("Echec de la recherche X pour '%s': %s", query, exc)

    @staticmethod
    def _to_signal(tw) -> Signal:
        engagement = (
            (tw.likeCount or 0)
            + (tw.retweetCount or 0)
            + (tw.replyCount or 0)
            + (getattr(tw, "quoteCount", 0) or 0)
        )
        return Signal(
            source="x",
            raw_id=str(tw.id),
            text=tw.rawContent or "",
            author=tw.user.username if tw.user else "?",
            url=tw.url or f"https://x.com/i/status/{tw.id}",
            created_at=tw.date,
            engagement=engagement,
        )
