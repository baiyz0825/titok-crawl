import os
from pathlib import Path


class Settings:
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / "data"

    # Database
    DB_PATH = DATA_DIR / "db" / "douyin.db"

    # Media storage
    MEDIA_DIR = DATA_DIR / "media"

    # Playwright browser
    HEADLESS = os.environ.get("HEADLESS", "false").lower() in ("true", "1", "yes")
    BROWSER_DATA_DIR = DATA_DIR / "browser"
    PAGE_TIMEOUT = 30000  # 30 seconds default timeout for page operations

    # Request control
    MIN_DELAY = 3.0
    MAX_DELAY = 6.0
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 30

    # Log file
    LOG_FILE = DATA_DIR / "logs" / "app.jsonl"

    # Task queue
    # 降低并发任务数以减少资源占用和页面卡顿
    # 可通过环境变量 MAX_CONCURRENT_TASKS 调整（推荐值：1-5）
    MAX_CONCURRENT_TASKS = int(os.environ.get("MAX_CONCURRENT_TASKS", "3"))

    # 任务内并行控制
    MAX_SUBPAGES_PER_TASK = int(os.environ.get("MAX_SUBPAGES_PER_TASK", "3"))  # 每个任务最大子页面数
    MAX_CONCURRENT_DOWNLOADS = int(os.environ.get("MAX_CONCURRENT_DOWNLOADS", "3"))  # 并行下载数
    MAX_CONCURRENT_COMMENTS = int(os.environ.get("MAX_CONCURRENT_COMMENTS", "2"))  # 并行评论采集数
    MAX_CONCURRENT_REFRESH = int(os.environ.get("MAX_CONCURRENT_REFRESH", "2"))  # 并行作品刷新数

    # Server ports (从环境变量读取，支持高位端口避免冲突)
    API_HOST = "0.0.0.0"
    API_PORT = int(os.environ.get("BACKEND_PORT", "18000"))
    MCP_PORT = int(os.environ.get("MCP_PORT", "18001"))

    # Douyin
    DOUYIN_BASE_URL = "https://www.douyin.com"
    API_PATTERN = "**/aweme/v1/web/**"

    # Favorites
    AUTO_ADD_TO_FAVORITES = os.environ.get("AUTO_ADD_TO_FAVORITES", "true").lower() in ("true", "1", "yes")

    @classmethod
    def ensure_dirs(cls):
        """Create required directories if they don't exist."""
        cls.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        cls.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        cls.BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
