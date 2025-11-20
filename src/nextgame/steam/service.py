from __future__ import annotations
from typing import Optional
import asyncio

from ..storage.db import DB, User, Snapshot, Game, Ownership
from .client import SteamAPIClient


async def update_user_profile(db: DB, api: SteamAPIClient, steamid: str) -> dict:
    # contitional headers from last snapshot
    with db.session() as s:
        user = s.query(User).filter_by(steamid=steamid).one_or_none()
        if not user:
            user = User(steamid=steamid)
            s.add(user)
            s.flush()

        last_snap: Optional[Snapshot] = (
            s.query(Snapshot)
            .filter_by(user_id=user.id, kind="player_summaries")
            .order_by(Snapshot.id.desc())
            .first()
        )
        headers = {}
        if last_snap:
            if last_snap.etag:
                headers["If-None-Match"] = last_snap.etag
            if last_snap.last_modified:
                headers["If-Modified-Since"] = last_snap.last_modified

    resp = await api.get_player_summaries([steamid], headers=headers)

    if resp.status_code == 304:
        return {"status": "not_modified"}

    resp.raise_for_status()
    payload = resp.json()
    etag = resp.headers.get("ETag")
    last_modified = resp.headers.get("Last-Modified")

    # player details
    player: Optional[dict] = None
    try:
        players = payload.get("response", {}).get("players", [])
        if players:
            player = players[0]
    except Exception:
        player = None

    with db.session() as s: 
        user = s.query(User).filter_by(steamid=steamid).one_or_none()
        if not user:
            user = User(steamid=steamid)
            s.add(user)
            s.flush()

        # store snapshot
        snap = Snapshot(
            user_id=user.id,
            kind="player_summaries",
            payload=payload,
            etag=etag,
            last_modified=last_modified,
        )
        s.add(snap)

        # update user
        if player:
            persona_name = player.get("personaname")
            avatar = (
                player.get("avatarfull")
                or player.get("avatarfull_url")
                or player.get("avatar")
            )
            if persona_name is not None:
                user.persona_name = persona_name
            if avatar is not None:
                user.avatar = avatar

        s.commit()

    return {"status": "ok", "updated_user": True if player else False}


def sync_owned_games(db: DB, api: SteamAPIClient, steamid: str) -> dict:
    # check if user exists
    with db.session() as s: 
        user = s.query(User).filter_by(steamid=steamid).one_or_none()
        if not user:
            user = User(steamid=steamid)
            s.add(user)
            s.flush()

    # call Steam 
    ps_resp = asyncio.run(api._get("ISteamUser/GetPlayerSummaries/v0002/", {"key": api.api_key, "steamids": steamid}))
    og_resp = asyncio.run(
        api._get(
            "IPlayerService/GetOwnedGames/v0001/",
            {"key": api.api_key, "steamid": steamid, "include_appinfo": 1, "include_played_free_games": 1},
        )
    )

    ps_resp.raise_for_status()
    og_resp.raise_for_status()

    ps = ps_resp.json()
    owned = og_resp.json()

    player = None
    try:
        players = ps.get("response", {}).get("players", [])
        if players:
            player = players[0]
    except Exception:
        player = None

    games = owned.get("response", {}).get("games", []) or []

    with db.session() as s:
        user = s.query(User).filter_by(steamid=steamid).one()

        # Update user fields
        if player:
            persona_name = player.get("personaname")
            avatar = (
                player.get("avatarfull")
                or player.get("avatarfull_url")
                or player.get("avatar")
            )
            if persona_name is not None:
                user.persona_name = persona_name
            if avatar is not None:
                user.avatar = avatar

        # update games/owns
        for g in games:
            appid = int(g.get("appid"))
            name = g.get("name")
            playtime_forever = int(g.get("playtime_forever", 0))
            playtime_2weeks = int(g.get("playtime_2weeks", 0))

            game = s.get(Game, appid)
            if not game:
                game = Game(appid=appid, name=name)
                s.add(game)
            else:
                if name and game.name != name:
                    game.name = name

            own = (
                s.query(Ownership)
                .filter(Ownership.user_id == user.id, Ownership.appid == appid)
                .one_or_none()
            )
            if not own:
                own = Ownership(
                    user_id=user.id,
                    appid=appid,
                    playtime_forever=playtime_forever,
                    playtime_2weeks=playtime_2weeks,
                )
                s.add(own)
            else:
                own.playtime_forever = playtime_forever
                own.playtime_2weeks = playtime_2weeks

        s.commit()

    return {"status": "ok", "games_seen": len(games)}
