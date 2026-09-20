"""
Database module — async SQLite storage for accounts, sessions, operations.
All credential fields are stored already-encrypted by CredentialManager.
"""

import os
import logging
import aiosqlite

logger = logging.getLogger(__name__)


class Database:
    """Async SQLite database manager."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self):
        """Create database file and tables if they don't exist."""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._create_tables()
        logger.info(f"Database initialized at {self.db_path}")

    async def _create_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_encrypted TEXT NOT NULL,
                password_encrypted TEXT NOT NULL,
                service TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'created',
                region TEXT,
                display_name TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service TEXT NOT NULL UNIQUE,
                storage_state_encrypted TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                op_type TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS spotify_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code_encrypted TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'hm_profile',
                status TEXT NOT NULL DEFAULT 'retrieved',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        await self._db.commit()

    # ── Accounts ──────────────────────────────────────────────

    async def save_account(
        self,
        email_enc: str,
        password_enc: str,
        service: str,
        status: str = "created",
        region: str | None = None,
        display_name: str | None = None,
    ) -> int:
        cursor = await self._db.execute(
            """INSERT INTO accounts
               (email_encrypted, password_encrypted, service, status, region, display_name)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (email_enc, password_enc, service, status, region, display_name),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_account(self, service: str) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM accounts WHERE service = ? ORDER BY id DESC LIMIT 1",
            (service,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_all_accounts(self) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM accounts ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def update_account_status(self, account_id: int, status: str):
        await self._db.execute(
            "UPDATE accounts SET status = ? WHERE id = ?", (status, account_id)
        )
        await self._db.commit()

    # ── Sessions ──────────────────────────────────────────────

    async def save_session(self, service: str, storage_state_enc: str):
        await self._db.execute(
            """INSERT OR REPLACE INTO sessions
               (service, storage_state_encrypted, updated_at)
               VALUES (?, ?, datetime('now'))""",
            (service, storage_state_enc),
        )
        await self._db.commit()

    async def get_session(self, service: str) -> str | None:
        cursor = await self._db.execute(
            "SELECT storage_state_encrypted FROM sessions WHERE service = ?",
            (service,),
        )
        row = await cursor.fetchone()
        return row["storage_state_encrypted"] if row else None

    async def clear_session(self, service: str):
        await self._db.execute("DELETE FROM sessions WHERE service = ?", (service,))
        await self._db.commit()

    async def clear_all_sessions(self):
        await self._db.execute("DELETE FROM sessions")
        await self._db.commit()

    async def get_active_sessions(self) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT service, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── Spotify Codes ─────────────────────────────────────────

    async def save_spotify_code(self, code_enc: str, source: str = "hm_profile") -> int:
        cursor = await self._db.execute(
            "INSERT INTO spotify_codes (code_encrypted, source) VALUES (?, ?)",
            (code_enc, source),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def get_latest_spotify_code(self) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM spotify_codes WHERE status = 'retrieved' ORDER BY id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update_spotify_code_status(self, code_id: int, status: str):
        await self._db.execute(
            "UPDATE spotify_codes SET status = ? WHERE id = ?", (status, code_id)
        )
        await self._db.commit()

    # ── Operations Log ────────────────────────────────────────

    async def log_operation(self, op_type: str, status: str, details: str | None = None):
        await self._db.execute(
            "INSERT INTO operations (op_type, status, details) VALUES (?, ?, ?)",
            (op_type, status, details),
        )
        await self._db.commit()

    async def get_operations(self, limit: int = 10) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM operations ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── Cleanup ───────────────────────────────────────────────

    async def purge_junk_codes(self, cred_mgr) -> int:
        """
        Decrypt every 'retrieved' spotify_code and mark it 'invalid'
        if it looks like a junk word (pure letters, no digits, known blacklist).
        Returns the number of codes purged.
        """
        JUNK_WORDS = {
            "permission", "undefined", "cookie", "accept", "submit", "button", "none", "trial",
            "subscribe", "standard", "membership", "overview", "benefit", "voucher", "account",
            "settings", "profile", "details", "password", "continue", "register", "redeem",
            "cancel", "login", "signup", "logout", "privacy", "terms", "help", "support",
            "home", "index", "about", "contact", "error", "page", "month", "months",
        }
        cursor = await self._db.execute(
            "SELECT id, code_encrypted FROM spotify_codes WHERE status = 'retrieved'"
        )
        rows = await cursor.fetchall()
        purged = 0
        for row in rows:
            try:
                code = cred_mgr.decrypt(row["code_encrypted"])
                c = code.strip().lower()
                is_junk = (
                    c in JUNK_WORDS
                    or (c.isalpha() and len(c) <= 30)  # pure letters = not a real code
                )
                if is_junk:
                    await self._db.execute(
                        "UPDATE spotify_codes SET status = 'invalid' WHERE id = ?",
                        (row["id"],),
                    )
                    purged += 1
                    logger.info(f"Purged junk code id={row['id']}: '{code}'")
            except Exception as e:
                logger.warning(f"Could not check code id={row['id']}: {e}")
        if purged:
            await self._db.commit()
        return purged

    async def clear_all_data(self):
        await self._db.executescript("""
            DELETE FROM sessions;
            DELETE FROM accounts;
            DELETE FROM spotify_codes;
            DELETE FROM operations;
        """)
        await self._db.commit()
        logger.info("All database data cleared")

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None
            logger.info("Database connection closed")
