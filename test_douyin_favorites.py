#!/usr/bin/env python3
"""
手动测试：分析抖音用户喜欢和收藏接口

使用方法：
1. 确保项目正在运行：python run.sh
2. 在浏览器中访问 http://localhost:8000/sessions 并完成抖音登录
3. 运行此脚本：python test_douyin_favorites.py

脚本会：
1. 使用已登录的浏览器
2. 访问测试用户主页
3. 尝试点击"喜欢"和"收藏"标签
4. 打印捕获的API接口
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from backend.scraper.engine import engine
from backend.scraper.interceptor import ResponseInterceptor
from backend.config import settings
import json


async def main():
    print("="*70)
    print("抖音喜欢/收藏接口分析工具")
    print("="*70)

    # 初始化引擎
    if not engine._browser:
        await engine.start()

    interceptor = ResponseInterceptor()
    page = await engine.get_page()

    # 检查登录状态
    is_logged_in = await engine.check_login()
    if not is_logged_in:
        print("\n❌ 未登录！")
        print("   请在浏览器中访问: http://localhost:8000/sessions")
        print("   扫码登录后，再运行此脚本")
        return

    print("\n✅ 检测到登录状态")

    # 测试用户列表
    test_users = [
        "MS4wLjABAAAA8VmHGtG4v-vM6-uJmKfgEUxvEWQStHBJ66Gk7FDk8Xk",
    ]

    captured_apis = {
        "likes": [],
        "favorites": [],
        "works": []
    }

    for sec_user_id in test_users:
        print(f"\n{'='*70}")
        print(f"测试用户: {sec_user_id[:30]}...")
        print(f"{'='*70}")

        try:
            # 1. 访问用户主页
            url = f"{settings.DOUYIN_BASE_URL}/user/{sec_user_id}"
            print(f"\n1️⃣  访问用户主页...")
            print(f"   URL: {url}")

            interceptor.clear()
            await interceptor.setup(page)

            await engine.safe_goto(page, url)
            await asyncio.sleep(3)

            # 截图
            await page.screenshot(path="test_1_user_home.png", full_page=False)
            print("   ✅ 已截图: test_1_user_home.png")

            # 检查页面内容
            page_text = await page.evaluate("() => document.body.innerText")

            print(f"\n2️⃣  页面分析:")
            keywords = ["喜欢", "收藏", "作品", "获赞"]
            for kw in keywords:
                if kw in page_text:
                    print(f"   ✅ 找到关键词: {kw}")

            # 查找可点击元素
            elements = await page.evaluate("""
                () => {
                    const results = [];
                    const all = document.querySelectorAll('*');
                    for (let el of all) {
                        const text = el.textContent?.trim() || '';
                        if ((text.includes('喜欢') || text.includes('收藏')) && text.length < 20) {
                            results.push({
                                tag: el.tagName,
                                text: text,
                                class: el.className,
                                visible: el.offsetParent !== null
                            });
                        }
                        if (results.length >= 10) break;
                    }
                    return results;
                }
            """)

            print(f"\n3️⃣  找到 {len(elements)} 个相关元素:")
            for i, el in enumerate(elements[:5]):
                status = "可见" if el['visible'] else "隐藏"
                print(f"   [{i+1}] <{el['tag']}> {el['text']} ({status})")

            # 4. 尝试点击"喜欢"
            print(f"\n4️⃣  尝试点击'喜欢'...")
            interceptor.clear()

            try:
                # 方法1: 文本选择器
                await page.click('text=喜欢', timeout=3000)
                print("   ✅ 点击成功")
                await asyncio.sleep(5)

                # 获取捕获的请求
                captured = interceptor.get_all()
                like_apis = [req for req in captured if any(kw in req.get('url', '') for kw in ['like', 'favor'])]

                print(f"\n5️⃣  捕获到 {len(like_apis)} 个API:")
                for api in like_apis[:3]:
                    print(f"   📡 {api['url'][:120]}")
                    captured_apis["likes"].append(api['url'])

                await page.screenshot(path="test_2_after_likes.png")
                print("   ✅ 已截图: test_2_after_likes.png")

            except Exception as e:
                print(f"   ⚠️  点击失败: {e}")

            # 5. 返回并尝试点击"收藏"
            print(f"\n6️⃣  返回主页...")
            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            print(f"\n7️⃣  尝试点击'收藏'...")
            interceptor.clear()

            try:
                await page.click('text=收藏', timeout=3000)
                print("   ✅ 点击成功")
                await asyncio.sleep(5)

                captured = interceptor.get_all()
                fav_apis = [req for req in captured if any(kw in req.get('url', '') for kw in ['favor', 'collect'])]

                print(f"\n8️⃣  捕获到 {len(fav_apis)} 个API:")
                for api in fav_apis[:3]:
                    print(f"   📡 {api['url'][:120]}")
                    captured_apis["favorites"].append(api['url'])

                await page.screenshot(path="test_3_after_favorites.png")
                print("   ✅ 已截图: test_3_after_favorites.png")

            except Exception as e:
                print(f"   ⚠️  点击失败: {e}")

        finally:
            await interceptor.teardown()

    # 保存结果
    print(f"\n{'='*70}")
    print("保存分析结果...")
    print(f"{'='*70}")

    with open("douyin_api_analysis.json", "w", encoding="utf-8") as f:
        json.dump(captured_apis, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 结果已保存到: douyin_api_analysis.json")
    print(f"\n{'='*70}")
    print("分析完成！")
    print(f"{'='*70}\n")

    # 打印汇总
    print("\n📊 API汇总:")
    print(f"   - 喜欢相关API: {len(captured_apis['likes'])} 个")
    print(f"   - 收藏相关API: {len(captured_apis['favorites'])} 个")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
