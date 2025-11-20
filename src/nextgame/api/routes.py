from __future__ import annotations
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..config import get_settings, Settings
from ..storage.db import DB, User, Ownership, Game
from ..steam.library import update_user_library
from ..steam.service import update_user_profile
from ..recommend.recommender import recommend_games
from ..steam.client import SteamAPIClient

class UserOut(BaseModel):
    steamid: str
    persona_name: Optional[str] = None
    avatar: Optional[str] = None


class GameOut(BaseModel):
    appid: int
    name: Optional[str]
    playtime_forever: int
    playtime_2weeks: int


class RecommendationsOut(BaseModel):
    items: List[dict]
    status: str

router = APIRouter()


def get_settings_dep() -> Settings:
    return get_settings()


def get_db(settings: Settings = Depends(get_settings_dep)):
    db = DB(settings.database_url)
    try:
        yield db
    finally:
        pass


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/users/{steamid}/sync", response_model=dict)
async def sync_user(steamid: str, db: DB = Depends(get_db), settings: Settings = Depends(get_settings_dep)):
    if not settings.steam_api_key:
        raise HTTPException(400, "STEAM_API_KEY missing")
    api_key = settings.steam_api_key
    api = SteamAPIClient(api_key)
    profile_summary = await update_user_profile(db, api, steamid)
    library_summary = await update_user_library(db, api, steamid)
    return {"profile": profile_summary, "library": library_summary}


@router.get("/users/{steamid}", response_model=UserOut)
def get_user(steamid: str, db: DB = Depends(get_db)):
    with db.session() as s:
        u = s.query(User).filter_by(steamid=steamid).one_or_none()
        if not u:
            raise HTTPException(404, "User not found")
        return UserOut(steamid=u.steamid, persona_name=u.persona_name, avatar=u.avatar)


@router.get("/users/{steamid}/top", response_model=List[GameOut])
def user_top_games(steamid: str, limit: int = Query(10, ge=1, le=100), db: DB = Depends(get_db)):
    with db.session() as s:
        user = s.query(User).filter_by(steamid=steamid).one_or_none()
        if not user:
            raise HTTPException(404, "User not found")
        rows = (
            s.query(Ownership, Game)
            .join(Game, Game.appid == Ownership.appid)
            .filter(Ownership.user_id == user.id)
            .order_by(Ownership.playtime_forever.desc())
            .limit(limit)
            .all()
        )
        return [
            GameOut(
                appid=g.appid,
                name=g.name,
                playtime_forever=o.playtime_forever,
                playtime_2weeks=o.playtime_2weeks,
            )
            for (o, g) in rows
        ]


@router.get("/users/{steamid}/recommendations", response_model=RecommendationsOut)
def user_recommendations(steamid: str, db: DB = Depends(get_db)):
    result = recommend_games(db, steamid)
    if "error" in result:
        raise HTTPException(400, result["error"])
    parsed = result.get("parsed", {})
    return RecommendationsOut(items=parsed.get("items", []), status=parsed.get("status", "unknown"))
