"""Structures de donnees partagees dans le pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Signal:
    """Une info reperee sur une source (X, etc.)."""

    source: str          # "x", "nitter", ...
    raw_id: str          # identifiant unique cote source (id du tweet)
    text: str
    author: str
    url: str
    created_at: datetime
    engagement: int = 0  # likes + RT + replies, indicateur brut de buzz

    # Renseignes par l'analyse :
    buzz_score: int = 0          # 0-100
    reason: str = ""             # pourquoi c'est juge important
    keywords: list[str] = field(default_factory=list)
    tickers: list[str] = field(default_factory=list)

    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "raw_id": self.raw_id,
            "text": self.text,
            "author": self.author,
            "url": self.url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "engagement": self.engagement,
            "buzz_score": self.buzz_score,
            "reason": self.reason,
            "keywords": self.keywords,
            "tickers": self.tickers,
        }


@dataclass
class Coin:
    """Un token Solana candidat, lie a un signal."""

    mint: str
    name: str
    symbol: str
    dex_url: str = ""
    price_usd: float = 0.0
    liquidity_usd: float = 0.0
    fdv: float = 0.0
    volume_24h: float = 0.0
    created_at: datetime | None = None
    creator: str = ""            # wallet deployeur / autorite
    top10_holder_pct: float = 0.0
    mint_authority: str | None = None
    freeze_authority: str | None = None
    is_known_dev: bool = False
    known_dev_label: str = ""

    def age_minutes(self) -> float | None:
        if not self.created_at:
            return None
        return (datetime.now(timezone.utc) - self.created_at).total_seconds() / 60

    def to_dict(self) -> dict:
        return {
            "mint": self.mint,
            "name": self.name,
            "symbol": self.symbol,
            "dex_url": self.dex_url,
            "price_usd": self.price_usd,
            "liquidity_usd": self.liquidity_usd,
            "fdv": self.fdv,
            "volume_24h": self.volume_24h,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "age_minutes": self.age_minutes(),
            "creator": self.creator,
            "top10_holder_pct": self.top10_holder_pct,
            "mint_authority": self.mint_authority,
            "freeze_authority": self.freeze_authority,
            "is_known_dev": self.is_known_dev,
            "known_dev_label": self.known_dev_label,
        }


@dataclass
class Alert:
    """Ce qui est envoye sur Discord : un signal + les coins trouves."""

    signal: Signal
    coins: list[Coin] = field(default_factory=list)
    ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "ts": self.ts.isoformat(),
            "signal": self.signal.to_dict(),
            "coins": [c.to_dict() for c in self.coins],
        }
