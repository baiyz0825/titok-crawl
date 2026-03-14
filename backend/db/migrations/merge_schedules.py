"""
Migration script to merge schedules into tasks table.

This script:
1. Reads all existing schedules
2. Creates corresponding tasks with is_scheduled=True
3. Sets up the next_run_at based on interval_minutes
4. Can be safely run multiple times (idempotent)
"""
import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.db.database import db


async def migrate_schedules_to_tasks():
    """Migrate existing schedules to scheduled tasks."""
    await db.connect()

    print("Starting migration: schedules -> tasks")

    # Check if schedules table exists
    cursor = await db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schedules'"
    )
    if not await cursor.fetchone():
        print("No schedules table found - skipping migration")
        await db.close()
        return

    # Get all enabled schedules
    cursor = await db.conn.execute(
        "SELECT * FROM schedules WHERE enabled = 1"
    )
    schedules = await cursor.fetchall()

    if not schedules:
        print("No enabled schedules found - skipping migration")
        await db.close()
        return

    print(f"Found {len(schedules)} schedules to migrate")

    migrated_count = 0
    for schedule in schedules:
        schedule_dict = dict(schedule)
        schedule_id = schedule_dict['id']
        sec_user_id = schedule_dict['sec_user_id']
        nickname = schedule_dict.get('nickname')
        sync_type = schedule_dict.get('sync_type', 'all')
        interval_minutes = schedule_dict.get('interval_minutes', 1440)
        last_run_at = schedule_dict.get('last_run_at')

        # Check if we already migrated this schedule
        cursor = await db.conn.execute(
            """SELECT id FROM tasks
            WHERE target = ? AND task_type = ? AND is_scheduled = 1""",
            (sec_user_id, f"user_{sync_type}")
        )
        existing = await cursor.fetchone()

        if existing:
            print(f"  Schedule {schedule_id} already migrated (task #{existing[0]})")
            continue

        # Map sync_type to task_type
        task_type_map = {
            "profile": "user_profile",
            "works": "user_works",
            "all": "user_all",
        }
        task_type = task_type_map.get(sync_type, "user_all")

        # Calculate next_run_at
        if last_run_at:
            next_run = datetime.fromisoformat(last_run_at) + timedelta(minutes=interval_minutes)
        else:
            next_run = datetime.now() + timedelta(minutes=interval_minutes)

        # Create the scheduled task
        cursor = await db.conn.execute(
            """INSERT INTO tasks (task_type, target, is_scheduled, schedule_interval, next_run_at, status)
            VALUES (?, ?, 1, ?, ?, 'pending')""",
            (task_type, sec_user_id, interval_minutes, next_run.isoformat())
        )
        task_id = cursor.lastrowid
        await db.conn.commit()

        migrated_count += 1
        print(f"  Migrated schedule {schedule_id}: {nickname or sec_user_id} -> task #{task_id}")

    print(f"\nMigration complete: {migrated_count} schedules migrated")

    # Optional: Drop the schedules table after successful migration
    print("\nTo drop the old schedules table, run:")
    print(f"  sqlite3 {db.db_path} \"DROP TABLE IF EXISTS schedules;\"")

    await db.close()


if __name__ == "__main__":
    asyncio.run(migrate_schedules_to_tasks())
