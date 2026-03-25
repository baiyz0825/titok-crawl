"""
Migration: Add UNIQUE constraint to users.uid

This migration:
1. Finds duplicate uid entries in users table
2. Merges duplicates, keeping the most recent entry
3. Adds UNIQUE constraint to uid column

Run with: python -m backend.db.migrations.add_uid_unique_constraint
"""

import asyncio
import sqlite3
from pathlib import Path

from backend.config import settings


async def run_migration():
    """Run the migration."""
    db_path = Path(settings.DATA_DIR) / "titok.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    print("Checking for duplicate uid entries...")

    # Find duplicates
    cursor.execute("""
        SELECT uid, COUNT(*) as cnt, GROUP_CONCAT(sec_user_id) as sec_user_ids
        FROM users
        WHERE uid IS NOT NULL
        GROUP BY uid
        HAVING COUNT(*) > 1
    """)

    duplicates = cursor.fetchall()

    if duplicates:
        print(f"Found {len(duplicates)} duplicate uid entries")

        for uid, count, sec_user_ids in duplicates:
            print(f"\nProcessing uid={uid}, count={count}, sec_user_ids={sec_user_ids}")

            # Get all records for this uid, ordered by updated_at desc
            cursor.execute("""
                SELECT id, sec_user_id, nickname, updated_at
                FROM users
                WHERE uid = ?
                ORDER BY updated_at DESC
            """, (uid,))

            records = cursor.fetchall()
            primary = records[0]
            primary_id, primary_sec_id, primary_name, _ = primary

            print(f"  Keeping: id={primary_id}, sec_user_id={primary_sec_id}, nickname={primary_name}")

            # Update works to use primary sec_user_id
            for record in records[1:]:
                old_id, old_sec_id, _, _ = record
                print(f"  Merging: id={old_id}, sec_user_id={old_sec_id}")

                # Update works
                cursor.execute(
                    "UPDATE works SET sec_user_id = ? WHERE sec_user_id = ?",
                    (primary_sec_id, old_sec_id)
                )
                print(f"    Updated {cursor.rowcount} works")

                # Update comments
                cursor.execute(
                    "UPDATE comments SET user_sec_uid = ? WHERE user_sec_uid = ?",
                    (primary_sec_id, old_sec_id)
                )
                print(f"    Updated {cursor.rowcount} comments")

                # Delete duplicate user
                cursor.execute("DELETE FROM users WHERE id = ?", (old_id,))
                print(f"    Deleted duplicate user")

        conn.commit()
        print("\nDuplicates merged successfully")
    else:
        print("No duplicate uid entries found")

    # Now add UNIQUE constraint
    # SQLite doesn't support ALTER TABLE ADD CONSTRAINT, so we need to recreate the table
    print("\nAdding UNIQUE constraint to uid column...")

    # Create new table with UNIQUE constraint
    cursor.execute("""
        CREATE TABLE users_new (
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
            is_verified INTEGER DEFAULT 0,
            verification_type TEXT,
            extra_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Copy data
    cursor.execute("""
        INSERT INTO users_new
        SELECT id, sec_user_id, uid, nickname, avatar_url, signature,
               douyin_id, location, follower_count, following_count,
               total_favorited, aweme_count, is_verified, verification_type,
               extra_data, created_at, updated_at
        FROM users
    """)

    # Drop old table
    cursor.execute("DROP TABLE users")

    # Rename new table
    cursor.execute("ALTER TABLE users_new RENAME TO users")

    conn.commit()
    print("UNIQUE constraint added successfully")

    conn.close()
    print("\nMigration completed!")


if __name__ == "__main__":
    asyncio.run(run_migration())
