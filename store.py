"""Stockage sqlite : deduplication des signaux/coins + historique des alertes."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class SeenStore:
    def __init__(self, path: str = "seen.db") -> None:
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS seen ("
            "  kind TEXT NOT NULL,"
            "  key  TEXT NOT NULL,"
            "  ts   REAL NOT NULL,"
            "  PRIMARY KEY (kind, key)"
            ")"
        )
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS alerts ("
            "  id   INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  ts   REAL NOT NULL,"
            "  data TEXT NOT NULL"
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

    def save_alert(self, alert_dict: dict) -> None:
        self.conn.execute(
            "INSERT INTO alerts (ts, data) VALUES (?, ?)",
            (time.time(), json.dumps(alert_dict)),
        )
        self.conn.commit()

    def recent_alerts(self, limit: int = 50) -> list[dict]:
        cur = self.conn.execute(
            "SELECT data FROM alerts ORDER BY id DESC LIMIT ?", (limit,)
        )
        return [json.loads(row[0]) for row in cur.fetchall()]

    def prune(self, max_age_seconds: float = 7 * 24 * 3600) -> None:
        cutoff = time.time() - max_age_seconds
        self.conn.execute("DELETE FROM seen WHERE ts < ?", (cutoff,))
        self.conn.execute(
            "DELETE FROM alerts WHERE ts < ?", (time.time() - 30 * 24 * 3600,)
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
