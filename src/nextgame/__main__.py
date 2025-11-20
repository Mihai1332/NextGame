import logging
from typing import Optional
import typer

from .config import get_settings
from .auth.openid import build_openid_redirect
from .storage.db import DB
from .api.app import create_app
import uvicorn

app = typer.Typer()

logger = logging.getLogger("nextgame")


def setup_logging(verbosity: int):
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


@app.callback()
def main_callback(
    ctx: typer.Context,
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to .env config file"
    ),
    verbose: int = typer.Option(0, "-v", count=True, help="Increase verbosity (-v, -vv)"),
):
    if config_file:
        settings = get_settings(config_file)
    else:
        settings = get_settings()
    ctx.obj = {"settings": settings, "db": DB(settings.database_url)}
    setup_logging(verbose)
    logger.debug("Settings loaded: %s", settings.model_dump(exclude={"steam_api_key"}))


@app.command()
def init_db(ctx: typer.Context):
    db: DB = ctx.obj["db"]
    db.create_all()
    typer.echo("Database initialized.")


@app.command()
def login_url(ctx: typer.Context, return_to: str = typer.Option(..., help="Return URL")):
    url = build_openid_redirect(return_to)
    typer.echo(url)

@app.command(name="serve-api")
def serve_api(
    ctx: typer.Context,
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload (dev only)"),
):

    app_instance = create_app()
    uvicorn.run(app_instance, host=host, port=port, reload=reload)

if __name__ == "__main__":
    app()
