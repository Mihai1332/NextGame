from __future__ import annotations
import os
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    steam_api_key: Optional[str] = Field(default=None, description="Steam Web API key")
    steam_id: Optional[str] = Field(default=None, description="User SteamID64 for dev mode")
    environment: str = Field(default="dev")
    database_url: str = Field(
        default="mysql+pymysql://user:password@localhost:3306/nextgame?charset=utf8mb4"
    )
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key for recommendations")

def get_settings(env_file: Optional[str] = None) -> Settings:
    if env_file and os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        load_dotenv()
    data = {
        "steam_api_key": os.getenv("STEAM_API_KEY"),
        "steam_id": os.getenv("STEAM_ID"),
        "environment": os.getenv("NEXTGAME_ENV", "dev"),
        "database_url": os.getenv(
            "DATABASE_URL",
            "mysql+pymysql://user:password@localhost:3306/nextgame?charset=utf8mb4",
        ),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
    }
    return Settings(**data)
