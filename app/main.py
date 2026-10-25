from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI

from app.api.routes import router
from app.core.database import close_db, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("swiftlink")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown lifecycle."""
    logger.info("Initializing database pools...")
    await init_db()
    logger.info("Application started successfully.")
    yield
    logger.info("Closing database pools...")
    await close_db()
    logger.info("Application shutdown complete.")


app = FastAPI(
    title="SwiftLink API — URL Shortener & Analytics",
    description=(
        "Architecture hybride de persistance : PostgreSQL (source de vérité relationnelle ACID) "
        "et Redis (cache de redirection en mémoire sub-milliseconde & compteurs atomiques temps réel)."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(router)
