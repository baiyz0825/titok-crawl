"""
Migration script to merge schedules into tasks table.

This script:
1. Reads all existing schedules
2. Creates corresponding tasks with is_scheduled=True
3. Sets up the next_run_at based on interval_minutes
4. Can be safely run multiple times (idempotent)

Usage: cd /path/to/titok-crawl && python backend/db/migrations/merge_schedules.py
"""
import asyncio
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path


def migrate_schedules_to_tasks():
    """Migrate existing schedules to scheduled tasks."""
    # Add parent directory to path
    project_root = Path(__file__).parent.parent.parent.parent
    db_path = project_root / "data" / "db" / "douyin.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    print(f"Using database: {db_path}")
    print("Starting migration: schedules -> tasks")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if schedules table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schedules'"
    )
    if not cursor.fetchone():
        print("No schedules table found - skipping migration")
        conn.close()
        return

    # Check if tasks table has new columns
    cursor.execute("PRAGMA table_info(tasks)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'is_scheduled' not in columns:
        print("Tasks table missing is_scheduled column - adding it")
        cursor.execute("ALTER TABLE tasks ADD COLUMN is_scheduled BOOLEAN DEFAULT 0")
    if 'schedule_interval' not in columns:
        print("Tasks table missing schedule_interval column - adding it")
        cursor.execute("ALTER TABLE tasks ADD COLUMN schedule_interval INTEGER")
    if 'next_run_at' not in columns:
        print("Tasks table missing next_run_at column - adding it")
        cursor.execute("ALTER TABLE tasks ADD COLUMN next_run_at TIMESTAMP")
    conn.commit()

    # Get all enabled schedules
    cursor.execute("SELECT * FROM schedules WHERE enabled = 1")
    schedules = cursor.fetchall()

    if not schedules:
        print("No enabled schedules found - skipping migration")
        conn.close()
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
        cursor.execute(
            """SELECT id FROM tasks
            WHERE target = ? AND is_scheduled = 1""",
            (sec_user_id,)
        )
        existing = cursor.fetchone()

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
            try:
                last_run_dt = datetime.fromisoformat(last_run_at)
                next_run = last_run_dt + timedelta(minutes=interval_minutes)
            except:
                next_run = datetime.now() + timedelta(minutes=interval_minutes)
        else:
            next_run = datetime.now() + timedelta(minutes=interval_minutes)

        # Create the scheduled task
        cursor.execute(
            """INSERT INTO tasks (task_type, target, is_scheduled, schedule_interval, next_run_at, status)
            VALUES (?, ?, 1, ?, ?, 'pending')""",
            (task_type, sec_user_id, interval_minutes, next_run.isoformat())
        )
        task_id = cursor.lastrowid
        conn.commit()

        migrated_count += 1
        print(f"  Migrated schedule {schedule_id}: {nickname or sec_user_id} -> task #{task_id}")

    print(f"\nMigration complete: {migrated_count} schedules migrated")

    # Optional: Drop the schedules table after successful migration
    print("\nTo drop the old schedules table, run:")
    print(f"  sqlite3 {db_path} \"DROP TABLE IF EXISTS schedules;\"")

    conn.close()


if __name__ == "__main__":
    migrate_schedules_to_tasks()
