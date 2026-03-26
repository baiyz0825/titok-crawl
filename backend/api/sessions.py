import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.scraper.engine import engine
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# 模块级变量：当前登录页面引用，供 input-code 使用
_login_page = None
_login_page_lock = asyncio.Lock()


@router.post("/login")
async def trigger_login(force: bool = False):
    """Trigger QR code login flow. Waits for QR scan (up to 2 min)."""
    if not force:
        is_logged_in = await engine.check_login()
        if is_logged_in:
            return {"logged_in": True, "message": "Already logged in"}

    # Clear existing cookies to force re-login
    if engine._context:
        await engine._context.clear_cookies()

    success = await engine.wait_for_login()
    return {"logged_in": success}


@router.get("/status")
async def login_status():
    """Check current login status and captcha state."""
    is_logged_in = await engine.check_login()
    return {
        "logged_in": is_logged_in,
        "captcha_active": engine.captcha_active,
    }


@router.get("/login-stream")
async def login_stream(request: Request):
    """SSE 端点：推送登录页面截图和状态

    完整登录流程状态：
    - qrcode: 显示二维码，等待扫码
    - scanned: 已扫码，显示身份验证窗口
    - verify: 短信已发送，等待输入验证码
    - saving: 验证通过，询问是否保存登录信息
    - success: 登录成功
    - timeout: 超时
    - error: 错误
    """

    async def event_generator():
        global _login_page
        page = None

        try:
            page = await engine.get_page()
            async with _login_page_lock:
                _login_page = page

            # 如果需要强制重新登录，清除 cookies
            if engine._context:
                await engine._context.clear_cookies()

            await page.goto(settings.DOUYIN_BASE_URL, wait_until="domcontentloaded")
            logger.info("Login stream started, navigated to Douyin")
            logger.info("⏳ Waiting for QR code scan...")
            logger.info("⏰ Login timeout: 10 minutes")

            timeout = 600  # 增加到10分钟（用户需要找手机、扫码、等待短信、输入验证码）
            verification_window_seen = False
            verification_window_start_time = 0
            last_phase = ""
            current_phase = "qrcode"  # 初始化状态
            login_success_countdown = 0  # 登录成功后的截图倒计时

            # 立即推送初始状态（确保前端能收到）
            yield f"event: status\ndata: {json.dumps({'phase': 'qrcode'})}\n\n"
            last_phase = "qrcode"
            logger.info("📤 Pushed initial state: qrcode")

            for i in range(timeout):
                # 检查客户端是否断开
                if await request.is_disconnected():
                    logger.info("Client disconnected from login stream")
                    break

                # 步骤0: 推送页面截图（用于前端显示登录过程中的所有状态）
                # 包括：二维码、验证码输入、保存登录信息对话框、登录成功页面等
                try:
                    screenshot_uri = await engine.screenshot_page(page)
                    yield f"event: screenshot\ndata: {json.dumps({'image': screenshot_uri})}\n\n"
                except Exception as e:
                    logger.debug(f"Screenshot failed: {e}")

                # 步骤1: 自动处理短信验证码弹窗
                try:
                    dialog_handled = await engine._handle_sms_consent_dialog(page)
                    if dialog_handled:
                        logger.info("✅ Stream: 已点击'接收短信验证码'")

                        # 等待验证窗口和输入框出现（最多3秒）
                        input_found = False
                        for wait_i in range(6):  # 6 * 0.5 = 3秒
                            await asyncio.sleep(0.5)
                            input_box = await page.query_selector('#button-input')
                            if input_box:
                                input_found = True
                                logger.info("✅ 验证码输入框已出现")
                                break

                        if input_found:
                            verification_window_seen = True
                            verification_window_start_time = i

                            # 推送 verify 状态，让前端显示验证码输入框
                            current_phase = "verify"
                            if current_phase != last_phase:
                                yield f"event: status\ndata: {json.dumps({'phase': current_phase})}\n\n"
                                last_phase = current_phase
                                logger.info("📤 Pushed verify state after input box appeared")
                        else:
                            logger.warning("⚠️ 点击后未找到输入框，可能需要重新点击")
                except Exception as e:
                    logger.debug(f"Auto-handle SMS dialog failed: {e}")

                # 步骤2: 检测验证窗口超时
                if verification_window_seen and verification_window_start_time:
                    elapsed = i - verification_window_start_time
                    if elapsed > 120:  # 2分钟后检查
                        qr_visible = await page.query_selector('#animate_qrcode_container')
                        if qr_visible and await qr_visible.is_visible():
                            logger.warning("❌ Stream: 验证窗口超时，回到扫码状态")
                            verification_window_seen = False
                            verification_window_start_time = 0
                            current_phase = "qrcode"  # 重置状态

                # 步骤3: 检测各种状态
                # 注意：不再在每次循环开始时重置 current_phase = "qrcode"
                # 而是保留上一次的状态，只在明确的状态变化时更新

                try:
                    # 检测登录状态（优先检查）
                    if await engine.check_login():
                        await engine._handle_save_login_dialog(page)
                        await engine.save_cookies("default")

                        # 登录成功，不再自动采集用户信息
                        # 用户可以通过"采集当前用户"按钮手动采集

                        current_phase = "success"
                        if current_phase != last_phase:
                            yield f"event: status\ndata: {json.dumps({'phase': current_phase})}\n\n"
                            last_phase = current_phase
                        logger.info("✅ Login successful via stream")

                        # 设置登录成功后的截图倒计时，继续推送10次截图（5秒）
                        # 让用户看到"保存登录信息"对话框和登录成功页面
                        if login_success_countdown == 0:
                            login_success_countdown = 10
                        # 不要立即break，继续循环推送截图

                    # 检测页面文字内容来判断状态
                    try:
                        page_text = await page.evaluate("() => document.body.innerText")
                    except Exception as e:
                        logger.debug(f"Failed to get page text: {e}")
                        page_text = ""

                    # 优先检测"短信已发送"（说明已经点击成功，进入验证码输入阶段）
                    if "短信已发送" in page_text or "请输入验证码" in page_text:
                        # 重要：必须确认验证窗口实际存在
                        verify_window = await page.query_selector('#uc-second-verify')
                        if verify_window and await verify_window.is_visible():
                            # 提取手机号（支持多种格式）
                            import re
                            # 格式1: 181******11（3位数字 + 多个星号 + 2-4位数字）
                            phone_match = re.search(r'1[3-9]\d{1}[*\*]{6,}\d{2,4}', page_text)
                            if not phone_match:
                                # 格式2: 181****11（较少星号）
                                phone_match = re.search(r'1[3-9]\d{1}[*\*]{4,}\d{2,4}', page_text)
                            if not phone_match:
                                # 格式3: 181****0011（更多数字）
                                phone_match = re.search(r'1[3-9]\d[*\*]+\d+', page_text)

                        phone = phone_match.group(0) if phone_match else ""

                        # 调试：只在第一次时打印详细信息
                        if current_phase != "verify" or (phone and i % 30 == 0):
                            if phone:
                                logger.info(f"✅ 提取到手机号: {phone}")
                            else:
                                # 打印相关文本片段帮助调试
                                phone_context = re.search(r'.{0,30}1\d.*?\d{2,4}.{0,10}', page_text)
                                if phone_context:
                                    logger.debug(f"[Phone Context] {phone_context.group(0)[:60]}")

                        # 即使没有手机号也推送 verify 状态
                        current_phase = "verify"
                        if current_phase != last_phase:
                            yield f"event: status\ndata: {json.dumps({'phase': current_phase, 'phone': phone})}\n\n"
                            last_phase = current_phase
                            logger.info(f"📱 State: {current_phase}, phone: {phone}")
                        # 不再 continue，让循环继续执行到截图和sleep
                    else:
                        # 文本包含"短信已发送"但窗口不存在，说明窗口已消失
                        if "短信已发送" in page_text or "请输入验证码" in page_text:
                            logger.info("⚠️ 检测到验证文本但窗口已消失，保持 verify 状态")
                            # 保持 verify 状态，不改变
                            if current_phase != "verify":
                                current_phase = "verify"
                                if current_phase != last_phase:
                                    yield f"event: status\ndata: {json.dumps({'phase': current_phase, 'phone': ''})}\n\n"
                                    last_phase = current_phase

                    # 检测扫码后的身份验证窗口（点击前）
                    if "接收短信验证码" in page_text or "发送短信验证" in page_text:
                        # 确认还没有发送短信（避免重复点击）
                        if "短信已发送" not in page_text:
                            current_phase = "scanned"

                    # 状态变化时推送
                    if current_phase != last_phase:
                        yield f"event: status\ndata: {json.dumps({'phase': current_phase})}\n\n"
                        last_phase = current_phase
                        if current_phase != "qrcode":
                            logger.info(f"🔄 State changed: {last_phase} → {current_phase}")

                except Exception as e:
                    logger.debug(f"Status detection error: {e}")

                # 步骤3.5: 如果之前在verify状态但现在不在了，说明验证窗口消失了，尝试重新点击
                if last_phase == "verify" and current_phase != "verify" and current_phase != "success":
                    try:
                        # 检查是否有"接收短信验证码"按钮
                        page_text = await page.evaluate("() => document.body.innerText")
                        if "接收短信验证码" in page_text or "发送短信验证" in page_text:
                            logger.info("🔄 验证窗口消失，尝试重新点击'接收短信验证码'")
                            handled = await engine._handle_sms_consent_dialog(page)
                            if handled:
                                logger.info("✅ 重新点击成功")
                                verification_window_seen = True
                                verification_window_start_time = i
                    except Exception as e:
                        logger.debug(f"Re-click failed: {e}")

                # 步骤4: 等待0.5秒（增加截图频率）
                await asyncio.sleep(0.5)

                # 步骤5: 检查登录成功后的截图倒计时
                if login_success_countdown > 0:
                    login_success_countdown -= 1
                    if login_success_countdown == 0:
                        logger.info("✅ Login success screenshots completed, ending stream")
                        break
                    # 继续循环，不再执行其他状态检测
                    continue

            else:
                # 循环正常结束 = 超时
                yield f"event: status\ndata: {json.dumps({'phase': 'timeout'})}\n\n"
                logger.warning("⏰ Login stream timeout")

        except Exception as e:
            logger.error(f"Login stream error: {e}")
            yield f"event: status\ndata: {json.dumps({'phase': 'error', 'message': str(e)})}\n\n"
        finally:
            async with _login_page_lock:
                _login_page = None

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class CodeInput(BaseModel):
    code: str


@router.post("/input-code")
async def input_code(body: CodeInput):
    """接收验证码，填入 Playwright 页面"""
    global _login_page
    async with _login_page_lock:
        page = _login_page

    if page is None:
        return {"success": False, "message": "没有活跃的登录页面"}

    ok = await engine.fill_verify_code(page, body.code)
    return {"success": ok}


@router.get("/current-user")
async def get_current_user():
    """获取当前登录用户信息"""
    # 先检查是否已登录（只检查 cookies，不导航）
    is_logged_in = await engine.check_login()
    if not is_logged_in:
        raise HTTPException(status_code=401, detail="未登录")

    try:
        from backend.db import crud

        # 获取当前登录用户的 sec_user_id
        sec_user_id = await engine.get_current_user_id()
        if not sec_user_id:
            raise HTTPException(status_code=404, detail="无法获取当前用户 ID，请点击\"采集当前用户\"按钮")

        # 从数据库中查找这个用户
        user = await crud.get_user(sec_user_id)
        if user:
            return user.model_dump()
        else:
            raise HTTPException(status_code=404, detail="用户信息未找到，请点击\"采集当前用户\"按钮")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get current user: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scrape-current-user")
async def scrape_current_user():
    """采集当前登录用户信息并保存到数据库"""
    # 先检查是否已登录
    is_logged_in = await engine.check_login()
    if not is_logged_in:
        raise HTTPException(status_code=401, detail="未登录，请先扫码登录")

    try:
        from backend.db import crud
        from backend.scraper.user_scraper import UserScraper

        sec_user_id = await engine.get_current_user_id()
        if not sec_user_id:
            raise HTTPException(status_code=404, detail="无法获取当前用户 ID")

        logger.info(f"Scraping current user profile: {sec_user_id}")

        # 使用 UserScraper 采集用户信息（复用任务采集逻辑）
        scraper = UserScraper()
        user_data = await scraper.scrape_profile(task_id=0, sec_user_id=sec_user_id)

        if user_data:
            # 保存到数据库（upsert_user 返回用户 ID）
            await crud.upsert_user(user_data)
            logger.info(f"✅ Saved current user: {user_data.nickname} ({sec_user_id})")
            return {
                "success": True,
                "user": user_data.model_dump(),
                "message": f"已采集用户: {user_data.nickname}"
            }
        else:
            raise HTTPException(status_code=500, detail="采集用户信息失败，请稍后重试")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to scrape current user: {e}")
        raise HTTPException(status_code=500, detail=f"采集失败: {str(e)}")
