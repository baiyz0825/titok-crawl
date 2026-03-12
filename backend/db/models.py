from datetime import datetime
from pydantic import BaseModel


class User(BaseModel):
    id: int | None = None
    sec_user_id: str
    uid: str | None = None
    nickname: str | None = None
    avatar_url: str | None = None
    signature: str | None = None
    douyin_id: str | None = None
    location: str | None = None
    follower_count: int = 0
    following_count: int = 0
    total_favorited: int = 0
    aweme_count: int = 0
    is_verified: bool = False
    verification_type: str | None = None
    extra_data: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Work(BaseModel):
    id: int | None = None
    aweme_id: str
    sec_user_id: str
    type: str  # 'video' or 'note'
    title: str | None = None
    cover_url: str | None = None
    duration: int | None = None
    digg_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    collect_count: int = 0
    play_count: int = 0
    hashtags: str | None = None  # JSON array string
    music_title: str | None = None
    publish_time: datetime | None = None
    transcript: str | None = None
    extra_data: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MediaFile(BaseModel):
    id: int | None = None
    aweme_id: str
    media_type: str  # 'video', 'image', 'cover'
    url: str
    local_path: str | None = None
    file_size: int | None = None
    download_status: str = "pending"
    retry_count: int = 0
    created_at: datetime | None = None


class Task(BaseModel):
    id: int | None = None
    task_type: str
    target: str
    params: str | None = None  # JSON string
    status: str = "pending"
    priority: int = 0
    progress: float = 0.0
    result: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Session(BaseModel):
    id: int | None = None
    name: str
    cookies: str  # JSON string
    user_agent: str | None = None
    is_active: bool = True
    last_used_at: datetime | None = None
    created_at: datetime | None = None


class Comment(BaseModel):
    id: int | None = None
    comment_id: str
    aweme_id: str
    user_nickname: str | None = None
    user_sec_uid: str | None = None
    user_avatar: str | None = None
    content: str | None = None
    digg_count: int = 0
    reply_count: int = 0
    reply_to: str | None = None  # parent comment_id, null for top-level
    create_time: datetime | None = None
    ip_label: str | None = None
    extra_data: str | None = None
    created_at: datetime | None = None


class Schedule(BaseModel):
    id: int | None = None
    sec_user_id: str
    nickname: str | None = None
    sync_type: str = "all"  # profile, works, all
    interval_minutes: int = 1440  # default 24h
    enabled: bool = True
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    created_at: datetime | None = None


# API request/response schemas

class ScrapeOptions(BaseModel):
    """Selective data collection options."""
    profile: bool = True
    works: bool = True
    comments: bool = False
    video_cover: bool = True
    video_data: bool = False
    images: bool = False
    stats: bool = True


class ScrapeRequest(BaseModel):
    sec_user_id: str
    scrape_works: bool = True
    download_media: bool = False
    max_pages: int | None = None
    collect_options: ScrapeOptions | None = None


class SearchRequest(BaseModel):
    keyword: str
    search_type: str = "user"  # 'user' or 'work'


class PaginationParams(BaseModel):
    page: int = 1
    size: int = 20
