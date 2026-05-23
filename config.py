"""Chargement de la configuration depuis l'environnement (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


@dataclass
class Config:
    discord_token: str = os.getenv("DISCORD_TOKEN", "").strip()
    discord_channel_id: int = _int("DISCORD_CHANNEL_ID", 0)

    x_accounts_file: str = os.getenv("X_ACCOUNTS_FILE", "accounts.txt").strip()
    x_queries: list[str] = field(
        default_factory=lambda: [
            q.strip() for q in os.getenv("X_QUERIES", "").split(";") if q.strip()
        ]
        or ["breaking", "trending", "just launched", "memecoin"]
    )

    helius_api_key: str = os.getenv("HELIUS_API_KEY", "").strip()

    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "").strip()
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()

    poll_interval: int = _int("POLL_INTERVAL", 30)
    min_buzz_score: int = _int("MIN_BUZZ_SCORE", 55)
    min_liquidity_usd: float = _float("MIN_LIQUIDITY_USD", 2000.0)
    known_devs_file: str = os.getenv("KNOWN_DEVS_FILE", "known_devs.json").strip()

    def require_runtime(self) -> None:
        """Verifie les valeurs indispensables au demarrage."""
        missing = []
        if not self.discord_token:
            missing.append("DISCORD_TOKEN")
        if not self.discord_channel_id:
            missing.append("DISCORD_CHANNEL_ID")
        if missing:
            raise SystemExit(
                "Configuration manquante: " + ", ".join(missing) +
                ". Copie .env.example en .env et remplis ces valeurs."
            )
