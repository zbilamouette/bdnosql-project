import logging
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.database import check_health
from app.models.link import DashboardData, LinkCreate, LinkResponse
from app.services.link_service import (
    LinkNotFoundError,
    SlugAlreadyExistsError,
    create_short_link,
    get_dashboard_data,
    resolve_slug_and_record_click,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home_page(request: Request, error: str | None = None, success: str | None = None):
    """Render the minimalist dashboard UI with Simple.css."""
    dashboard = await get_dashboard_data()
    settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "dashboard": dashboard,
            "base_url": settings.base_url.rstrip("/"),
            "error": error,
            "success": success,
        },
    )


@router.post("/submit", response_class=RedirectResponse)
async def submit_form(
    target_url: str = Form(...),
    title: str | None = Form(default=None),
    custom_slug: str | None = Form(default=None),
):
    """Handle standard HTML form submissions and redirect back to the home page."""
    try:
        payload = LinkCreate(
            target_url=target_url,
            title=title if title and title.strip() else None,
            custom_slug=custom_slug if custom_slug and custom_slug.strip() else None,
        )
        created = await create_short_link(payload)
        return RedirectResponse(
            url=f"/?success={created.slug}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except ValidationError as exc:
        first_err = exc.errors()[0]
        msg = first_err.get("msg", "Erreur de validation.")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        return RedirectResponse(
            url=f"/?error={quote_plus(msg)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except (SlugAlreadyExistsError, ValueError) as exc:
        return RedirectResponse(
            url=f"/?error={quote_plus(str(exc))}",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.post(
    "/api/links",
    response_model=LinkResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a shortened link",
)
async def api_create_link(payload: LinkCreate):
    """Create a shortened link, persist in PostgreSQL and cache in Redis."""
    try:
        return await create_short_link(payload)
    except SlugAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.get(
    "/api/links",
    response_model=DashboardData,
    summary="Get all links and metrics",
)
async def api_get_links():
    """Fetch all stored links from PostgreSQL merged with Redis real-time analytics."""
    return await get_dashboard_data()


@router.get(
    "/r/{slug}",
    response_class=RedirectResponse,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    summary="Redirect short link to original target URL",
)
async def redirect_to_target(slug: str):
    """Resolve slug from Redis (or fallback PostgreSQL) and increment real-time click metrics."""
    try:
        target_url = await resolve_slug_and_record_click(slug)
        return RedirectResponse(url=target_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    except LinkNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lien court inexistant pour '/r/{slug}'",
        ) from exc


@router.get(
    "/health",
    summary="Check system and database health",
)
async def health():
    """Verify connectivity to PostgreSQL and Redis."""
    status_report = await check_health()
    all_ok = all(v == "ok" for v in status_report.values())
    http_code = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if all_ok else "degraded", "services": status_report}
