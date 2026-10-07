"""Build an allowlisted plugin archive without secrets or unrelated repo files.

No installation, network calls, publication, or config changes occur here.
Choose skills-only, a registered private server, or a reviewed HTTPS endpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugins" / "careerground"
SKILL = "skills/career-interview/SKILL.md"


def build_archive(
    output: Path, *, registered_server_id: str | None = None, mcp_url: str | None = None
) -> tuple[str, ...]:
    """Include only the manifest, actual skill and explicitly configured binding."""
    if registered_server_id and mcp_url:
        raise ValueError("Choose one server binding")
    if registered_server_id and not re.fullmatch(
        r"(?:asdk_app_|connector_|templated_apps_)[A-Za-z0-9][A-Za-z0-9_-]*",
        registered_server_id,
    ):
        raise ValueError("Invalid registered server ID")
    if mcp_url:
        parsed = urlsplit(mcp_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or any(c.isspace() for c in mcp_url)
            or "\\" in mcp_url
            or parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            or not (
                parsed.path == "/mcp" or re.fullmatch(r"/v1/mcp/tunnel_[0-9a-f]{32}", parsed.path)
            )
        ):
            raise ValueError("A reviewed HTTPS MCP endpoint is required")
    for name in ("plugin.json", SKILL):
        path = SOURCE / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Missing regular package source")
    manifest = json.loads((SOURCE / "plugin.json").read_text())
    files = {SKILL: (SOURCE / SKILL).read_bytes()}
    if registered_server_id:
        manifest["extensions"]["com.openai"]["apps"] = "./.app.json"
        files[".app.json"] = json.dumps(
            {"apps": {"careerground": {"id": registered_server_id, "required": True}}}
        ).encode()
    elif mcp_url:
        files["mcp.json"] = json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                "mcpServers": {"careerground": {"type": "streamable-http", "url": mcp_url}},
            }
        ).encode()
    files["plugin.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
    # O_EXCL/O_NOFOLLOW protects existing files and symlink targets.
    fd = os.open(output, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with (
            os.fdopen(fd, "w+b") as stream,
            zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive,
        ):
            for name, content in sorted(files.items()):
                archive.writestr(name, content)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return tuple(sorted(files))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    binding = parser.add_mutually_exclusive_group()
    binding.add_argument("--registered-server-id")
    binding.add_argument("--mcp-url")
    args = parser.parse_args()
    members = build_archive(
        args.output, registered_server_id=args.registered_server_id, mcp_url=args.mcp_url
    )
    print(
        json.dumps(
            {
                "archive": str(args.output),
                "members": members,
                "installed": False,
                "published": False,
            }
        )
    )


if __name__ == "__main__":
    main()
