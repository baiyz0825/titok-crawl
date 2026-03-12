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
    MAX_CONCURRENT_TASKS = 1

    # Server ports
    API_HOST = "0.0.0.0"
    API_PORT = 8000
    MCP_PORT = 8001

    # Douyin
    DOUYIN_BASE_URL = "https://www.douyin.com"
    API_PATTERN = "**/aweme/v1/web/**"

    @classmethod
    def ensure_dirs(cls):
        """Create required directories if they don't exist."""
        cls.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        cls.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
        cls.BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
