#!/usr/bin/env python3
"""
手动测试抖音接口分析

需要先运行项目并登录抖音，然后：
1. 访问 http://localhost:8000/sessions 完成登录
2. 运行此脚本分析接口
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from backend.scraper.engine import engine
from backend.scraper.interceptor import ResponseInterceptor
from backend.config import settings


async def analyze_user_likes_and_favorites():
    """分析用户喜欢和收藏的API接口"""
    print("="*60)
    print("抖音用户喜欢/收藏接口分析")
    print("="*60)

    # 初始化引擎
    if not engine._context:
        await engine.start()

    interceptor = ResponseInterceptor()
    page = await engine.get_page()

    # 检查登录状态
    is_logged_in = await engine.check_login()
    if not is_logged_in:
        print("\n❌ 未登录！请先访问 http://localhost:8000/sessions 完成登录")
        return

    print("\n✅ 已登录，开始分析...")

    # 测试用户主页（使用一个示例用户）
    test_users = [
        "MS4wLjABAAAA8VmHGtG4v-vM6-uJmKfgEUxvEWQStHBJ66Gk7FDk8Xk",  # 示例用户
    ]

    for sec_user_id in test_users:
        print(f"\n{'='*60}")
        print(f"分析用户: {sec_user_id}")
        print(f"{'='*60}")

        interceptor.clear()
        await interceptor.setup(page)

        try:
            # 1. 访问用户主页
            url = f"{settings.DOUYIN_BASE_URL}/user/{sec_user_id}"
            print(f"\n1️⃣ 访问用户主页: {url}")
            await engine.safe_goto(page, url)
            await asyncio.sleep(3)

            # 截图
            await page.screenshot(path="screenshot_user_home.png")
            print("   ✅ 已保存截图: screenshot_user_home.png")

            # 2. 检查页面结构
            page_text = await page.evaluate("() => document.body.innerText")
            print(f"\n2️⃣ 页面文本分析:")

            # 查找可能的标签
            labels_to_find = ["喜欢", "收藏", "作品", "获赞"]
            found = [label for label in labels_to_find if label in page_text]
            for label in found:
                print(f"   ✅ 找到: {label}")

            # 3. 查找可点击的元素
            elements = await page.evaluate("""
                () => {
                    const results = [];
                    const all = document.querySelectorAll('*');

                    for (let el of all) {
                        const text = el.textContent?.trim() || '';
                        if (text.includes('喜欢') || text.includes('收藏') || text.includes('作品')) {
                            if (text.length < 30) {  // 只取短的文本
                                results.push({
                                    tag: el.tagName,
                                    text: text,
                                    class: el.className,
                                    id: el.id,
                                    visible: el.offsetParent !== null
                                });
                            }
                        }
                        if (results.length >= 20) break;
                    }
                    return results;
                }
            """)

            print(f"\n3️⃣ 找到 {len(elements)} 个相关元素:")
            for i, el in enumerate(elements[:10]):
                print(f"   {i+1}. <{el['tag']}> {el['text']}")

            # 4. 尝试点击"喜欢"
            print(f"\n4️⃣ 尝试点击'喜欢'标签...")
            interceptor.clear()

            # 查找并点击
            clicked = False
            for el in elements:
                if "喜欢" in el['text'] and el['visible']:
                    try:
                        # 使用XPath定位
                        xpath = f"//{el['tag'].lower()}[contains(text(), '喜欢')]"
                        await page.click(f"text=喜欢", timeout=3000)
                        clicked = True
                        print("   ✅ 成功点击'喜欢'")
                        break
                    except:
                        pass

            if clicked:
                await asyncio.sleep(5)  # 等待API响应

                # 检查捕获的请求
                captured = interceptor.get_all()
                like_apis = [req for req in captured if any(kw in req.get('url', '') for kw in ['like', 'favor', 'collect'])]

                print(f"\n5️⃣ 捕获到 {len(like_apis)} 个可能的API:")
                for api in like_apis[:5]:
                    print(f"   - {api['url'][:100]}")

                await page.screenshot(path="screenshot_after_likes.png")
                print("   ✅ 已保存截图: screenshot_after_likes.png")

            # 5. 返回主页并尝试点击"收藏"
            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            print(f"\n6️⃣ 尝试点击'收藏'标签...")
            interceptor.clear()

            clicked = False
            for el in elements:
                if "收藏" in el['text'] and el['visible']:
                    try:
                        await page.click(f"text=收藏", timeout=3000)
                        clicked = True
                        print("   ✅ 成功点击'收藏'")
                        break
                    except:
                        pass

            if clicked:
                await asyncio.sleep(5)

                captured = interceptor.get_all()
                fav_apis = [req for req in captured if any(kw in req.get('url', '') for kw in ['favor', 'collect', 'like'])]

                print(f"\n7️⃣ 捕获到 {len(fav_apis)} 个可能的API:")
                for api in fav_apis[:5]:
                    print(f"   - {api['url'][:100]}")

                await page.screenshot(path="screenshot_after_favorites.png")
                print("   ✅ 已保存截图: screenshot_after_favorites.png")

        finally:
            await interceptor.teardown()

    print(f"\n{'='*60}")
    print("✅ 分析完成！")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(analyze_user_likes_and_favorites())
