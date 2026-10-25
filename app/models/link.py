from datetime import datetime
from pydantic import BaseModel, Field, HttpUrl, field_validator


class LinkCreate(BaseModel):
    """Schema for creating a short link."""
    target_url: HttpUrl = Field(
        ...,
        description="Original target URL to shorten (must include http:// or https://)",
        examples=["https://github.com"],
    )
    title: str | None = Field(
        default=None,
        max_length=200,
        description="Optional title or description for this URL",
    )
    custom_slug: str | None = Field(
        default=None,
        min_length=3,
        max_length=64,
        description="Optional custom slug (alphanumeric, dashes and underscores only)",
    )

    @field_validator("custom_slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip().lower()
        if not cleaned:
            return None

        # Si l'utilisateur a entré une URL complète (ex: http://youyou ou http://host/r/youyou)
        import re
        from urllib.parse import urlparse

        if cleaned.startswith(("http://", "https://")):
            parsed = urlparse(cleaned)
            path = parsed.path.strip("/")
            if path.startswith("r/"):
                cleaned = path[2:].strip("/")
            elif path:
                cleaned = path
            elif parsed.netloc:
                cleaned = parsed.netloc.split(":")[0]

        # Si préfixé par /r/ ou /
        if cleaned.startswith("/"):
            cleaned = cleaned.lstrip("/")
        if cleaned.startswith("r/"):
            cleaned = cleaned[2:].lstrip("/")

        if not cleaned:
            return None

        if len(cleaned) < 3 or len(cleaned) > 64:
            raise ValueError("L'identifiant court doit comporter entre 3 et 64 caractères.")

        if not re.match(r"^[a-zA-Z0-9_-]+$", cleaned):
            raise ValueError(
                f"L'identifiant '{cleaned}' est invalide : seuls les lettres, chiffres, tirets (-) et underscores (_) sont autorisés."
            )

        reserved = {"api", "r", "docs", "health", "static", "openapi.json", "submit"}
        if cleaned in reserved:
            raise ValueError(f"'{cleaned}' est un mot-clé réservé par l'application et ne peut pas servir d'identifiant.")

        return cleaned


class LinkResponse(BaseModel):
    """Schema for returning link data to clients."""
    id: int
    slug: str
    target_url: str
    title: str
    created_at: datetime
    short_url: str
    clicks: int = 0
    in_redis_cache: bool = False


class PopularLink(BaseModel):
    """Top ranking link from Redis sorted set."""
    slug: str
    clicks: int


class DashboardData(BaseModel):
    """Aggregated stats and link listings for the dashboard."""
    total_links: int
    total_clicks: int
    links: list[LinkResponse]
    popular_links: list[PopularLink]
