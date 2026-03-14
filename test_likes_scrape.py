"""测试脚本：检查喜欢列表能抓取多少数据"""
import asyncio
import sys
from backend.scraper.engine import engine
from backend.scraper.user_scraper import UserScraper

async def test_likes():
    """测试喜欢列表抓取"""
    await engine.start()
    print("✅ 引擎已启动")

    scraper = UserScraper()
    sec_user_id = "MS4wLjABAAAAUkV7eU2KngYX8Q4yR_jAsgLc5KgBb7cNn6Os04uyIFU"

    # 使用一个固定的 task_id
    task_id = 99999

    try:
        print("\n🔄 开始抓取喜欢列表...")
        works = await scraper.scrape_likes(
            task_id=task_id,
            sec_user_id=sec_user_id,
            max_pages=20,  # 最多抓取20页
            on_page=lambda page, total: print(f"📄 第 {page} 页")
        )

        print(f"\n✅ 抓取完成！")
        print(f"📊 总共抓取 {len(works)} 个视频")

        # 检查是否有重复的 aweme_id
        aweme_ids = [w.aweme_id for w in works]
        unique_ids = set(aweme_ids)
        print(f"🔍 唯一视频数: {len(unique_ids)}")

        if len(aweme_ids) != len(unique_ids):
            print(f"⚠️ 发现 {len(aweme_ids) - len(unique_ids)} 个重复视频")

    finally:
        await engine.stop()
        print("\n✅ 引擎已停止")

if __name__ == "__main__":
    asyncio.run(test_likes())
