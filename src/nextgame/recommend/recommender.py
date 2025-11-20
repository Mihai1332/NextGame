from __future__ import annotations
from typing import Dict, List
import json

from pydantic import BaseModel, ValidationError, Field

from ..config import get_settings
from ..storage.db import DB, User, Ownership, Game, Snapshot
from openai import OpenAI


class Recommendation(BaseModel):
    appid: int
    title: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)

def build_prompt(user: User, owned: List[Ownership], games: Dict[int, Game]) -> str:
    candidates = sorted(
        owned,
        key=lambda o: (o.playtime_2weeks, -o.playtime_forever),
    )[:40]
    lines: List[str] = []
    for o in candidates:
        g = games.get(o.appid)
        title = (g.name if g and g.name else f"App {o.appid}")
        lines.append(
            f"- {title} (appid {o.appid}, total {o.playtime_forever} min, recent {o.playtime_2weeks} min)"
        )
    prompt = (
        "The user owns these Steam games. Recommend exactly 5 games to play next with a brief rationale, "
        "balancing novelty and past engagement.\n" + "\n".join(lines) +
        "\nReturn strict JSON array: [{\"appid\":123,\"title\":\"...\",\"reason\":\"...\"}]."
    )
    return prompt

def _extract_json_array(text: str) -> str | None:

    stripped = text.strip()
    if stripped.startswith("["):
        return stripped

    start = stripped.find("[")
    if start == -1:
        return None
    depth = 0
    for idx in range(start, len(stripped)):
        ch = stripped[idx]
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                candidate = stripped[start:idx + 1]
                return candidate
    return None


def parse_recommendations(raw: str) -> dict:
    json_fragment = _extract_json_array(raw)
    if not json_fragment:
        return {"status": "parse_error", "errors": ["No JSON array found"], "items": []}
    try:
        data = json.loads(json_fragment)
    except json.JSONDecodeError as e:
        return {"status": "parse_error", "errors": [f"JSON decode error: {e}"], "items": []}
    if not isinstance(data, list):
        return {"status": "parse_error", "errors": ["Top-level JSON is not a list"], "items": []}
    items: List[Recommendation] = []
    errors: List[str] = []
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            errors.append(f"Item {i} not an object")
            continue
        try:
            rec = Recommendation(
                appid=int(entry.get("appid")),
                title=str(entry.get("title")),
                reason=str(entry.get("reason")),
            )
            items.append(rec)
        except (ValueError, ValidationError) as exc:
            errors.append(f"Item {i} validation failed: {exc}")
    if not items:
        return {"status": "parse_error", "errors": errors or ["No valid items"], "items": []}
    items = items[:5]
    return {"status": "ok", "items": [r.model_dump() for r in items], "errors": errors}


def recommend_games(db: DB, steamid: str) -> dict:
    settings = get_settings()
    if not settings.openai_api_key:
        return {"error": "OPENAI_API_KEY missing"}

    with db.session() as s:
        user = s.query(User).filter_by(steamid=steamid).one_or_none()
        if not user:
            return {"error": "user not found"}

        owned: List[Ownership] = s.query(Ownership).filter_by(user_id=user.id).all()
        if not owned:
            return {"error": "no ownership data"}

        game_ids = [o.appid for o in owned]
        games = {g.appid: g for g in s.query(Game).filter(Game.appid.in_(game_ids)).all()}

        prompt = build_prompt(user, owned, games)
        client = OpenAI(api_key=settings.openai_api_key) 
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a concise game recommendation assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        content = completion.choices[0].message.content or ""
        parsed = parse_recommendations(content)
        snap = Snapshot(user_id=user.id, kind="recommendations", payload={"raw": content, "parsed": parsed})
        s.add(snap)
        s.commit()

        return {"status": "ok", "raw": content, "parsed": parsed}
