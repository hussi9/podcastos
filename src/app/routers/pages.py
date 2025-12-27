
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

# Setup Templates
templates_dir = Path(__file__).parent.parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Render the landing page."""
    return templates.TemplateResponse("landing.html", {
        "request": request, 
        "page_title": "AI Audio content Engine"
    })

@router.get("/app", response_class=HTMLResponse)
async def app_interface(request: Request):
    """Render the main app interface."""
    return templates.TemplateResponse("app.html", {
        "request": request,
        "page_title": "Studio"
    })

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page."""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "page_title": "Log In"
    })
