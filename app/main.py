import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from pymongo import MongoClient

PG_DSN = os.environ["PG_DSN"]
MONGO_URI = os.environ["MONGO_URI"]
MONGO_DB = os.environ.get("MONGO_DB", "nosql")

mongo_client = MongoClient(MONGO_URI)
mongo_collection = mongo_client[MONGO_DB]["submissions"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    with psycopg.connect(PG_DSN) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submissions (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(200) NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        conn.execute("ALTER TABLE submissions ADD COLUMN IF NOT EXISTS rating INTEGER")
    yield
    mongo_client.close()


app = FastAPI(title="Livre d'or API", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


class Submission(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=3, max_length=200)
    message: str = Field(min_length=1, max_length=2000)
    rating: int | None = Field(default=None, ge=1, le=5)


def save_submission(sub: Submission) -> dict:
    created_at = datetime.now(timezone.utc)

    with psycopg.connect(PG_DSN) as conn:
        pg_id = conn.execute(
            "INSERT INTO submissions (name, email, message, created_at, rating) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (sub.name, sub.email or "", sub.message, created_at, sub.rating),
        ).fetchone()[0]

    result = mongo_collection.insert_one(
        {**sub.model_dump(), "created_at": created_at, "pg_id": pg_id}
    )

    return {"postgres_id": pg_id, "mongo_id": str(result.inserted_id)}


def list_postgres() -> list[dict]:
    with psycopg.connect(PG_DSN, row_factory=dict_row) as conn:
        return conn.execute(
            "SELECT id, name, email, message, created_at, rating "
            "FROM submissions ORDER BY id DESC LIMIT 50"
        ).fetchall()


def list_mongo() -> list[dict]:
    docs = mongo_collection.find().sort("_id", -1).limit(50)
    return [{**d, "_id": str(d["_id"])} for d in docs]


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"pg_rows": list_postgres(), "mongo_docs": list_mongo()},
    )


@app.post("/submit")
def submit_form(
    name: str = Form(min_length=1, max_length=100),
    message: str = Form(min_length=1, max_length=2000),
    email: str | None = Form(default=None, min_length=3, max_length=200),
    rating: int | None = Form(default=None, ge=1, le=5),
):
    save_submission(Submission(name=name, email=email, message=message, rating=rating))
    return RedirectResponse("/", status_code=303)


@app.post("/api/submissions", status_code=201)
def create_submission(sub: Submission):
    return save_submission(sub)


@app.get("/api/submissions")
def get_submissions():
    return {"postgres": list_postgres(), "mongodb": list_mongo()}


@app.get("/health")
def health():
    with psycopg.connect(PG_DSN) as conn:
        conn.execute("SELECT 1")
    mongo_client.admin.command("ping")
    return {"postgres": "ok", "mongodb": "ok"}
