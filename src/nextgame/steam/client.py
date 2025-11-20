from __future__ import annotations
import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx

STEAM_API_BASE = "https://api.steampowered.com"


class SteamAPIClient:
    def __init__(self, api_key: str, timeout: float = 10.0):
        self.api_key = api_key
        self.timeout = timeout
        self._last_request: float = 0.0
        self._backoff: float = 0.0

    async def _throttle(self):
        # throttle between requests
        now = time.time()
        delta = now - self._last_request
        if delta < 0.2:
            await asyncio.sleep(0.2 - delta)
        self._last_request = time.time()

    async def _get(self, path: str, params: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        await self._throttle()
        url = f"{STEAM_API_BASE}/{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, params=params, headers=headers)
        return resp

    async def get_player_summaries(self, steamids: List[str], *, headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        params = {"key": self.api_key, "steamids": ",".join(steamids)}
        return await self._get("ISteamUser/GetPlayerSummaries/v2", params, headers)

    async def get_owned_games(
        self,
        steamid: str,
        include_appinfo: bool = True,
        include_played_free_games: bool = True,
        *,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        params = {
            "key": self.api_key,
            "steamid": steamid,
            "include_appinfo": int(include_appinfo),
            "include_played_free_games": int(include_played_free_games),
        }
        return await self._get("IPlayerService/GetOwnedGames/v1", params, headers)
