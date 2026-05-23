"""Configuration runtime, editable depuis l'interface web.

Valeurs par defaut <- variables d'environnement (.env) <- settings.json.
Le fichier settings.json (gitignore) est la source modifiee par l'UI.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

SETTINGS_FILE = Path(os.getenv("SETTINGS_FILE", "settings.json"))

# Champs consideres comme secrets : masques dans les reponses API.
SECRET_FIELDS = {"helius_api_key", "anthropic_api_key", "discord_webhook_url", "x_accounts"}


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name, "")
    items = [x.strip() for x in raw.split(";") if x.strip()]
    return items or default


@dataclass
class Settings:
    # sorties
    discord_webhook_url: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # source X
    x_accounts: str = ""  # multi-lignes "user:pass:email:email_pass"
    x_queries: list[str] = field(
        default_factory=lambda: _env_list(
            "X_QUERIES", ["breaking", "trending", "just launched", "memecoin"]
        )
    )

    # solana / IA
    helius_api_key: str = os.getenv("HELIUS_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    # reglages
    poll_interval: int = int(os.getenv("POLL_INTERVAL", "30") or 30)
    min_buzz_score: int = int(os.getenv("MIN_BUZZ_SCORE", "55") or 55)
    min_liquidity_usd: float = float(os.getenv("MIN_LIQUIDITY_USD", "2000") or 2000)

    # devs connus : { "wallets": {addr: label}, "handles": {handle: label} }
    known_devs: dict = field(default_factory=lambda: {"wallets": {}, "handles": {}})

    # ---- persistance -------------------------------------------------------
    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        if SETTINGS_FILE.exists():
            try:
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                for k, v in data.items():
                    if hasattr(s, k):
                        setattr(s, k, v)
            except Exception:
                pass
        return s

    def save(self) -> None:
        SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def update(self, data: dict) -> None:
        """Applique un patch partiel (depuis l'UI), ignore les champs inconnus
        et les secrets envoyes vides (pour ne pas ecraser une valeur existante)."""
        for k, v in data.items():
            if not hasattr(self, k):
                continue
            if k in SECRET_FIELDS and (v is None or v == ""):
                continue  # ne pas effacer un secret avec une valeur vide
            setattr(self, k, v)

    def public_dict(self) -> dict:
        """Version pour l'UI : les secrets sont remplaces par un booleen 'is_set'."""
        out = asdict(self)
        for f in SECRET_FIELDS:
            value = out.get(f) or ""
            out[f] = ""               # ne jamais renvoyer la valeur en clair
            out[f + "_is_set"] = bool(value)
        return out

    def known_wallets(self) -> dict[str, str]:
        return dict((self.known_devs or {}).get("wallets", {}))

    def known_handles(self) -> dict[str, str]:
        return {
            k.lower().lstrip("@"): v
            for k, v in (self.known_devs or {}).get("handles", {}).items()
        }
