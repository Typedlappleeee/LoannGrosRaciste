"""Sorties optionnelles : envoi d'une alerte vers un webhook Discord."""
from __future__ import annotations

import logging

import httpx

from models import Alert, Coin

log = logging.getLogger("outputs.discord")


def _coin_line(c: Coin) -> str:
    age = c.age_minutes()
    age_str = f"{age:.0f}min" if age is not None else "?"
    parts = [f"**{c.symbol or '?'}** liq ${c.liquidity_usd:,.0f} · age {age_str}"]
    if c.is_known_dev:
        parts.append(f"⭐{c.known_dev_label}")
    if c.top10_holder_pct:
        parts.append(f"top10 {c.top10_holder_pct}%")
    if c.dex_url:
        parts.append(c.dex_url)
    return " · ".join(parts)


async def send_discord(client: httpx.AsyncClient, webhook_url: str, alert: Alert) -> None:
    if not webhook_url:
        return
    s = alert.signal
    lines = [
        f"**Buzz {s.buzz_score}/100** — {s.source} @{s.author}",
        s.text[:400],
    ]
    if s.tickers:
        lines.append("Tickers: " + ", ".join(f"${t}" for t in s.tickers))
    if alert.coins:
        lines.append("__Coins__:")
        lines += [f"• {_coin_line(c)}" for c in alert.coins]
    else:
        lines.append("_Aucun coin correspondant._")
    content = "\n".join(lines)[:1900]
    try:
        await client.post(webhook_url, json={"content": content}, timeout=10)
    except Exception as exc:
        log.warning("Envoi webhook Discord echoue: %s", exc)
