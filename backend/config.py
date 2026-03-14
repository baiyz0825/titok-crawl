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

    # Request control
    MIN_DELAY = 3.0
    MAX_DELAY = 6.0
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 30

    # Log file
    LOG_FILE = DATA_DIR / "logs" / "app.jsonl"

    # Task queue
    MAX_CONCURRENT_TASKS = 10  # 支持同时执行10个任务

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
