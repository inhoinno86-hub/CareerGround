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
PORTABLE_SOURCE = ROOT / "plugins" / "careerground-portable"
PORTABLE_SOURCE_MEMBERS = (
    "plugin.json",
    "README.md",
    "skills/setup/SKILL.md",
    "skills/career-collect/SKILL.md",
    "skills/career-review/SKILL.md",
    "skills/base-resume/SKILL.md",
    "skills/jd-discover/SKILL.md",
    "skills/resume-tailor/SKILL.md",
    "skills/interview-export/SKILL.md",
    "skills/interview-review/SKILL.md",
    "templates/project-instructions.md",
    "templates/workspace-review.md",
    "templates/resume.md",
    "templates/jd-mapping.md",
    "references/workflow.md",
    "references/workflow.py",
    "references/portable.py",
    "references/exchange.py",
    "references/exchange-contract.md",
    "references/schemas/workspace-1.0.schema.json",
    "references/schemas/handoff-1.0.schema.json",
    "references/schemas/result-1.0.schema.json",
)
COMMON_SKILL_RESOURCES = (
    "references/workflow.md",
    "references/workflow.py",
    "references/portable.py",
    "references/schemas/workspace-1.0.schema.json",
    "templates/workspace-review.md",
)
EXCHANGE_SKILL_RESOURCES = (
    "references/exchange-contract.md",
    "references/exchange.py",
    "references/schemas/handoff-1.0.schema.json",
    "references/schemas/result-1.0.schema.json",
)
# skills.read resolves supporting resources within one skill, unlike a whole
# filesystem plugin cache. Generate identical per-skill copies from reviewed
# canonical files, without maintaining divergent copies in the repository.
PORTABLE_SKILL_RESOURCES = {
    "setup": COMMON_SKILL_RESOURCES + ("templates/project-instructions.md",),
    "career-collect": COMMON_SKILL_RESOURCES,
    "career-review": COMMON_SKILL_RESOURCES,
    "base-resume": COMMON_SKILL_RESOURCES + ("templates/resume.md",),
    "jd-discover": COMMON_SKILL_RESOURCES,
    "resume-tailor": COMMON_SKILL_RESOURCES + ("templates/jd-mapping.md",),
    "interview-export": COMMON_SKILL_RESOURCES + EXCHANGE_SKILL_RESOURCES,
    "interview-review": COMMON_SKILL_RESOURCES + EXCHANGE_SKILL_RESOURCES,
}
PORTABLE_MEMBERS = PORTABLE_SOURCE_MEMBERS + tuple(
    f"skills/{skill}/{resource}"
    for skill, resources in PORTABLE_SKILL_RESOURCES.items()
    for resource in resources
)


def portable_files():
    """Strict source allowlist; parent symlinks and unreviewed bindings are rejected."""
    files = {}
    if PORTABLE_SOURCE.is_symlink():
        raise ValueError("Symlink package source")
    for name in PORTABLE_SOURCE_MEMBERS:
        path = PORTABLE_SOURCE / name
        if (
            path.is_symlink()
            or not path.is_file()
            or any(p.is_symlink() for p in path.parents)
            or not path.resolve().is_relative_to(PORTABLE_SOURCE.resolve())
        ):
            raise ValueError("Missing regular portable package source")
        files[name] = path.read_bytes()
    for skill, resources in PORTABLE_SKILL_RESOURCES.items():
        for resource in resources:
            files[f"skills/{skill}/{resource}"] = files[resource]
    manifest = json.loads(files["plugin.json"])
    openai = manifest["extensions"]["com.openai"]
    if (
        manifest["name"] != "careerground-portable"
        or openai.get("onboardingSkill") != "./skills/setup/SKILL.md"
        or "apps" in openai
        or "mcpServers" in manifest
        or "mcp" in manifest
    ):
        raise ValueError("Invalid skills-only manifest")
    # Every Markdown resource link must point to an included member, not the repo.
    for name, content in files.items():
        if not name.endswith(".md"):
            continue
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content.decode()):
            if target.startswith(("https://", "http://", "#")):
                continue
            linked = (PORTABLE_SOURCE / name).parent / target.split("#")[0]
            try:
                member = linked.resolve().relative_to(PORTABLE_SOURCE.resolve()).as_posix()
            except ValueError as error:
                raise ValueError("Package link escapes source") from error
            if member not in files:
                raise ValueError("Package link target missing")
    return files


def build_archive(
    output: Path,
    *,
    registered_server_id: str | None = None,
    mcp_url: str | None = None,
    variant: str = "legacy",
) -> tuple[str, ...]:
    """Build the selected allowlist; portable packages reject all server bindings."""
    if variant not in {"legacy", "portable"}:
        raise ValueError("Unknown package variant")
    if variant == "portable" and (registered_server_id or mcp_url):
        raise ValueError("Portable package does not support server bindings")
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
    if variant == "portable":
        files = portable_files()
    else:
        for name in ("plugin.json", SKILL):
            path = SOURCE / name
            if path.is_symlink() or not path.is_file():
                raise ValueError("Missing regular package source")
        manifest = json.loads((SOURCE / "plugin.json").read_text())
        files = {SKILL: (SOURCE / SKILL).read_bytes()}
    if variant == "legacy" and registered_server_id:
        manifest["extensions"]["com.openai"]["apps"] = "./.app.json"
        files[".app.json"] = json.dumps(
            {"apps": {"careerground": {"id": registered_server_id, "required": True}}}
        ).encode()
    elif variant == "legacy" and mcp_url:
        files["mcp.json"] = json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                "mcpServers": {"careerground": {"type": "streamable-http", "url": mcp_url}},
            }
        ).encode()
    if variant == "legacy":
        files["plugin.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
    if any(parent.is_symlink() for parent in output.absolute().parents):
        raise ValueError("Symlink output directory")
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
    parser.add_argument("--variant", choices=("legacy", "portable"), default="legacy")
    binding = parser.add_mutually_exclusive_group()
    binding.add_argument("--registered-server-id")
    binding.add_argument("--mcp-url")
    args = parser.parse_args()
    members = build_archive(
        args.output,
        registered_server_id=args.registered_server_id,
        mcp_url=args.mcp_url,
        variant=args.variant,
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
