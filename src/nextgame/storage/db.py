from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from sqlalchemy import create_engine, Index, JSON, ForeignKey, String, func, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    steamid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    persona_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ownerships: Mapped[list["Ownership"]] = relationship(back_populates="user")


class Game(Base):
    __tablename__ = "games"
    appid: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    last_updated: Mapped[datetime] = mapped_column(default=func.now(), server_default=func.now())
    ownerships: Mapped[list["Ownership"]] = relationship(back_populates="game")


class Ownership(Base):
    __tablename__ = "ownerships"
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    appid: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("games.appid", ondelete="CASCADE"), index=True)
    playtime_forever: Mapped[int] = mapped_column(default=0)
    playtime_2weeks: Mapped[int] = mapped_column(default=0)
    last_updated: Mapped[datetime] = mapped_column(default=func.now(), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="ownerships")
    game: Mapped[Game] = relationship(back_populates="ownerships")

    __table_args__ = (
        Index("uq_user_appid", "user_id", "appid", unique=True),
    )


class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # e.g., owned_games, player_summaries
    etag: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    last_modified: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), server_default=func.now())


@dataclass
class DB:
    engine_url: str

    def __post_init__(self):
        self.engine = create_engine(
            self.engine_url,
        )
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_all(self):
        Base.metadata.create_all(self.engine)

    def session(self):
        return self.SessionLocal()
