import asyncio
import json
import logging

from fastapi import APIRouter, Request
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
    """SSE 端点：推送登录页面截图和状态"""

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

            timeout = 180
            for i in range(timeout):
                # 检查客户端是否断开
                if await request.is_disconnected():
                    logger.info("Client disconnected from login stream")
                    break

                # 截图推送
                try:
                    image = await engine.screenshot_page(page)
                    yield f"event: screenshot\ndata: {json.dumps({'image': image})}\n\n"
                except Exception as e:
                    logger.warning(f"Screenshot failed: {e}")

                # 检测登录状态
                if await engine.check_login():
                    await engine.save_cookies("default")
                    yield f"event: status\ndata: {json.dumps({'phase': 'success'})}\n\n"
                    logger.info("Login successful via stream")
                    break

                # 检测验证码输入框
                verify_info = await engine.detect_verify_code_input(page)
                if verify_info:
                    yield f"event: status\ndata: {json.dumps({'phase': 'verify', 'phone': verify_info['phone']})}\n\n"
                else:
                    yield f"event: status\ndata: {json.dumps({'phase': 'qrcode'})}\n\n"

                await asyncio.sleep(1)
            else:
                # 循环正常结束 = 超时
                yield f"event: status\ndata: {json.dumps({'phase': 'timeout'})}\n\n"
                logger.warning("Login stream timeout")

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
