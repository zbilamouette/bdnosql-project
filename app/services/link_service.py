import logging
import secrets
import string
from urllib.parse import urlparse

from psycopg.errors import UniqueViolation

from app.core.config import get_settings
from app.core.database import get_pg_connection, get_redis
from app.models.link import DashboardData, LinkCreate, LinkResponse, PopularLink

logger = logging.getLogger(__name__)

ALPHABET = string.ascii_lowercase + string.digits


def generate_random_slug(length: int = 6) -> str:
    """Generate a clean, url-safe random slug."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


class SlugAlreadyExistsError(Exception):
    """Raised when a slug is already taken."""
    pass


class LinkNotFoundError(Exception):
    """Raised when a short link is not found."""
    pass


async def create_short_link(data: LinkCreate) -> LinkResponse:
    """Create a new short link, persist in PostgreSQL and cache in Redis."""
    settings = get_settings()
    redis = get_redis()
    target_url_str = str(data.target_url)

    # Determine title
    if data.title and data.title.strip():
        title = data.title.strip()
    else:
        parsed = urlparse(target_url_str)
        title = parsed.netloc or target_url_str[:50]

    slug = data.custom_slug if data.custom_slug else generate_random_slug()

    # Retry generation up to 3 times if collision with random slug
    for attempt in range(4):
        try:
            async with get_pg_connection() as conn:
                cursor = await conn.execute(
                    """
                    INSERT INTO urls (slug, target_url, title, created_at)
                    VALUES (%s, %s, %s, NOW())
                    RETURNING id, slug, target_url, title, created_at
                    """,
                    (slug, target_url_str, title),
                )
                row = await cursor.fetchone()
                break
        except UniqueViolation:
            if data.custom_slug:
                raise SlugAlreadyExistsError(f"Le slug '{data.custom_slug}' est déjà utilisé.")
            if attempt == 3:
                raise RuntimeError("Impossible de générer un slug unique. Veuillez réessayer.")
            slug = generate_random_slug()

    # Populate Redis: cache URL + init click counter
    pipe = redis.pipeline()
    pipe.set(f"url:{row['slug']}", target_url_str)
    pipe.setnx(f"clicks:{row['slug']}", 0)
    pipe.zadd("popular_urls", {row['slug']: 0}, nx=True)
    await pipe.execute()

    short_url = f"{settings.base_url.rstrip('/')}/r/{row['slug']}"
    return LinkResponse(
        id=row["id"],
        slug=row["slug"],
        target_url=row["target_url"],
        title=row["title"],
        created_at=row["created_at"],
        short_url=short_url,
        clicks=0,
        in_redis_cache=True,
    )


async def resolve_slug_and_record_click(slug: str) -> str:
    """Resolve a short slug to its target URL and record atomic click metrics in Redis."""
    redis = get_redis()
    slug = slug.strip().lower()

    # 1. Fast path: check Redis cache
    target_url = await redis.get(f"url:{slug}")

    # 2. Slow path: check PostgreSQL on cache miss
    if not target_url:
        async with get_pg_connection() as conn:
            cursor = await conn.execute(
                "SELECT target_url FROM urls WHERE slug = %s",
                (slug,),
            )
            row = await cursor.fetchone()
            if not row:
                raise LinkNotFoundError(f"Lien court inexistant pour le slug '{slug}'.")
            target_url = row["target_url"]

        # Re-populate Redis cache
        await redis.set(f"url:{slug}", target_url)

    # 3. Atomically increment metrics in Redis
    pipe = redis.pipeline()
    pipe.incr(f"clicks:{slug}")
    pipe.zincrby("popular_urls", 1, slug)
    await pipe.execute()

    return target_url


async def get_dashboard_data() -> DashboardData:
    """Aggregate links from PostgreSQL and real-time click metrics from Redis."""
    settings = get_settings()
    redis = get_redis()

    # Query PostgreSQL
    async with get_pg_connection() as conn:
        cursor = await conn.execute(
            """
            SELECT id, slug, target_url, title, created_at
            FROM urls
            ORDER BY id DESC
            LIMIT 50
            """
        )
        rows = await cursor.fetchall()

    if not rows:
        return DashboardData(
            total_links=0,
            total_clicks=0,
            links=[],
            popular_links=[],
        )

    # Query Redis in pipeline for high performance
    pipe = redis.pipeline()
    for row in rows:
        pipe.get(f"clicks:{row['slug']}")
        pipe.exists(f"url:{row['slug']}")
    redis_results = await pipe.execute()

    total_clicks = 0
    links: list[LinkResponse] = []

    for idx, row in enumerate(rows):
        clicks_raw = redis_results[idx * 2]
        is_cached_raw = redis_results[idx * 2 + 1]

        clicks = int(clicks_raw) if clicks_raw else 0
        total_clicks += clicks

        links.append(
            LinkResponse(
                id=row["id"],
                slug=row["slug"],
                target_url=row["target_url"],
                title=row["title"],
                created_at=row["created_at"],
                short_url=f"{settings.base_url.rstrip('/')}/r/{row['slug']}",
                clicks=clicks,
                in_redis_cache=bool(is_cached_raw),
            )
        )

    # Top popular links from Redis sorted set
    top_raw = await redis.zrevrange("popular_urls", 0, 4, withscores=True)
    popular_links = [
        PopularLink(slug=slug, clicks=int(score))
        for slug, score in top_raw
        if int(score) > 0
    ]

    return DashboardData(
        total_links=len(links),
        total_clicks=total_clicks,
        links=links,
        popular_links=popular_links,
    )
