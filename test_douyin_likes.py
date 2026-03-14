"""使用 Playwright 手动分析抖音喜欢列表 API"""
import asyncio
import json
from playwright.async_api import async_playwright

async def analyze_likes_api():
    """详细分析抖音喜欢列表的API调用"""
    async with async_playwright() as p:
        print("🚀 启动浏览器...")

        # 使用持久化上下文，保留登录状态
        browser = await p.chromium.launch_persistent_context(
            user_data_dir="data/browser",
            headless=False,
            viewport={"width": 1280, "height": 720},
        )

        # 创建新页面
        page = await browser.new_page()

        # 存储所有拦截到的 API
        api_calls = []

        async def handle_response(response):
            """拦截所有响应"""
            url = response.url
            if "aweme/favorite" in url or "aweme/v1/web" in url:
                try:
                    data = await response.json()
                    api_calls.append({
                        "url": url,
                        "status": response.status,
                        "data": data
                    })
                    print(f"\n📡 拦截到 API #{len(api_calls)}")
                    print(f"   URL: {url[:200]}...")

                    # 分析响应
                    if "aweme_list" in data:
                        count = len(data.get("aweme_list", []))
                        print(f"   📦 返回 {count} 个视频")

                    # 打印所有关键字段
                    for key in sorted(data.keys()):
                        if key not in ["aweme_list", "author_user_info"]:
                            print(f"   🔑 {key}: {data[key]}")

                except Exception as e:
                    print(f"   ❌ 解析失败: {e}")

        page.on("response", handle_response)

        # 导航到喜欢列表
        print("\n🌐 导航到喜欢列表...")
        await page.goto("https://www.douyin.com/user/self?showTab=like", wait_until="networkidle")
        await asyncio.sleep(3)

        print(f"\n✅ 初始加载完成，已拦截 {len(api_calls)} 个 API")

        # 手动滚动，观察API调用
        for i in range(10):
            print(f"\n{'='*80}")
            print(f"📜 第 {i+1} 次滚动")
            print('='*80)

            # 多阶段滚动
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight - 800)")
            await asyncio.sleep(2)

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)

            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(2)

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(4)

            print(f"   当前已拦截 {len(api_calls)} 个 API")

            # 如果3秒内没有新API，可能到底了
            if i >= 2:
                recent_count = sum(1 for call in api_calls if call.get("_timestamp", 0) > asyncio.get_event_loop().time() - 10)
                if recent_count == 0:
                    print("   ⚠️ 最近10秒没有新API，可能已到底")
                    break

        # 分析结果
        print(f"\n{'='*80}")
        print("📊 最终分析结果")
        print('='*80)

        print(f"\n总 API 调用数: {len(api_calls)}")

        total_videos = 0
        for idx, call in enumerate(api_calls):
            aweme_list = call["data"].get("aweme_list", [])
            total_videos += len(aweme_list)
            print(f"\nAPI #{idx+1}:")
            print(f"  - 视频数: {len(aweme_list)}")

            # 检查关键字段
            data = call["data"]
            if "max_cursor" in data:
                print(f"  - max_cursor: {data['max_cursor']}")
            if "has_more" in data:
                print(f"  - has_more: {data['has_more']}")

        print(f"\n累计视频数: {total_videos}")

        # 保持浏览器打开，供手动检查
        print(f"\n⏸️ 浏览器将保持打开，请手动检查...")
        print(f"   按 Ctrl+C 退出")

        try:
            await asyncio.sleep(300)  # 保持5分钟
        except KeyboardInterrupt:
            pass

        await browser.close()
        print("\n✅ 浏览器已关闭")

if __name__ == "__main__":
    asyncio.run(analyze_likes_api())
