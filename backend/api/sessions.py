from fastapi import APIRouter

from backend.scraper.engine import engine

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


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
