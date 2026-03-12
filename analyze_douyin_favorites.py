#!/usr/bin/env python3
"""
分析抖音的喜欢和收藏接口

使用方法：
1. 先登录抖音（使用项目的登录功能）
2. 运行此脚本：python analyze_douyin_favorites.py
3. 脚本会导航到用户主页并监听网络请求
"""

import asyncio
import json
from playwright.async_api import async_playwright, Page
import re

# 存储捕获的请求
captured_requests = {
    "likes": [],
    "favorites": [],
    "profile": []
}


async def setup_request_interceptor(page: Page):
    """设置请求拦截器"""

    async def handle_request(request):
        url = request.url
        method = request.method

        # 只关注API请求
        if "aweme" in url or "v1" in url or "web" in url:
            print(f"[请求] {method} {url[:100]}")

    async def handle_response(response):
        url = response.url
        status = response.status

        # 捕获可能包含喜欢/收藏数据的响应
        if status == 200:
            url_lower = url.lower()

            # 用户喜欢列表
            if any(kw in url_lower for kw in ["like", "favor", "collect"]):
                try:
                    # 只记录JSON响应
                    content_type = response.header_value("content-type") or ""
                    if "application/json" in content_type:
                        body = await response.text()
                        if len(body) < 10000:  # 避免过大的响应
                            data = json.loads(body)

                            # 分类存储
                            if "like" in url_lower and "user" in url_lower:
                                captured_requests["likes"].append({
                                    "url": url,
                                    "data": data
                                })
                                print(f"\n✅ 捕获到喜欢接口:")
                                print(f"   URL: {url[:150]}")
                                print(f"   数据键: {list(data.keys()) if isinstance(data, dict) else 'list'}\n")

                            elif "favor" in url_lower or "collect" in url_lower:
                                captured_requests["favorites"].append({
                                    "url": url,
                                    "data": data
                                })
                                print(f"\n✅ 捕获到收藏接口:")
                                print(f"   URL: {url[:150]}")
                                print(f"   数据键: {list(data.keys()) if isinstance(data, dict) else 'list'}\n")

                except Exception as e:
                    pass

    page.on("request", handle_request)
    page.on("response", handle_response)


async def analyze_user_page(page: Page, user_url: str):
    """分析用户主页"""
    print(f"\n{'='*60}")
    print(f"访问用户主页: {user_url}")
    print(f"{'='*60}\n")

    await page.goto(user_url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(3)

    # 截图
    await page.screenshot(path="screenshot_user_page.png")
    print("✅ 已保存用户主页截图: screenshot_user_page.png")

    # 查找页面文本以了解结构
    page_text = await page.evaluate("() => document.body.innerText")

    # 查找可能的标签按钮
    print("\n🔍 查找喜欢/收藏标签...")

    # 常见的标签文本
    possible_labels = ["喜欢", "收藏", "作品", "作品数", "获赞"]
    found_labels = []
    for label in possible_labels:
        if label in page_text:
            found_labels.append(label)
            print(f"   找到: {label}")

    # 尝试获取页面结构
    page_structure = await page.evaluate("""
        () => {
            // 查找所有可能的标签容器
            const buttons = Array.from(document.querySelectorAll('div, span, button, a'))
                .filter(el => {
                    const text = el.textContent?.trim() || ''
                    return text.includes('喜欢') || text.includes('收藏') || text.includes('作品')
                })
                .map(el => ({
                    tag: el.tagName,
                    text: el.textContent?.trim().substring(0, 50),
                    class: el.className,
                    id: el.id
                }))
                .slice(0, 10)

            return buttons
        }
    """)

    print("\n📋 页面元素:")
    for item in page_structure[:5]:
        print(f"   {item}")

    return page_structure


async def click_and_monitor(page: Page, label_text: str, category: str):
    """点击标签并监听请求"""
    print(f"\n{'='*60}")
    print(f"尝试点击: {label_text}")
    print(f"{'='*60}\n")

    # 使用文本定位器点击
    try:
        # 等待一下
        await asyncio.sleep(2)

        # 尝试多种方式点击
        click_success = False

        # 方法1: getByText
        try:
            element = page.get_by_text(label_text, exact=True)
            if await element.is_visible(timeout=3000):
                await element.click()
                click_success = True
                print(f"✅ 使用getByText成功点击: {label_text}")
        except:
            pass

        # 方法2: 文本选择器
        if not click_success:
            try:
                await page.click(f'text="{label_text}"', timeout=5000)
                click_success = True
                print(f"✅ 使用文本选择器成功点击: {label_text}")
            except:
                pass

        # 方法3: JavaScript点击
        if not click_success:
            try:
                result = await page.evaluate(f"""
                    () => {{
                        const elements = Array.from(document.querySelectorAll('*'))
                        const target = elements.find(el => el.textContent?.trim() === '{label_text}')
                        if (target) {{
                            target.click()
                            return true
                        }}
                        return false
                    }}
                """)
                if result:
                    click_success = True
                    print(f"✅ 使用JS成功点击: {label_text}")
            except:
                pass

        if click_success:
            # 等待网络请求
            await asyncio.sleep(5)
            await page.screenshot(path=f"screenshot_after_{category}.png")
            print(f"✅ 已保存截图: screenshot_after_{category}.png")

            # 尝试滚动加载更多
            for i in range(3):
                await page.evaluate("window.scrollBy(0, window.innerHeight * 0.5)")
                await asyncio.sleep(2)
                await page.screenshot(path=f"screenshot_{category}_scroll_{i+1}.png")

            print(f"\n📊 捕获到的{category}接口数量: {len(captured_requests[category])}")
        else:
            print(f"❌ 无法点击: {label_text}")

    except Exception as e:
        print(f"❌ 点击出错: {e}")


async def main():
    """主函数"""
    print("抖音喜欢/收藏接口分析工具")
    print("="*60)

    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.86 Safari/537.36"
        )

        # 加载cookies（如果已登录）
        try:
            with open("data/cookies.json", "r") as f:
                cookies = json.load(f)
                await context.add_cookies(cookies)
                print("✅ 已加载cookies")
        except:
            print("⚠️  未找到cookies，需要手动登录")

        page = await context.new_page()

        # 设置请求拦截
        await setup_request_interceptor(page)

        try:
            # 访问抖音
            await page.goto("https://www.douyin.com", wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # 检查登录状态
            logged_in = await page.evaluate("""
                () => {
                    return document.querySelector('[data-e2e="user-info"]') !== null
                }
            """)

            if not logged_in:
                print("\n⚠️  请先扫码登录抖音！")
                print("   登录完成后，按Enter键继续...")
                input()

                # 保存cookies
                cookies = await context.cookies()
                with open("data/cookies.json", "w") as f:
                    json.dump(cookies, f)
                print("✅ 已保存cookies")

            # 测试用户主页（这里使用一个示例，实际使用时需要替换）
            # 或者访问当前登录用户的主页
            print("\n访问用户主页...")

            # 方案1: 访问当前登录用户的主页
            await page.goto("https://www.douyin.com", wait_until="domcontentloaded")
            await asyncio.sleep(2)

            # 尝试找到当前用户的主页链接
            user_home_url = await page.evaluate("""
                () => {
                    // 查找用户头像或用户名链接
                    const avatar = document.querySelector('[data-e2e="user-info"] img')
                    if (avatar) {
                        const link = avatar.closest('a')
                        if (link) return link.href
                    }
                    return null
                }
            """)

            if user_home_url:
                print(f"✅ 找到用户主页: {user_home_url}")
            else:
                # 使用测试用户
                user_home_url = "https://www.douyin.com/user/MS4wLjABAAAA8VmHGtG4v-vM6-uJmKfgEUxvEWQStHBJ66Gk7FDk8Xk"
                print(f"⚠️  使用测试用户: {user_home_url}")

            # 分析用户主页
            await analyze_user_page(page, user_home_url)

            # 尝试点击"喜欢"
            await click_and_monitor(page, "喜欢", "likes")

            # 返回主页
            await page.goto(user_home_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)

            # 尝试点击"收藏"
            await click_and_monitor(page, "收藏", "favorites")

        finally:
            # 保存结果
            output_file = "douyin_api_analysis.json"
            with open(output_file, "w", ensure_ascii=False, indent=2) as f:
                json.dump(captured_requests, f)
            print(f"\n{'='*60}")
            print(f"✅ 分析完成！结果已保存到: {output_file}")
            print(f"{'='*60}\n")

            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
