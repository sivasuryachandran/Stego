"""Append-only JSONL log of every model call (the 'Receipts'), plus a disk cache."""
import hashlib
import json
import os
import sqlite3
import threading
import time

_lock = threading.Lock()


class Ledger:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        self.f = open(path, "a", encoding="utf-8")

    def log(self, **rec):
        rec["ts"] = time.time()
        with _lock:
            self.f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self.f.flush()


class Cache:
    """Avoid paying twice while iterating tonight. Disable for the final timed run (--no-cache)."""

    def __init__(self, path, enabled=True):
        self.enabled = enabled
        if enabled:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            self.db = sqlite3.connect(path, check_same_thread=False)
            self.db.execute("CREATE TABLE IF NOT EXISTS c (k TEXT PRIMARY KEY, v TEXT)")

    @staticmethod
    def key(*parts):
        return hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()

    def get(self, k):
        if not self.enabled:
            return None
        with _lock:
            row = self.db.execute("SELECT v FROM c WHERE k=?", (k,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, k, v):
        if not self.enabled:
            return
        with _lock:
            self.db.execute("INSERT OR REPLACE INTO c VALUES (?,?)", (k, json.dumps(v)))
            self.db.commit()
