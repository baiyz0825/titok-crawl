"""更详细的抖音喜欢列表API分析"""
import asyncio
import json
from playwright.async_api import async_playwright

async def analyze():
    async with async_playwright() as p:
        print("🚀 启动浏览器...")
        browser = await p.chromium.launch_persistent_context(
            user_data_dir="data/browser",
            headless=False,
            viewport={"width": 1280, "height": 720},
        )

        page = await browser.new_page()

        # 存储所有API
        all_apis = []

        async def handle_response(response):
            url = response.url
            # 捕获所有 aweme 相关的API
            if "aweme" in url:
                try:
                    data = await response.json()
                    all_apis.append({
                        "url": url,
                        "data": data
                    })
                    print(f"\n📡 API #{len(all_apis)}")
                    print(f"   {url[:150]}...")

                    # 打印关键字段
                    if isinstance(data, dict):
                        if "aweme_list" in data:
                            print(f"   📦 aweme_list: {len(data['aweme_list'])} items")
                        for key in ["status_code", "has_more", "max_cursor", "cursor"]:
                            if key in data:
                                print(f"   🔑 {key}: {data[key]}")

                except:
                    pass

        page.on("response", handle_response)

        print("\n🌐 导航到喜欢列表...")
        await page.goto("https://www.douyin.com/user/self?showTab=like", wait_until="networkidle")
        await asyncio.sleep(5)

        print(f"\n✅ 页面加载完成，已拦截 {len(all_apis)} 个 API")

        # 检查页面内容
        is_likes_page = await page.evaluate("""
            () => {
                return {
                    url: window.location.href,
                    hasLikeTab: document.body.innerHTML.includes('喜欢'),
                    showTab: new URL(window.location.href).searchParams.get('showTab')
                }
            }
        """)
        print(f"\n📄 页面信息: {is_likes_page}")

        # 查找所有包含"喜欢"的API
        print(f"\n🔍 查找喜欢列表相关的API...")
        for idx, api in enumerate(all_apis):
            url = api["url"]
            if "like" in url.lower() or "favorite" in url.lower():
                print(f"\n✅ 找到可能相关的API #{idx+1}:")
                print(f"   {url}")

                # 打印完整响应
                print(f"\n   完整响应:")
                print(f"   {json.dumps(api['data'], indent=2, ensure_ascii=False)[:500]}...")

        # 手动滚动并观察
        print(f"\n📜 开始滚动...")
        for i in range(5):
            print(f"\n--- 滚动 {i+1}/5 ---")

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(2)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(4)

            new_apis = len(all_apis)
            print(f"   当前API总数: {new_apis}")

        # 最终分析
        print(f"\n{'='*80}")
        print("📊 最终统计")
        print('='*80)
        print(f"总API数: {len(all_apis)}")

        # 分类统计
        api_types = {}
        for api in all_apis:
            url = api["url"]
            if "/aweme/v1/web/" in url:
                path = url.split("/aweme/v1/web/")[1].split("?")[0]
                api_types[path] = api_types.get(path, 0) + 1

        print(f"\nAPI类型分布:")
        for path, count in sorted(api_types.items(), key=lambda x: -x[1]):
            print(f"  {path}: {count} 次")

        print(f"\n⏸️ 保持浏览器打开30秒...")
        await asyncio.sleep(30)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(analyze())
