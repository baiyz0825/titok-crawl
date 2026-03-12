#!/usr/bin/env python3
"""
持续监控抖音登录状态
用于捕获扫码后的所有变化，包括弹框、验证码等
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

# 这里需要集成到你的项目结构中
# async def monitor_login_status(page):
#     """持续监控登录状态"""
#     last_state = {}
#
#     for i in range(100):  # 最多监控 100 次
#         try:
#             # 获取当前状态
#             current_state = await page.evaluate("""
#                 () => {
#                     const result = {
#                         timestamp: Date.now(),
#                         url: window.location.href,
#                         loginPanelExists: !!document.getElementById('login-panel-new'),
#                         qrContainerExists: !!document.getElementById('animate_qrcode_container'),
#                         events: window.__douyinEvents || []
#                     };
#
#                     // 检查是否有验证码弹框
#                     const captcha = document.querySelector('[class*="captcha"], [id*="captcha"]');
#                     if (captcha) {
#                         result.captchaVisible = true;
#                         result.captchaText = captcha.textContent?.substring(0, 100);
#                     }
#
#                     // 检查是否有确认弹框
#                     const dialogs = document.querySelectorAll('[role="dialog"], .modal, .popup');
#                     result.dialogCount = dialogs.length;
#
#                     // 检查登录状态
#                     const loginButton = document.querySelector('button[class*="login"]');
#                     result.loginButtonVisible = !!loginButton;
#
#                     // 获取二维码状态
#                     const qrContainer = document.getElementById('animate_qrcode_container');
#                     if (qrContainer) {
#                         // 尝试从 React Fiber 获取状态
#                         const fiberKey = Object.keys(qrContainer).find(k => k.startsWith('__reactFiber'));
#                         if (fiberKey) {
#                             // 这里可以进一步解析状态
#                             result.hasReactFiber = true;
#                         }
#                     }
#
#                     return result;
#                 }
#             """)
#
#             # 检查状态变化
#             if current_state != last_state:
#                 print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 状态变化:")
#                 print(json.dumps(current_state, indent=2, ensure_ascii=False))
#                 last_state = current_state
#
#                 # 保存到文件
#                 log_file = Path("login_events.jsonl")
#                 with open(log_file, "a") as f:
#                     f.write(json.dumps({
#                         "timestamp": datetime.now().isoformat(),
#                         "state": current_state
//                     }) + "\n")
#
#             # 如果登录面板消失了，可能登录成功
#             if not current_state.get('loginPanelExists') and last_state.get('loginPanelExists'):
#                 print(f"\n✅ 登录面板消失，可能已登录成功！")
#                 break
#
#             await asyncio.sleep(2)
#
#         except Exception as e:
#             print(f"监控出错: {e}")
#             await asyncio.sleep(2)


# 使用示例
if __name__ == "__main__":
    print("抖音登录状态监控器")
    print("=" * 50)
    print()
    print("请使用 Chrome DevTools MCP 进行监控")
    print("或者将此代码集成到你的 engine.py 中")
