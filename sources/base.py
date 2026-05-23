"""Interface commune des sources d'information.

Une source produit des `Signal`. On la concoit comme un adaptateur enfichable :
aujourd'hui X via twscrape, demain une API payante, Telegram, etc.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from models import Signal


class Source(ABC):
    name: str = "base"

    async def setup(self) -> None:
        """Initialisation asynchrone (connexion, login...). Optionnel."""

    @abstractmethod
    def fetch(self) -> AsyncIterator[Signal]:
        """Renvoie les nouveaux signaux depuis le dernier appel.

        Doit etre un async generator. L'orchestrateur se charge de la
        deduplication via le SeenStore, donc une source peut renvoyer des
        doublons sans risque.
        """
        raise NotImplementedError
