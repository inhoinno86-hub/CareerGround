"""Explicit opt-in ASGI entrypoint for the isolated authentication PoC."""

from careerground.mcp.poc_server import PocSettings, build_app

app = build_app(PocSettings.from_environment())
