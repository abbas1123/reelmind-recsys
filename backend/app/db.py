"""SQLite persistence for application data (profiles, ratings, favorites, interactions).

MovieLens ratings stay in the processed parquet files and are not duplicated here;
the ``items`` table mirrors the catalog so the API can join and filter cheaply.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
    event,
    func,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from recsys.config import Settings

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80))
    ml_user_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    preferences: Mapped[list[UserGenrePreference]] = relationship(cascade="all, delete-orphan")
    ratings: Mapped[list[Rating]] = relationship(cascade="all, delete-orphan")
    favorites: Mapped[list[Favorite]] = relationship(cascade="all, delete-orphan")


class UserGenrePreference(Base):
    __tablename__ = "user_genre_preferences"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    genre: Mapped[str] = mapped_column(String(40), primary_key=True)


class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # dataset item id (MovieLens movieId)
    domain: Mapped[str] = mapped_column(String(20), index=True, default="movie")
    title: Mapped[str] = mapped_column(String(300), index=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    genres: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    external_ids: Mapped[dict] = mapped_column(JSON, default=dict)


class Rating(Base):
    __tablename__ = "ratings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    rating: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Interaction(Base):
    __tablename__ = "interactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # view | click | search | rate | favorite
    query: Mapped[str | None] = mapped_column(String(200), nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


# ------------------------------------------------------------------ engine setup
_ENGINES: dict[str, Engine] = {}


def get_engine(settings: Settings) -> Engine:
    url = f"sqlite:///{settings.p.db_path.as_posix()}"
    if url not in _ENGINES:
        settings.p.db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()

        _ENGINES[url] = engine
    return _ENGINES[url]


def session_factory(settings: Settings) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(settings), expire_on_commit=False)


def init_db(settings: Settings) -> None:
    Base.metadata.create_all(get_engine(settings))


def seed_items(settings: Settings) -> int:
    """Load the processed catalog into the items table (idempotent: existing ids are updated)."""
    path = settings.p.processed_dir / "items.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing. Run `uv run recsys preprocess` first.")
    df = pd.read_parquet(path)
    Session_ = session_factory(settings)
    with Session_() as s:
        existing = {i for (i,) in s.execute(select(Item.id))}
        for row in df.itertuples(index=False):
            values = {
                "id": int(row.item_id),
                "domain": str(row.domain),
                "title": str(row.title),
                "year": int(row.year) if pd.notna(row.year) else None,
                "genres": list(row.genres),
                "tags": list(row.tags),
                "external_ids": json.loads(row.external_ids) if isinstance(row.external_ids, str) else {},
            }
            if values["id"] in existing:
                s.merge(Item(**values))
            else:
                s.add(Item(**values))
        s.commit()
        return int(s.scalar(select(func.count()).select_from(Item)) or 0)


def iter_session(factory: sessionmaker[Session]) -> Iterator[Session]:
    with factory() as session:
        yield session
