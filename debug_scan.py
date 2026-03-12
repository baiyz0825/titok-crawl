#!/usr/bin/env python3
"""
调试脚本：检测扫码后的实际页面状态
用法：
1. 运行此脚本
2. 在弹出的浏览器中扫码
3. 查看控制台输出的页面结构
"""

import asyncio
import json
from playwright.async_api import async_playwright

async def debug_scan_state():
    """检测扫码后的页面状态"""
    print("🔍 启动浏览器...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # 显示浏览器
            args=[
                "--disable-blink-features=AutomationControlled",
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            locale="zh-CN",
        )

        page = await context.new_page()

        print("📱 访问抖音...")
        await page.goto("https://www.douyin.com", wait_until="domcontentloaded")

        print("\n" + "="*60)
        print("请在浏览器中扫码登录")
        print("扫码后会自动检测页面状态...")
        print("="*60 + "\n")

        # 持续检测页面状态
        for i in range(60):
            await asyncio.sleep(1)

            # 每5秒检测一次
            if i % 5 == 0:
                print(f"\n📍 第 {i} 秒检测结果：")

                # 检查1: 登录面板
                login_panel = await page.query_selector('#login-panel-new')
                if login_panel:
                    visible = await login_panel.is_visible()
                    print(f"  ✅ 登录面板存在: {visible}")
                else:
                    print(f"  ❌ 登录面板不存在")

                # 检查2: 二维码容器
                qr_container = await page.query_selector('#animate_qrcode_container')
                if qr_container:
                    visible = await qr_container.is_visible()
                    print(f"  ✅ 二维码容器存在: {visible}")
                else:
                    print(f"  ❌ 二维码容器不存在")

                # 检查3: 验证窗口（我们预期的ID）
                verify_window = await page.query_selector('#uc-second-verify')
                if verify_window:
                    visible = await verify_window.is_visible()
                    print(f"  ✅ 验证窗口 #uc-second-verify 存在: {visible}")

                    if visible:
                        # 获取窗口内容
                        content = await verify_window.inner_text()
                        print(f"  📝 窗口内容: {content[:100]}...")
                else:
                    print(f"  ❌ 验证窗口 #uc-second-verify 不存在")

                # 检查4: 查找所有可能的验证相关元素
                all_dialogs = await page.evaluate("""
                    () => {
                        const result = [];

                        // 查找所有对话框/弹窗
                        const dialogs = document.querySelectorAll('[role="dialog"], .modal, .popup, [id*="verify"], [id*="second"], [class*="verify"]');
                        dialogs.forEach(d => {
                            if (d.offsetParent !== null) {  // 可见
                                result.push({
                                    tag: d.tagName,
                                    id: d.id,
                                    className: d.className,
                                    text: d.textContent?.substring(0, 50)
                                });
                            }
                        });

                        return result;
                    }
                """)

                if all_dialogs:
                    print(f"\n  🎯 发现 {len(all_dialogs)} 个可见对话框/弹窗：")
                    for idx, dlg in enumerate(all_dialogs[:3]):  # 只显示前3个
                        print(f"    [{idx+1}] {dlg['tag']}")
                        print(f"        id: {dlg['id']}")
                        print(f"        class: {dlg['className'][:60]}...")
                        print(f"        text: {dlg['text']}")
                else:
                    print(f"\n  ℹ️ 未发现其他对话框/弹窗")

                # 检查5: 页面URL
                url = page.url
                print(f"\n  🔗 当前URL: {url}")

                # 检查6: 页面标题
                title = await page.title()
                print(f"  📄 页面标题: {title}")

                # 检查是否登录成功
                cookies = await context.cookies("https://www.douyin.com")
                sessionid = next((c for c in cookies if c["name"] == "sessionid"), None)
                if sessionid and sessionid.get("value"):
                    print(f"\n  🎉 发现 sessionid cookie: {sessionid['value'][:20]}...")
                    print(f"  ✅ 可能已经登录成功！")
                    break

        print("\n" + "="*60)
        print("检测结束，浏览器将在5秒后关闭...")
        print("="*60)

        await asyncio.sleep(5)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_scan_state())
