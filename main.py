"""Point d'entree de l'agent LoanGrosRaciste."""
from __future__ import annotations

import logging

from bot import MemeBot
from config import Config
from store import SeenStore


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cfg = Config()
    cfg.require_runtime()
    store = SeenStore()
    store.prune()

    bot = MemeBot(cfg, store)
    try:
        bot.run(cfg.discord_token, log_handler=None)
    finally:
        store.close()


if __name__ == "__main__":
    main()
