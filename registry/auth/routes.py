import logging
from typing import Annotated

from fastapi import APIRouter, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ..core.config import settings
from .dependencies import create_session_cookie, validate_login_credentials

logger = logging.getLogger(__name__)

router = APIRouter()

# Templates
templates = Jinja2Templates(directory=settings.templates_dir)


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, error: str | None = None):
    """Show simple login form"""
    return templates.TemplateResponse(
        "login.html", 
        {
            "request": request, 
            "error": error
        }
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: Annotated[str, Form()], 
    password: Annotated[str, Form()]
):
    """Handle login form submission - supports both traditional and API calls"""
    logger.info(f"Login attempt for username: {username}")
    
    # Check if this is an API call (React) or traditional form submission
    accept_header = request.headers.get("accept", "")
    is_api_call = "application/json" in accept_header
    
    if validate_login_credentials(username, password):
        session_data = create_session_cookie(username)
        
        if is_api_call:
            # API response for React
            response = JSONResponse(content={"success": True, "message": "Login successful"})
        else:
            # Traditional redirect response
            response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        
        response.set_cookie(
            key=settings.session_cookie_name,
            value=session_data,
            max_age=settings.session_max_age_seconds,
            httponly=True,
            samesite="lax",
        )
        logger.info(f"User '{username}' logged in successfully.")
        return response
    else:
        logger.info(f"Login failed for user '{username}'.")
        
        if is_api_call:
            # API error response for React
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        else:
            # Traditional redirect with error
            return RedirectResponse(
                url="/login?error=Invalid+username+or+password",
                status_code=status.HTTP_303_SEE_OTHER,
            )


@router.get("/logout")
async def logout_get(request: Request):
    """Handle logout via GET request"""
    logger.info("User logged out.")
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.session_cookie_name)
    return response


@router.post("/logout")
async def logout_post(request: Request):
    """Handle logout via POST request"""
    logger.info("User logged out.")
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.session_cookie_name)
    return response