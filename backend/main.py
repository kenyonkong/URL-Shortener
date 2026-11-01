import os
import secrets
import sqlite3
import string
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Iterator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, HttpUrl


DATABASE_PATH = Path(
    os.getenv("URL_SHORTENER_DB", Path(__file__).with_name("url_shortener.db"))
)
SHORT_CODE_LENGTH = 7
SHORT_CODE_ALPHABET = string.ascii_letters + string.digits
MAX_VISITS = 5


class ShortenRequest(BaseModel):
    url: HttpUrl


class ShortenResponse(BaseModel):
    original_url: str
    shortened_url: str
    short_code: str
    access_count: int


class ResolveResponse(BaseModel):
    original_url: str


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_url TEXT NOT NULL UNIQUE,
                short_code TEXT NOT NULL UNIQUE,
                access_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="URL Shortener API", lifespan=lifespan)


def get_or_create_short_code(original_url: str) -> tuple[str, int]:
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT short_code, access_count FROM urls WHERE original_url = ?",
            (original_url,),
        ).fetchone()
        if existing:
            return existing["short_code"], existing["access_count"]

        while True:
            short_code = "".join(
                secrets.choice(SHORT_CODE_ALPHABET) for _ in range(SHORT_CODE_LENGTH)
            )
            try:
                connection.execute(
                    "INSERT INTO urls (original_url, short_code) VALUES (?, ?)",
                    (original_url, short_code),
                )
                return short_code, 0
            except sqlite3.IntegrityError:
                # A concurrent request may have inserted this URL, or the random
                # code may already exist. Reuse the URL's code or generate another.
                existing = connection.execute(
                    "SELECT short_code, access_count FROM urls WHERE original_url = ?",
                    (original_url,),
                ).fetchone()
                if existing:
                    return existing["short_code"], existing["access_count"]


def use_short_url(short_code: str) -> str:
    with get_connection() as connection:
        result = connection.execute(
            """
            UPDATE urls
            SET access_count = access_count + 1
            WHERE short_code = ? AND access_count < ?
            """,
            (short_code, MAX_VISITS),
        )
        row = connection.execute(
            "SELECT original_url FROM urls WHERE short_code = ?", (short_code,)
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Short URL not found")

        if result.rowcount != 1:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Short URL visit limit reached",
            )

    return row["original_url"]


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/shorten",
    response_model=ShortenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def shorten_url(payload: ShortenRequest, request: Request) -> ShortenResponse:
    original_url = str(payload.url)
    short_code, access_count = get_or_create_short_code(original_url)
    shortened_url = f"{str(request.base_url).rstrip('/')}/{short_code}"
    return ShortenResponse(
        original_url=original_url,
        shortened_url=shortened_url,
        short_code=short_code,
        access_count=access_count,
    )


@app.get("/api/urls", response_model=list[ShortenResponse])
async def list_short_urls(request: Request) -> list[ShortenResponse]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT original_url, short_code, access_count
            FROM urls
            ORDER BY id DESC
            """
        ).fetchall()

    base_url = str(request.base_url).rstrip("/")
    return [
        ShortenResponse(
            original_url=row["original_url"],
            shortened_url=f"{base_url}/{row['short_code']}",
            short_code=row["short_code"],
            access_count=row["access_count"],
        )
        for row in rows
    ]


@app.post("/api/resolve/{short_code}", response_model=ResolveResponse)
async def resolve_short_url(short_code: str) -> ResolveResponse:
    return ResolveResponse(original_url=use_short_url(short_code))


@app.get("/{short_code}", include_in_schema=False)
async def redirect_short_url(short_code: str) -> RedirectResponse:
    original_url = use_short_url(short_code)
    return RedirectResponse(url=original_url, status_code=307)

