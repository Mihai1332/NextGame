from __future__ import annotations
import urllib.parse
from typing import Optional

STEAM_OPENID_ENDPOINT = "https://steamcommunity.com/openid/login"


def build_openid_redirect(return_to: str, realm: Optional[str] = None) -> str:
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": realm or return_to.split("/", 3)[:3][2] if "//" in return_to else return_to,
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
    }
    return f"{STEAM_OPENID_ENDPOINT}?{urllib.parse.urlencode(params)}"
