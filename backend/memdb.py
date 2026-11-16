"""Holder for a pre-built in-memory SQLite connection (serverless deployment).

deploy/vercel-api/api/index.py loads the slim warehouse shards into one sqlite3 connection (main + attached
in-memory schemas) and stores it here *before* backend.database is imported (this module lives outside that package so importing it does not create the engine early); the session module then
serves every query from that connection instead of opening a database file.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

CONN: Optional[sqlite3.Connection] = None
