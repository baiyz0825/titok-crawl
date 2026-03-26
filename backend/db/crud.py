import json
import logging
from datetime import datetime

from backend.db.database import db
from backend.db.models import User, Work, MediaFile, Task, Session, Comment, Favorite

logger = logging.getLogger(__name__)


# ── Users ──

async def upsert_user(user: User) -> int:
    """Insert or update user. If uid is provided, merge by uid instead of sec_user_id.
    
    This handles the case where the same user (same uid) might have different
    sec_user_ids due to different login sessions or account binding scenarios.
    """
    now = datetime.now().isoformat()
    
    # If uid is provided, check if user with this uid already exists
    if user.uid:
        cursor = await db.conn.execute(
            "SELECT sec_user_id FROM users WHERE uid = ? LIMIT 1",
            (user.uid,)
        )
        existing = await cursor.fetchone()
        
        if existing and existing[0] != user.sec_user_id:
            # Found existing user with same uid but different sec_user_id
            # Update the existing record with new sec_user_id and latest data
            primary_sec_id = existing[0]
            await db.conn.execute(
                """UPDATE users SET 
                    sec_user_id=?, nickname=?, avatar_url=?, signature=?,
                    douyin_id=?, location=?, follower_count=?, following_count=?,
                    total_favorited=?, aweme_count=?, is_verified=?, 
                    verification_type=?, extra_data=?, updated_at=?
                WHERE uid=?""",
                (user.sec_user_id, user.nickname, user.avatar_url, user.signature,
                 user.douyin_id, user.location, user.follower_count, user.following_count,
                 user.total_favorited, user.aweme_count, user.is_verified,
                 user.verification_type, user.extra_data, now, user.uid),
            )
            await db.conn.commit()
            
            # Update all works to use the new sec_user_id
            await db.conn.execute(
                "UPDATE works SET sec_user_id = ? WHERE sec_user_id = ?",
                (user.sec_user_id, primary_sec_id)
            )
            await db.conn.commit()
            
            # Return the updated user's ID
            cursor = await db.conn.execute(
                "SELECT id FROM users WHERE uid = ?", (user.uid,)
            )
            row = await cursor.fetchone()
            return row[0]
    
    # No uid provided or no existing user with this uid - use normal upsert
    await db.conn.execute(
        """INSERT INTO users (sec_user_id, uid, nickname, avatar_url, signature,
            douyin_id, location, follower_count, following_count, total_favorited,
            aweme_count, is_verified, verification_type, extra_data, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sec_user_id) DO UPDATE SET
            uid=excluded.uid, nickname=excluded.nickname, avatar_url=excluded.avatar_url,
            signature=excluded.signature, douyin_id=excluded.douyin_id, location=excluded.location,
            follower_count=excluded.follower_count, following_count=excluded.following_count,
            total_favorited=excluded.total_favorited, aweme_count=excluded.aweme_count,
            is_verified=excluded.is_verified, verification_type=excluded.verification_type,
            extra_data=excluded.extra_data, updated_at=excluded.updated_at""",
        (user.sec_user_id, user.uid, user.nickname, user.avatar_url, user.signature,
         user.douyin_id, user.location, user.follower_count, user.following_count,
         user.total_favorited, user.aweme_count, user.is_verified, user.verification_type,
         user.extra_data, now),
    )
    await db.conn.commit()
    cursor = await db.conn.execute(
        "SELECT id FROM users WHERE sec_user_id = ?", (user.sec_user_id,)
    )
    row = await cursor.fetchone()
    return row[0]


async def get_user(sec_user_id: str) -> User | None:
    """Get user by sec_user_id."""
    cursor = await db.conn.execute(
        "SELECT * FROM users WHERE sec_user_id = ?", (sec_user_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return User(**dict(row))


async def get_user_by_uid(uid: str) -> User | None:
    """Get user by uid (the real unique identifier).
    
    This is useful when the same user might have multiple sec_user_ids.
    """
    cursor = await db.conn.execute(
        "SELECT * FROM users WHERE uid = ? ORDER BY updated_at DESC LIMIT 1",
        (uid,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return User(**dict(row))


async def get_users(page: int = 1, size: int = 20, sort_by: str = "updated_at", sort_order: str = "DESC") -> list[User]:
    """Get users with pagination and sorting."""
    allowed_sort_by = {"updated_at", "nickname", "follower_count", "total_favorited", "aweme_count"}
    if sort_by not in allowed_sort_by:
        sort_by = "updated_at"
    if sort_order.upper() not in ("ASC", "DESC"):
        sort_order = "DESC"

    offset = (page - 1) * size
    cursor = await db.conn.execute(
        f"SELECT * FROM users ORDER BY {sort_by} {sort_order.upper()} LIMIT ? OFFSET ?",
        (size, offset)
    )
    rows = await cursor.fetchall()
    return [User(**dict(r)) for r in rows]


async def count_users() -> int:
    cursor = await db.conn.execute("SELECT COUNT(*) FROM users")
    row = await cursor.fetchone()
    return row[0]


async def search_users_local(keyword: str, limit: int = 20) -> list[User]:
    """Search local users by nickname or douyin_id."""
    cursor = await db.conn.execute(
        "SELECT * FROM users WHERE nickname LIKE ? OR douyin_id LIKE ? ORDER BY follower_count DESC LIMIT ?",
        (f"%{keyword}%", f"%{keyword}%", limit),
    )
    rows = await cursor.fetchall()
    return [User(**dict(r)) for r in rows]


async def get_delete_preview(sec_user_ids: list[str] | None = None, cascade: bool = True, uids: list[str] | None = None) -> dict:
    """Get preview of what will be deleted.

    Args:
        sec_user_ids: List of sec_user_ids to delete (fallback)
        cascade: Whether to cascade delete related data
        uids: List of uids to delete (preferred, more reliable)
    """
    # Prefer uids over sec_user_ids
    if uids:
        user_count = len(uids)
    elif sec_user_ids:
        user_count = len(sec_user_ids)
    else:
        user_count = 0

    result = {
        "users_count": user_count,
        "works_count": 0,
        "comments_count": 0,
        "favorites_count": 0,
    }

    if not cascade or user_count == 0:
        return result

    if uids:
        # Use uid-based queries (more reliable)
        placeholders = ",".join("?" * len(uids))

        # Count works
        cursor = await db.conn.execute(
            f"SELECT COUNT(*) FROM works WHERE uid IN ({placeholders})",
            uids
        )
        result["works_count"] = (await cursor.fetchone())[0]

        # Count comments for those works
        cursor = await db.conn.execute(
            f"SELECT COUNT(*) FROM comments WHERE aweme_id IN (SELECT aweme_id FROM works WHERE uid IN ({placeholders}))",
            uids
        )
        result["comments_count"] = (await cursor.fetchone())[0]

        # Count favorites
        cursor = await db.conn.execute(
            f"SELECT COUNT(*) FROM favorites WHERE aweme_id IN (SELECT aweme_id FROM works WHERE uid IN ({placeholders}))",
            uids
        )
        result["favorites_count"] = (await cursor.fetchone())[0]
    else:
        # Fallback to sec_user_id-based queries
        placeholders = ",".join("?" * len(sec_user_ids))

        # Count works
        cursor = await db.conn.execute(
            f"SELECT COUNT(*) FROM works WHERE sec_user_id IN ({placeholders})",
            sec_user_ids
        )
        result["works_count"] = (await cursor.fetchone())[0]

        # Count comments for those works
        cursor = await db.conn.execute(
            f"SELECT COUNT(*) FROM comments WHERE aweme_id IN (SELECT aweme_id FROM works WHERE sec_user_id IN ({placeholders}))",
            sec_user_ids
        )
        result["comments_count"] = (await cursor.fetchone())[0]

        # Count favorites
        cursor = await db.conn.execute(
            f"SELECT COUNT(*) FROM favorites WHERE sec_user_id IN ({placeholders})",
            sec_user_ids
        )
        result["favorites_count"] = (await cursor.fetchone())[0]

    return result


async def delete_user(sec_user_id: str | None = None, cascade: bool = False, uid: str | None = None):
    """Delete a user. If cascade=True, also delete their works, comments, media files.

    Args:
        sec_user_id: User's sec_user_id (fallback)
        cascade: Whether to cascade delete related data
        uid: User's real uid (preferred, more reliable)
    """
    if cascade:
        # Get all aweme_ids for this user
        if uid:
            cursor = await db.conn.execute(
                "SELECT aweme_id FROM works WHERE uid = ?", (uid,)
            )
        else:
            cursor = await db.conn.execute(
                "SELECT aweme_id FROM works WHERE sec_user_id = ?", (sec_user_id,)
            )
        aweme_ids = [row[0] for row in await cursor.fetchall()]
        # Delete comments and media for those works
        for aid in aweme_ids:
            await db.conn.execute("DELETE FROM comments WHERE aweme_id = ?", (aid,))
            await db.conn.execute("DELETE FROM media_files WHERE aweme_id = ?", (aid,))
        # Delete works
        if uid:
            await db.conn.execute("DELETE FROM works WHERE uid = ?", (uid,))
        else:
            await db.conn.execute("DELETE FROM works WHERE sec_user_id = ?", (sec_user_id,))
    if uid:
        await db.conn.execute("DELETE FROM users WHERE uid = ?", (uid,))
    else:
        await db.conn.execute("DELETE FROM users WHERE sec_user_id = ?", (sec_user_id,))
    await db.conn.commit()


async def delete_users_batch(sec_user_ids: list[str] | None = None, cascade: bool = False, uids: list[str] | None = None):
    """Delete multiple users.

    Args:
        sec_user_ids: List of sec_user_ids to delete (fallback)
        cascade: Whether to cascade delete related data
        uids: List of uids to delete (preferred, more reliable)
    """
    if uids:
        for user_uid in uids:
            await delete_user(uid=user_uid, cascade=cascade)
    elif sec_user_ids:
        for sid in sec_user_ids:
            await delete_user(sec_user_id=sid, cascade=cascade)


# ── Works ──

async def upsert_work(work: Work) -> int:
    now = datetime.now().isoformat()
    params = (work.aweme_id, work.uid, work.sec_user_id, work.type, work.title, work.cover_url,
              work.duration, work.digg_count, work.comment_count, work.share_count,
              work.collect_count, work.play_count, work.hashtags, work.music_title,
              work.publish_time.isoformat() if work.publish_time else None, work.extra_data, now)
    logger.debug(f"upsert_work: aweme_id={work.aweme_id}, params_count={len(params)}")
    await db.conn.execute(
        """INSERT INTO works (aweme_id, uid, sec_user_id, type, title, cover_url, duration,
            digg_count, comment_count, share_count, collect_count, play_count,
            hashtags, music_title, publish_time, extra_data, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(aweme_id) DO UPDATE SET
            uid=excluded.uid, sec_user_id=excluded.sec_user_id,
            title=excluded.title, cover_url=excluded.cover_url, duration=excluded.duration,
            digg_count=excluded.digg_count, comment_count=excluded.comment_count,
            share_count=excluded.share_count, collect_count=excluded.collect_count,
            play_count=excluded.play_count, hashtags=excluded.hashtags,
            music_title=excluded.music_title, publish_time=excluded.publish_time,
            extra_data=excluded.extra_data, updated_at=excluded.updated_at""",
        params,
    )
    await db.conn.commit()
    cursor = await db.conn.execute(
        "SELECT id FROM works WHERE aweme_id = ?", (work.aweme_id,)
    )
    row = await cursor.fetchone()
    return row[0]


async def get_work(aweme_id: str) -> Work | None:
    cursor = await db.conn.execute(
        "SELECT * FROM works WHERE aweme_id = ?", (aweme_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return Work(**dict(row))


def _build_filter_conditions(
    sec_user_id: str | None,
    work_type: str | None,
    start_date: str | None,
    end_date: str | None,
    has_comments: bool | None,
    has_media: bool | None,
    has_transcript: bool | None,
    uid: str | None = None,  # Filter by author's real uid (more reliable)
) -> tuple[list[str], list]:
    """Build shared WHERE conditions for get_works / count_works."""
    conditions: list[str] = []
    params: list = []
    if uid:
        # Prefer uid for filtering (more stable than sec_user_id)
        conditions.append("uid = ?")
        params.append(uid)
    elif sec_user_id:
        # Fallback to sec_user_id if uid not provided
        conditions.append("sec_user_id = ?")
        params.append(sec_user_id)
    if work_type:
        conditions.append("type = ?")
        params.append(work_type)
    if start_date:
        conditions.append("publish_time >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("publish_time <= ?")
        params.append(end_date + " 23:59:59")
    if has_transcript is True:
        conditions.append("transcript IS NOT NULL AND transcript != ''")
    elif has_transcript is False:
        conditions.append("(transcript IS NULL OR transcript = '')")
    if has_comments is True:
        conditions.append("EXISTS (SELECT 1 FROM comments WHERE comments.aweme_id = works.aweme_id)")
    elif has_comments is False:
        conditions.append("NOT EXISTS (SELECT 1 FROM comments WHERE comments.aweme_id = works.aweme_id)")
    if has_media is True:
        conditions.append("EXISTS (SELECT 1 FROM media_files WHERE media_files.aweme_id = works.aweme_id AND download_status = 'completed')")
    elif has_media is False:
        conditions.append("NOT EXISTS (SELECT 1 FROM media_files WHERE media_files.aweme_id = works.aweme_id AND download_status = 'completed')")
    return conditions, params


async def get_works(
    sec_user_id: str | None = None,
    uid: str | None = None,  # Prefer uid for more reliable filtering
    work_type: str | None = None,
    page: int = 1,
    size: int = 20,
    sort_by: str = "publish_time",
    sort_order: str = "DESC",
    start_date: str | None = None,
    end_date: str | None = None,
    has_comments: bool | None = None,
    has_media: bool | None = None,
    has_transcript: bool | None = None,
) -> list[Work]:
    allowed_sort_by = {"publish_time", "digg_count", "play_count", "comment_count", "collect_count", "created_at"}
    if sort_by not in allowed_sort_by:
        sort_by = "publish_time"
    if sort_order.upper() not in ("ASC", "DESC"):
        sort_order = "DESC"
    conditions, params = _build_filter_conditions(
        sec_user_id, work_type, start_date, end_date, has_comments, has_media, has_transcript, uid,
    )
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    offset = (page - 1) * size
    cursor = await db.conn.execute(
        f"SELECT * FROM works{where} ORDER BY {sort_by} {sort_order.upper()} LIMIT ? OFFSET ?",
        params + [size, offset],
    )
    rows = await cursor.fetchall()
    return [Work(**dict(r)) for r in rows]


async def get_works_by_author_uid(author_uid: str, page: int = 1, size: int = 20) -> list[Work]:
    """Get works by author's real uid (more reliable than sec_user_id).
    
    This is useful when the same author might have multiple sec_user_ids.
    It queries both the sec_user_id field and the author_uid in extra_data (JSON).
    
    Args:
        author_uid: The author's real uid (e.g., "7123456789")
        page: Page number (default 1)
        size: Page size (default 20)
    
    Returns:
        List of works by this author
    """
    offset = (page - 1) * size
    cursor = await db.conn.execute(
        """SELECT * FROM works 
        WHERE sec_user_id IN (SELECT sec_user_id FROM users WHERE uid = ?)
           OR json_extract(extra_data, '$.author_uid') = ?
        ORDER BY publish_time DESC
        LIMIT ? OFFSET ?""",
        (author_uid, author_uid, size, offset),
    )
    rows = await cursor.fetchall()
    return [Work(**dict(r)) for r in rows]


async def count_works_by_author_uid(author_uid: str) -> int:
    """Count total works by author's real uid."""
    cursor = await db.conn.execute(
        """SELECT COUNT(*) FROM works 
        WHERE sec_user_id IN (SELECT sec_user_id FROM users WHERE uid = ?)
           OR json_extract(extra_data, '$.author_uid') = ?""",
        (author_uid, author_uid),
    )
    row = await cursor.fetchone()
    return row[0]


async def count_works(
    sec_user_id: str | None = None,
    uid: str | None = None,  # Prefer uid for more reliable counting
    work_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    has_comments: bool | None = None,
    has_media: bool | None = None,
    has_transcript: bool | None = None,
) -> int:
    conditions, params = _build_filter_conditions(
        sec_user_id, work_type, start_date, end_date, has_comments, has_media, has_transcript, uid,
    )
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    cursor = await db.conn.execute(f"SELECT COUNT(*) FROM works{where}", params)
    row = await cursor.fetchone()
    return row[0]


async def delete_work(aweme_id: str):
    """Delete a work and its comments and media files."""
    await db.conn.execute("DELETE FROM comments WHERE aweme_id = ?", (aweme_id,))
    await db.conn.execute("DELETE FROM media_files WHERE aweme_id = ?", (aweme_id,))
    await db.conn.execute("DELETE FROM works WHERE aweme_id = ?", (aweme_id,))
    await db.conn.commit()


async def delete_works_batch(aweme_ids: list[str]):
    """Delete multiple works."""
    for aid in aweme_ids:
        await delete_work(aid)


async def update_work_transcript(aweme_id: str, transcript: str):
    """Update the transcript field for a work."""
    now = datetime.now().isoformat()
    await db.conn.execute(
        "UPDATE works SET transcript = ?, updated_at = ? WHERE aweme_id = ?",
        (transcript, now, aweme_id),
    )
    await db.conn.commit()


# ── Media Files ──

async def upsert_media_file(mf: MediaFile) -> int:
    """Insert or update media file. Uses (aweme_id, media_type) as unique key."""
    cursor = await db.conn.execute(
        """INSERT INTO media_files (aweme_id, media_type, url, local_path, file_size, download_status, retry_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(aweme_id, media_type) DO UPDATE SET
            url=excluded.url, local_path=excluded.local_path,
            file_size=excluded.file_size, download_status=excluded.download_status,
            retry_count=excluded.retry_count""",
        (mf.aweme_id, mf.media_type, mf.url, mf.local_path, mf.file_size, mf.download_status, mf.retry_count or 0),
    )
    await db.conn.commit()
    return cursor.lastrowid


async def create_media_file(mf: MediaFile) -> int:
    """Deprecated: Use upsert_media_file instead. Kept for backward compatibility."""
    return await upsert_media_file(mf)


async def update_media_file(file_id: int, **kwargs):
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [file_id]
    await db.conn.execute(f"UPDATE media_files SET {sets} WHERE id = ?", vals)
    await db.conn.commit()


async def get_media_files(aweme_id: str) -> list[MediaFile]:
    cursor = await db.conn.execute(
        "SELECT * FROM media_files WHERE aweme_id = ?", (aweme_id,)
    )
    rows = await cursor.fetchall()
    return [MediaFile(**dict(r)) for r in rows]


async def get_pending_media_files(limit: int = 10) -> list[MediaFile]:
    cursor = await db.conn.execute(
        "SELECT * FROM media_files WHERE download_status IN ('pending', 'failed') AND retry_count < 3 LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    return [MediaFile(**dict(r)) for r in rows]


async def count_media_files() -> int:
    cursor = await db.conn.execute("SELECT COUNT(*) FROM media_files")
    row = await cursor.fetchone()
    return row[0]


# ── Tasks ──

async def create_task(task: Task) -> int:
    cursor = await db.conn.execute(
        """INSERT INTO tasks (task_type, target, params, status, priority, max_retries, is_scheduled, schedule_interval, next_run_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (task.task_type, task.target, task.params, task.status, task.priority, task.max_retries,
         task.is_scheduled, task.schedule_interval,
         task.next_run_at.isoformat() if task.next_run_at else None),
    )
    await db.conn.commit()
    return cursor.lastrowid


async def update_task(task_id: int, **kwargs):
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [task_id]
    await db.conn.execute(f"UPDATE tasks SET {sets} WHERE id = ?", vals)
    await db.conn.commit()


async def get_task(task_id: int) -> Task | None:
    cursor = await db.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = await cursor.fetchone()
    if row is None:
        return None
    return Task(**dict(row))


async def get_tasks(
    status: str | None = None,
    task_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    page: int = 1,
    size: int = 20
) -> list[Task]:
    conditions = []
    params: list = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if task_type:
        conditions.append("task_type = ?")
        params.append(task_type)
    if start_date:
        conditions.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("created_at <= ?")
        params.append(end_date + " 23:59:59")
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    offset = (page - 1) * size
    cursor = await db.conn.execute(
        f"SELECT * FROM tasks{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [size, offset],
    )
    rows = await cursor.fetchall()
    return [Task(**dict(r)) for r in rows]


async def get_next_pending_task() -> Task | None:
    """Atomically get and lock the next pending task to prevent race conditions.

    Uses a transaction with immediate UPDATE to ensure only one worker
    can claim a task at a time.
    """
    # Use atomic UPDATE with RETURNING to prevent race conditions
    # Set status to 'running' immediately to prevent other workers from picking it up
    cursor = await db.conn.execute(
        """UPDATE tasks
           SET status = 'running', started_at = ?
           WHERE id = (
               SELECT id FROM tasks
               WHERE status = 'pending'
               ORDER BY priority DESC, created_at ASC
               LIMIT 1
           )
           RETURNING *""",
        (datetime.now().isoformat(),)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    await db.conn.commit()
    return Task(**dict(row))


async def reset_running_tasks():
    """Reset tasks that were running when the server stopped."""
    await db.conn.execute("UPDATE tasks SET status = 'pending' WHERE status = 'running'")
    await db.conn.commit()


async def count_tasks(
    status: str | None = None,
    task_type: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None
) -> int:
    conditions = []
    params: list = []
    if status:
        conditions.append("status = ?")
        params.append(status)
    if task_type:
        conditions.append("task_type = ?")
        params.append(task_type)
    if start_date:
        conditions.append("created_at >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("created_at <= ?")
        params.append(end_date + " 23:59:59")
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    cursor = await db.conn.execute(f"SELECT COUNT(*) FROM tasks{where}", params)
    row = await cursor.fetchone()
    return row[0]


async def delete_tasks_batch(task_ids: list[int]):
    """Delete multiple tasks by their IDs."""
    for tid in task_ids:
        await db.conn.execute("DELETE FROM tasks WHERE id = ?", (tid,))
    await db.conn.commit()


async def update_task_priority(task_id: int, priority: int):
    """Update a task's priority."""
    await db.conn.execute("UPDATE tasks SET priority = ? WHERE id = ?", (priority, task_id))
    await db.conn.commit()


async def delete_task(task_id: int):
    """Delete a task by ID."""
    await db.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    await db.conn.commit()


# ── Sessions ──

async def save_session(session: Session):
    now = datetime.now().isoformat()
    await db.conn.execute(
        """INSERT INTO sessions (name, cookies, user_agent, is_active, last_used_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
            cookies=excluded.cookies, user_agent=excluded.user_agent,
            is_active=excluded.is_active, last_used_at=excluded.last_used_at""",
        (session.name, session.cookies, session.user_agent, session.is_active, now),
    )
    await db.conn.commit()


async def get_session(name: str) -> Session | None:
    cursor = await db.conn.execute(
        "SELECT * FROM sessions WHERE name = ? AND is_active = 1", (name,)
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return Session(**dict(row))


# ── Comments ──

async def upsert_comment(comment: Comment) -> int:
    await db.conn.execute(
        """INSERT INTO comments (comment_id, aweme_id, user_nickname, user_sec_uid,
            user_avatar, content, digg_count, reply_count, reply_to, create_time, ip_label, extra_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(comment_id) DO UPDATE SET
            digg_count=excluded.digg_count,
            reply_count=excluded.reply_count,
            content=excluded.content,
            reply_to=excluded.reply_to""",
        (comment.comment_id, comment.aweme_id, comment.user_nickname,
         comment.user_sec_uid, comment.user_avatar, comment.content,
         comment.digg_count, comment.reply_count, comment.reply_to, comment.create_time,
         comment.ip_label, comment.extra_data),
    )
    await db.conn.commit()
    cursor = await db.conn.execute("SELECT last_insert_rowid()")
    row = await cursor.fetchone()
    return row[0]


async def get_comments(aweme_id: str, page: int = 1, size: int = 50) -> list[Comment]:
    offset = (page - 1) * size
    cursor = await db.conn.execute(
        "SELECT * FROM comments WHERE aweme_id = ? ORDER BY create_time DESC LIMIT ? OFFSET ?",
        (aweme_id, size, offset),
    )
    rows = await cursor.fetchall()
    return [Comment(**dict(r)) for r in rows]


async def count_comments(aweme_id: str) -> int:
    cursor = await db.conn.execute(
        "SELECT COUNT(*) FROM comments WHERE aweme_id = ?", (aweme_id,)
    )
    row = await cursor.fetchone()
    return row[0]


async def count_user_comments(sec_user_id: str | None = None, uid: str | None = None) -> int:
    """Count all comments across all works of a user.

    Args:
        sec_user_id: User's sec_user_id (fallback)
        uid: User's real uid (preferred, more reliable)
    """
    if uid:
        # Prefer uid for filtering (more stable than sec_user_id)
        cursor = await db.conn.execute(
            "SELECT COUNT(*) FROM comments WHERE aweme_id IN (SELECT aweme_id FROM works WHERE uid = ?)",
            (uid,),
        )
    else:
        cursor = await db.conn.execute(
            "SELECT COUNT(*) FROM comments WHERE aweme_id IN (SELECT aweme_id FROM works WHERE sec_user_id = ?)",
            (sec_user_id,),
        )
    row = await cursor.fetchone()
    return row[0]


async def count_user_media(sec_user_id: str | None = None, uid: str | None = None) -> int:
    """Count all media files across all works of a user.

    Args:
        sec_user_id: User's sec_user_id (fallback)
        uid: User's real uid (preferred, more reliable)
    """
    if uid:
        # Prefer uid for filtering (more stable than sec_user_id)
        cursor = await db.conn.execute(
            "SELECT COUNT(*) FROM media_files WHERE aweme_id IN (SELECT aweme_id FROM works WHERE uid = ?)",
            (uid,),
        )
    else:
        cursor = await db.conn.execute(
            "SELECT COUNT(*) FROM media_files WHERE aweme_id IN (SELECT aweme_id FROM works WHERE sec_user_id = ?)",
            (sec_user_id,),
        )
    row = await cursor.fetchone()
    return row[0]


async def update_user_aweme_count(sec_user_id: str | None = None, uid: str | None = None) -> int:
    """Update user's aweme_count based on actual works in database.

    Args:
        sec_user_id: User's sec_user_id (fallback)
        uid: User's real uid (preferred, more reliable)

    Returns:
        The updated count
    """
    count = await count_works(sec_user_id=sec_user_id, uid=uid)
    if uid:
        await db.conn.execute(
            "UPDATE users SET aweme_count = ? WHERE uid = ?",
            (count, uid),
        )
    else:
        await db.conn.execute(
            "UPDATE users SET aweme_count = ? WHERE sec_user_id = ?",
            (count, sec_user_id),
        )
    await db.conn.commit()
    return count


# ── Scheduled Tasks ──

async def get_due_scheduled_tasks() -> list[Task]:
    """Get tasks that are scheduled and due to run."""
    from datetime import timedelta
    now = datetime.now().isoformat()
    cursor = await db.conn.execute(
        "SELECT * FROM tasks WHERE is_scheduled = 1 AND status IN ('pending', 'completed') AND (next_run_at IS NULL OR next_run_at <= ?)",
        (now,),
    )
    rows = await cursor.fetchall()
    return [Task(**dict(r)) for r in rows]


async def update_scheduled_task_next_run(task_id: int, interval_minutes: int):
    """Update the next run time for a scheduled task after execution."""
    from datetime import timedelta
    next_run = (datetime.now() + timedelta(minutes=interval_minutes)).isoformat()
    await db.conn.execute(
        "UPDATE tasks SET next_run_at = ?, status = 'pending' WHERE id = ?",
        (next_run, task_id)
    )
    await db.conn.commit()


# ── Favorites ──

async def add_favorite(aweme_id: str, sec_user_id: str | None = None) -> bool:
    """Add a work to favorites."""
    try:
        now = datetime.now().isoformat()
        await db.conn.execute(
            """INSERT INTO favorites (aweme_id, sec_user_id, created_at)
            VALUES (?, ?, ?)""",
            (aweme_id, sec_user_id, now),
        )
        await db.conn.commit()
        return True
    except Exception:
        # aweme_id already exists
        return False


async def remove_favorite(aweme_id: str) -> bool:
    """Remove a work from favorites."""
    cursor = await db.conn.execute(
        "DELETE FROM favorites WHERE aweme_id = ?", (aweme_id,)
    )
    await db.conn.commit()
    return cursor.rowcount > 0


async def is_favorite(aweme_id: str) -> bool:
    """Check if a work is in favorites."""
    cursor = await db.conn.execute(
        "SELECT 1 FROM favorites WHERE aweme_id = ?", (aweme_id,)
    )
    row = await cursor.fetchone()
    return row is not None


async def get_favorites(page: int = 1, size: int = 20) -> list[Favorite]:
    """Get all favorites with pagination.

    Uses uid for user association (more reliable than sec_user_id).
    """
    offset = (page - 1) * size
    cursor = await db.conn.execute(
        """SELECT f.*, w.title, w.cover_url, w.sec_user_id, w.uid as author_uid, u.nickname
        FROM favorites f
        LEFT JOIN works w ON f.aweme_id = w.aweme_id
        LEFT JOIN users u ON w.uid = u.uid
        ORDER BY f.created_at DESC
        LIMIT ? OFFSET ?""",
        (size, offset),
    )
    rows = await cursor.fetchall()
    return [Favorite(**dict(r)) for r in rows]


async def count_favorites() -> int:
    """Count total favorites."""
    cursor = await db.conn.execute("SELECT COUNT(*) FROM favorites")
    row = await cursor.fetchone()
    return row[0]


# ── Scheduled Tasks (Pagination) ──

async def get_scheduled_tasks(page: int = 1, size: int = 20, status: str | None = None) -> list[Task]:
    """Get scheduled tasks with pagination.

    Args:
        page: Page number (1-indexed)
        size: Number of items per page
        status: Filter by status (e.g., 'pending', 'running', 'completed', 'failed')

    Returns:
        List of scheduled tasks
    """
    offset = (page - 1) * size
    sql = "SELECT * FROM tasks WHERE is_scheduled = 1"
    params = []
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY next_run_at ASC LIMIT ? OFFSET ?"
    params.extend([size, offset])
    cursor = await db.conn.execute(sql, params)
    rows = await cursor.fetchall()
    return [Task(**dict(r)) for r in rows]


async def count_scheduled_tasks(status: str | None = None) -> int:
    """Count scheduled tasks.

    Args:
        status: Filter by status (e.g., 'pending', 'running', 'completed', 'failed')

    Returns:
        Total count of scheduled tasks matching the filter
    """
    sql = "SELECT COUNT(*) FROM tasks WHERE is_scheduled = 1"
    params = []
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    cursor = await db.conn.execute(sql, params)
    result = await cursor.fetchone()
    return result[0] if result else 0
