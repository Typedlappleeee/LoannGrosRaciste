"""Cache de deduplication (sqlite) : on n'alerte jamais deux fois sur la meme chose."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path


class SeenStore:
    def __init__(self, path: str = "seen.db") -> None:
        self.conn = sqlite3.connect(path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS seen ("
            "  kind TEXT NOT NULL,"
            "  key  TEXT NOT NULL,"
            "  ts   REAL NOT NULL,"
            "  PRIMARY KEY (kind, key)"
            ")"
        )
        self.conn.commit()

    def is_new(self, kind: str, key: str) -> bool:
        """Retourne True et enregistre la cle si elle n'a jamais ete vue."""
        cur = self.conn.execute(
            "SELECT 1 FROM seen WHERE kind = ? AND key = ?", (kind, key)
        )
        if cur.fetchone() is not None:
            return False
        self.conn.execute(
            "INSERT INTO seen (kind, key, ts) VALUES (?, ?, ?)",
            (kind, key, time.time()),
        )
        self.conn.commit()
        return True

    def prune(self, max_age_seconds: float = 7 * 24 * 3600) -> None:
        cutoff = time.time() - max_age_seconds
        self.conn.execute("DELETE FROM seen WHERE ts < ?", (cutoff,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
