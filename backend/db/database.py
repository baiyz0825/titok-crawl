import aiosqlite
import logging
from pathlib import Path

from backend.config import settings

logger = logging.getLogger(__name__)

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sec_user_id TEXT UNIQUE NOT NULL,
    uid TEXT UNIQUE,
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
    uid TEXT NOT NULL,  -- Author's real unique identifier (more stable than sec_user_id)
    sec_user_id TEXT NOT NULL,  -- Current sec_user_id (may change over time)
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
    FOREIGN KEY (sec_user_id) REFERENCES users(sec_user_id),
    FOREIGN KEY (uid) REFERENCES users(uid)
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
    UNIQUE(aweme_id, media_type),
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
    is_scheduled BOOLEAN DEFAULT FALSE,
    schedule_interval INTEGER,
    next_run_at TIMESTAMP,
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
    user_uid TEXT NOT NULL,  -- Comment author's real unique identifier
    user_sec_uid TEXT,  -- Current sec_user_id (may change over time)
    user_nickname TEXT,
    user_avatar TEXT,
    content TEXT,
    digg_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    reply_to TEXT,
    create_time TIMESTAMP,
    ip_label TEXT,
    extra_data TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (aweme_id) REFERENCES works(aweme_id),
    FOREIGN KEY (user_uid) REFERENCES users(uid)
);

CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aweme_id TEXT UNIQUE NOT NULL,
    uid TEXT NOT NULL,  -- User's real unique identifier who favorited this work
    sec_user_id TEXT,  -- Current sec_user_id (may change over time)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (aweme_id) REFERENCES works(aweme_id) ON DELETE CASCADE,
    FOREIGN KEY (uid) REFERENCES users(uid)
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
        # Enable WAL mode for better concurrent read/write performance
        # This prevents frontend from blocking when backend is writing
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA busy_timeout=30000")  # 30 seconds timeout
        await self._conn.executescript(_CREATE_TABLES_SQL)
        await self._conn.commit()
        logger.info("Database connected with WAL mode enabled")
        # Migrations for existing databases
        await self._migrate()

    async def _migrate(self):
        """Run safe ALTER TABLE migrations for existing databases."""
        migrations = [
            ("comments", "reply_to", "ALTER TABLE comments ADD COLUMN reply_to TEXT"),
            ("works", "transcript", "ALTER TABLE works ADD COLUMN transcript TEXT"),
            ("tasks", "is_scheduled", "ALTER TABLE tasks ADD COLUMN is_scheduled BOOLEAN DEFAULT 0"),
            ("tasks", "schedule_interval", "ALTER TABLE tasks ADD COLUMN schedule_interval INTEGER"),
            ("tasks", "next_run_at", "ALTER TABLE tasks ADD COLUMN next_run_at TIMESTAMP"),
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

        # Add unique constraint to media_files (aweme_id, media_type) if not exists
        # SQLite doesn't support ADD CONSTRAINT, so we need to recreate the table
        cursor = await self._conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='media_files'")
        row = await cursor.fetchone()
        if row and "UNIQUE" not in row[0]:
            # Backup and recreate media_files with unique constraint
            await self._conn.execute("""
                CREATE TABLE IF NOT EXISTS media_files_new (
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
                    UNIQUE(aweme_id, media_type)
                )
            """)
            # Copy existing data
            await self._conn.execute("""
                INSERT INTO media_files_new SELECT * FROM media_files
            """)
            # Drop old table and rename
            await self._conn.execute("DROP TABLE media_files")
            await self._conn.execute("ALTER TABLE media_files_new RENAME TO media_files")
            await self._conn.commit()
            logger.info("Migrated media_files table with unique constraint")

    async def close(self):
        if self._conn:
            try:
                # Perform WAL checkpoint to ensure all data is written
                await self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                await self._conn.commit()
                logger.info("WAL checkpoint completed")
            except Exception as e:
                logger.warning(f"WAL checkpoint failed: {e}")
            finally:
                await self._conn.close()
                self._conn = None
                logger.info("Database connection closed")

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn


# Global singleton
db = Database()
