import aiosqlite
from pathlib import Path

from backend.config import settings

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sec_user_id TEXT UNIQUE NOT NULL,
    uid TEXT,
    nickname TEXT,
    avatar_url TEXT,
    signature TEXT,
    douyin_id TEXT,
    location TEXT,
    follower_count INTEGER DEFAULT 0,
    following_count INTEGER DEFAULT 0,
    total_favorited INTEGER DEFAULT 0,
    aweme_count INTEGER DEFAULT 0,
    is_verified BOOLEAN DEFAULT FALSE,
    verification_type TEXT,
    extra_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS works (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aweme_id TEXT UNIQUE NOT NULL,
    sec_user_id TEXT NOT NULL,
    type TEXT NOT NULL CHECK(type IN ('video', 'note')),
    title TEXT,
    cover_url TEXT,
    duration INTEGER,
    digg_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    collect_count INTEGER DEFAULT 0,
    play_count INTEGER DEFAULT 0,
    hashtags TEXT,
    music_title TEXT,
    publish_time TIMESTAMP,
    extra_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sec_user_id) REFERENCES users(sec_user_id)
);

CREATE TABLE IF NOT EXISTS media_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aweme_id TEXT NOT NULL,
    media_type TEXT NOT NULL CHECK(media_type IN ('video', 'image', 'cover')),
    url TEXT NOT NULL,
    local_path TEXT,
    file_size INTEGER,
    download_status TEXT DEFAULT 'pending'
        CHECK(download_status IN ('pending', 'downloading', 'completed', 'failed')),
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (aweme_id) REFERENCES works(aweme_id)
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    target TEXT NOT NULL,
    params TEXT,
    status TEXT DEFAULT 'pending'
        CHECK(status IN ('pending', 'running', 'paused', 'completed', 'failed', 'cancelled')),
    priority INTEGER DEFAULT 0,
    progress REAL DEFAULT 0,
    result TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    cookies TEXT NOT NULL,
    user_agent TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id TEXT UNIQUE NOT NULL,
    aweme_id TEXT NOT NULL,
    user_nickname TEXT,
    user_sec_uid TEXT,
    user_avatar TEXT,
    content TEXT,
    digg_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    reply_to TEXT,
    create_time TIMESTAMP,
    ip_label TEXT,
    extra_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (aweme_id) REFERENCES works(aweme_id)
);

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sec_user_id TEXT NOT NULL,
    nickname TEXT,
    sync_type TEXT NOT NULL DEFAULT 'all' CHECK(sync_type IN ('profile', 'works', 'all')),
    interval_minutes INTEGER NOT NULL DEFAULT 1440,
    enabled BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sec_user_id) REFERENCES users(sec_user_id)
);

CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aweme_id TEXT UNIQUE NOT NULL,
    sec_user_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (aweme_id) REFERENCES works(aweme_id) ON DELETE CASCADE
);
"""


class Database:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.DB_PATH
        self._conn: aiosqlite.Connection | None = None

    async def connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_CREATE_TABLES_SQL)
        await self._conn.commit()
        # Migrations for existing databases
        await self._migrate()

    async def _migrate(self):
        """Run safe ALTER TABLE migrations for existing databases."""
        migrations = [
            ("comments", "reply_to", "ALTER TABLE comments ADD COLUMN reply_to TEXT"),
            ("works", "transcript", "ALTER TABLE works ADD COLUMN transcript TEXT"),
        ]
        for table, column, sql in migrations:
            cursor = await self._conn.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in await cursor.fetchall()]
            if column not in columns:
                await self._conn.execute(sql)
                await self._conn.commit()

        # Create favorites table if not exists (for existing databases)
        cursor = await self._conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='favorites'")
        if not await cursor.fetchone():
            await self._conn.execute("""
                CREATE TABLE favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aweme_id TEXT UNIQUE NOT NULL,
                    sec_user_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (aweme_id) REFERENCES works(aweme_id) ON DELETE CASCADE
                )
            """)
            await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn


# Global singleton
db = Database()
