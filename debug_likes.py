"""临时脚本：检查抖音喜欢列表的实际数据量"""
import asyncio
import json
from playwright.async_api import async_playwright

async def check_likes_api():
    """使用 Playwright 检查喜欢列表API"""
    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.86 Safari/537.36"
        )

        # 加载已保存的 cookies
        try:
            with open("data/browser/cookies.json", "r") as f:
                cookies = json.load(f)
                await context.add_cookies(cookies)
                print("✅ 已加载登录 cookies")
        except Exception as e:
            print(f"❌ 无法加载 cookies: {e}")
            await browser.close()
            return

        # 创建页面并监听网络请求
        page = await context.new_page()

        # 存储拦截到的API响应
        api_responses = []

        async def handle_response(response):
            try:
                if "aweme/favorite" in response.url:
                    print(f"\n📡 拦截到 API: {response.url[:150]}...")
                    data = await response.json()
                    api_responses.append(data)

                    aweme_list = data.get("aweme_list", [])
                    print(f"   └─ 返回 {len(aweme_list)} 个视频")

                    # 检查是否有更多数据的标记
                    if "max_cursor" in data:
                        print(f"   └─ max_cursor: {data['max_cursor']}")

                    if "has_more" in data:
                        print(f"   └─ has_more: {data['has_more']}")

            except Exception as e:
                pass

        page.on("response", handle_response)

        # 导航到喜欢列表页面
        print("\n🌐 导航到喜欢列表页面...")
        await page.goto("https://www.douyin.com/user/self?showTab=like", wait_until="domcontentloaded")
        await asyncio.sleep(3)

        print(f"\n✅ 初始加载完成，已拦截 {len(api_responses)} 个API响应")

        # 模拟滚动加载更多
        for i in range(5):
            print(f"\n📜 第 {i+1} 次滚动...")

            # 滚动到底部
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

            # 增量滚动
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(1)

            # 再次滚动到底部
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)

            print(f"   当前已拦截 {len(api_responses)} 个API响应")

            # 如果最近2次滚动没有新API，说明到底了
            if i >= 2 and len(api_responses) == prev_count:
                print("   ⚠️ 连续滚动无新API，可能已到底")
                break
            prev_count = len(api_responses)

        # 分析结果
        print("\n" + "="*80)
        print("📊 数据分析结果")
        print("="*80)

        total_videos = 0
        unique_video_ids = set()

        for idx, resp in enumerate(api_responses):
            aweme_list = resp.get("aweme_list", [])
            total_videos += len(aweme_list)

            for aweme in aweme_list:
                aweme_id = aweme.get("aweme_id")
                if aweme_id:
                    unique_video_ids.add(aweme_id)

            print(f"API #{idx+1}: {len(aweme_list)} 个视频")

        print(f"\n总 API 响应数: {len(api_responses)}")
        print(f"总视频数（累计）: {total_videos}")
        print(f"唯一视频数: {len(unique_video_ids)}")

        # 检查最后一个API
        if api_responses:
            last_api = api_responses[-1]
            print(f"\n最后一个API:")
            print(f"  - 视频数: {len(last_api.get('aweme_list', []))}")
            print(f"  - max_cursor: {last_api.get('max_cursor', 'N/A')}")
            print(f"  - has_more: {last_api.get('has_more', 'N/A')}")

        print("\n⏸️ 浏览器将保持打开30秒，请手动检查...")
        await asyncio.sleep(30)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_likes_api())
