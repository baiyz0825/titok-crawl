import json
import logging
from datetime import datetime

import pandas as pd

from backend.db.database import db
from backend.db import crud

logger = logging.getLogger(__name__)


class UserAnalyzer:
    async def analyze_user(self, sec_user_id: str) -> dict:
        """Generate analysis report for a user."""
        user = await crud.get_user(sec_user_id)
        if not user:
            return {"error": "User not found"}

        # Fetch all works
        works = await crud.get_works(sec_user_id=sec_user_id, page=1, size=9999)
        if not works:
            return {
                "user": user.model_dump(),
                "works_count": 0,
                "message": "No works data available",
            }

        # Convert to DataFrame
        df = pd.DataFrame([w.model_dump() for w in works])

        # Basic stats
        video_count = len(df[df["type"] == "video"])
        note_count = len(df[df["type"] == "note"])

        # Engagement stats
        engagement = {
            "avg_digg": round(df["digg_count"].mean(), 1),
            "avg_comment": round(df["comment_count"].mean(), 1),
            "avg_share": round(df["share_count"].mean(), 1),
            "avg_collect": round(df["collect_count"].mean(), 1),
            "max_digg": int(df["digg_count"].max()),
            "total_digg": int(df["digg_count"].sum()),
        }

        # Publishing frequency
        if "publish_time" in df.columns and df["publish_time"].notna().any():
            df["publish_time"] = pd.to_datetime(df["publish_time"], errors="coerce")
            valid = df[df["publish_time"].notna()].sort_values("publish_time")
            if len(valid) > 1:
                time_span = (valid["publish_time"].max() - valid["publish_time"].min()).days
                frequency = round(len(valid) / max(time_span, 1) * 7, 1)  # works per week
            else:
                frequency = 0
        else:
            frequency = 0

        return {
            "user": {
                "nickname": user.nickname,
                "sec_user_id": user.sec_user_id,
                "follower_count": user.follower_count,
                "total_favorited": user.total_favorited,
            },
            "works_summary": {
                "total": len(works),
                "videos": video_count,
                "notes": note_count,
                "video_ratio": round(video_count / len(works) * 100, 1) if works else 0,
            },
            "engagement": engagement,
            "publishing_frequency_per_week": frequency,
        }

    async def get_overview(self) -> dict:
        """Get system overview statistics."""
        return {
            "users_count": await crud.count_users(),
            "works_count": await crud.count_works(),
            "media_files_count": await crud.count_media_files(),
            "tasks": {
                "total": await crud.count_tasks(),
                "pending": await crud.count_tasks("pending"),
                "running": await crud.count_tasks("running"),
                "completed": await crud.count_tasks("completed"),
                "failed": await crud.count_tasks("failed"),
            },
        }


analyzer = UserAnalyzer()
