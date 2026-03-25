#!/usr/bin/env python3
"""
Migration script to add uid column to works table and populate it from author data.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "db" / "douyin.db"


def migrate():
    """Run the migration to add uid column to works table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("Starting works table migration (adding uid column)...")
    print("=" * 80)
    
    # Step 1: Check if uid column already exists
    cursor.execute("PRAGMA table_info(works)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "uid" in columns:
        print("✅ uid column already exists in works table")
    else:
        print("\n📝 Adding uid column to works table...")
        try:
            cursor.execute("""
                ALTER TABLE works 
                ADD COLUMN uid TEXT
            """)
            conn.commit()
            print("✅ Successfully added uid column")
        except Exception as e:
            print(f"❌ Failed to add uid column: {e}")
            return
    
    # Step 2: Create index on uid for faster queries
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_works_uid ON works(uid)")
        conn.commit()
        print("✅ Created index on works.uid")
    except Exception as e:
        print(f"⚠️  Failed to create index: {e}")
    
    # Step 3: Populate uid from users table where possible
    print("\n📝 Populating uid from users table...")
    cursor.execute("""
        UPDATE works 
        SET uid = (
            SELECT uid FROM users 
            WHERE users.sec_user_id = works.sec_user_id
        )
        WHERE uid IS NULL
    """)
    updated_count = cursor.rowcount
    conn.commit()
    print(f"✅ Updated {updated_count} works with uid from users table")
    
    # Step 4: Try to extract uid from extra_data (JSON) for remaining works
    print("\n📝 Extracting uid from extra_data for remaining works...")
    cursor.execute("""
        UPDATE works 
        SET uid = json_extract(extra_data, '$.author_uid')
        WHERE uid IS NULL 
          AND json_extract(extra_data, '$.author_uid') IS NOT NULL
    """)
    extracted_count = cursor.rowcount
    conn.commit()
    print(f"✅ Extracted uid from extra_data for {extracted_count} works")
    
    # Step 5: Report works that still don't have uid
    cursor.execute("""
        SELECT COUNT(*) FROM works WHERE uid IS NULL OR uid = ''
    """)
    null_count = cursor.fetchone()[0]
    
    if null_count > 0:
        print(f"\n⚠️  Warning: {null_count} works still don't have uid")
        print("   These works will need manual intervention or re-scraping")
    else:
        print("\n✅ All works now have uid populated")
    
    # Step 6: Add NOT NULL constraint (requires recreating the table in SQLite)
    if null_count == 0:
        print("\n📝 Making uid column NOT NULL...")
        try:
            # SQLite doesn't support adding NOT NULL to existing columns
            # We need to recreate the table
            cursor.execute("BEGIN TRANSACTION")
            
            # Create new table with proper schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS works_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    aweme_id TEXT UNIQUE NOT NULL,
                    uid TEXT NOT NULL,
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
                    transcript TEXT,
                    extra_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sec_user_id) REFERENCES users(sec_user_id),
                    FOREIGN KEY (uid) REFERENCES users(uid)
                )
            """)
            
            # Copy data from old table to new table
            cursor.execute("""
                INSERT INTO works_new 
                SELECT * FROM works
            """)
            
            # Drop old table
            cursor.execute("DROP TABLE works")
            
            # Rename new table
            cursor.execute("ALTER TABLE works_new RENAME TO works")
            
            # Recreate indexes
            cursor.execute("CREATE INDEX idx_works_uid ON works(uid)")
            
            conn.commit()
            print("✅ Successfully made uid column NOT NULL")
            
        except Exception as e:
            conn.rollback()
            print(f"⚠️  Failed to make uid NOT NULL: {e}")
            print("   uid column remains nullable for now")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("Migration completed!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
