from __future__ import annotations
from typing import Optional
from datetime import datetime


from .client import SteamAPIClient
from ..storage.db import DB, User, Game, Ownership, Snapshot


async def update_user_library(db: DB, api: SteamAPIClient, steamid: str) -> dict:
    with db.session() as s: 
        user = s.query(User).filter_by(steamid=steamid).one_or_none()
        if not user:
            user = User(steamid=steamid)
            s.add(user)
            s.flush()

        # headers from last snapshot
        last_snap: Optional[Snapshot] = (
            s.query(Snapshot)
            .filter_by(user_id=user.id, kind="owned_games")
            .order_by(Snapshot.id.desc())
            .first()
        )
        headers = {}
        if last_snap:
            if last_snap.etag:
                headers["If-None-Match"] = last_snap.etag
            if last_snap.last_modified:
                headers["If-Modified-Since"] = last_snap.last_modified

    # request
    resp = await api.get_owned_games(steamid, headers=headers)

    if resp.status_code == 304:
        return {"status": "not_modified"}

    resp.raise_for_status()
    owned = resp.json()

    etag = resp.headers.get("ETag")
    last_modified = resp.headers.get("Last-Modified")

    response = owned.get("response", {})
    games = response.get("games", [])

    summary = {"games": len(games), "upserted_games": 0, "upserted_ownerships": 0}

    with db.session() as s: 
        user = s.query(User).filter_by(steamid=steamid).one_or_none()
        
        if not user:
            return

        snap = Snapshot(
            user_id=user.id, kind="owned_games", payload=owned, etag=etag, last_modified=last_modified
        )
        s.add(snap)

        for g in games:
            appid = int(g.get("appid"))
            name = g.get("name")
            playtime_forever = int(g.get("playtime_forever", 0))
            playtime_2weeks = int(g.get("playtime_2weeks", 0))

            game = s.get(Game, appid)
            if not game:
                game = Game(appid=appid, name=name, last_updated=datetime.utcnow())
                s.add(game)
                summary["upserted_games"] += 1
            else:
                if name and game.name != name:
                    game.name = name
                game.last_updated = datetime.utcnow()

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
                    last_updated=datetime.utcnow(),
                )
                s.add(own)
                summary["upserted_ownerships"] += 1
            else:
                own.playtime_forever = playtime_forever
                own.playtime_2weeks = playtime_2weeks
                own.last_updated = datetime.utcnow()

        s.commit()

    return summary
