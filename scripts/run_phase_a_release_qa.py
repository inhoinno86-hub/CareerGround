"""Run synthetic release QA in an owner-only persistent, Git-ignored directory.

Uses existing Auth0 configuration and localhost ports 5000/8001. No tunnel,
model API, profile creation, human approval, restore, or cleanup is performed.
Initialize a new named environment once, then restart without --initialize.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

CONFIG_NAMES = {
    "AUTH0_DOMAIN",
    "AUTH0_CLIENT_ID",
    "AUTH0_CLIENT_SECRET",
    "AUTH0_SECRET",
    "APP_BASE_URL",
    "CAREERGROUND_POC_ISSUER",
    "CAREERGROUND_POC_RESOURCE_URL",
}
MARKER = {"schema": 1, "purpose": "synthetic-release-qa", "origin": "http://localhost:5000"}


def private_path(path, *, directory=False):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Symlink paths are not accepted")
    info = path.stat()
    expected = 0o700 if directory else 0o600
    if (
        info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != expected
        or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
    ):
        raise ValueError("Owner-only QA path required")


def write_marker(base, initialized, *, first=False):
    content = json.dumps({**MARKER, "runtime_initialized": initialized}, sort_keys=True).encode()
    target = base / "qa.json"
    temporary = target if first else base / ".qa-next.json"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    if not first:
        os.replace(temporary, target)


def load_environment(project, inherited=None):
    env = dict(os.environ if inherited is None else inherited)
    # Each run is bound to the reviewed files, not incidental shell overrides.
    for name in CONFIG_NAMES:
        env.pop(name, None)
    for filename in (".env", ".env.poc"):
        path = project / filename
        if path.is_symlink() or not path.is_file():
            raise ValueError("Existing regular development configuration required")
        for line in path.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() in CONFIG_NAMES:
                parsed = shlex.split(value, comments=True)
                if len(parsed) != 1:
                    raise ValueError("Invalid development configuration; contents suppressed")
                env[key.strip()] = parsed[0]
    if not all(env.get(name) for name in CONFIG_NAMES):
        raise ValueError("Incomplete development configuration; contents suppressed")
    if env["APP_BASE_URL"] != MARKER["origin"] or env["CAREERGROUND_POC_ISSUER"] != (
        "https://" + env["AUTH0_DOMAIN"] + "/"
    ):
        raise ValueError("Existing loopback origin/issuer binding required")
    env.pop("CAREERGROUND_DATABASE_URL", None)
    return env


def prepare(project, name, *, initialize=False):
    if (
        not project.is_absolute()
        or ".." in project.parts
        or any(p.is_symlink() for p in (project, *project.parents))
    ):
        raise ValueError("Regular absolute project path required")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("Invalid QA name")
    parent = project / ".careerground-release-qa"
    if not parent.exists():
        if not initialize:
            raise ValueError("Initialize the new QA explicitly once")
        if parent.is_symlink():
            raise ValueError("Symlink paths are not accepted")
        parent.mkdir(mode=0o700)
    private_path(parent, directory=True)
    base = parent / name
    if initialize:
        if base.exists() or base.is_symlink():
            raise ValueError("Initialization never replaces an existing QA")
        base.mkdir(mode=0o700)
        write_marker(base, False, first=True)
    private_path(base, directory=True)
    private_path(base / "qa.json")
    marker = json.loads((base / "qa.json").read_text())
    if (
        set(marker) != {*MARKER, "runtime_initialized"}
        or any(marker.get(k) != v for k, v in MARKER.items())
        or type(marker["runtime_initialized"]) is not bool
    ):
        raise ValueError("Unexpected existing QA marker")
    state, passkeys = base / "state", base / "passkeys"
    present = [p.exists() or p.is_symlink() for p in (state, passkeys)]
    if any(present) and not all(present):
        raise ValueError("Incomplete QA; inspect retained files before restarting")
    if marker["runtime_initialized"] and not all(present):
        raise ValueError("Initialized QA files missing; never recreate automatically")
    if all(present):
        for path in (state, passkeys):
            private_path(path, directory=True)
        private_path(state / "authenticated.sqlite")
        if not marker["runtime_initialized"]:
            write_marker(base, True)
    return base


def runtime_command(base, *, enable_connections=False):
    command = [
        sys.executable,
        "-m",
        "careerground.auth0_development_runtime",
        "--allow-development-login",
        "--allow-development-profile-deletion",
        "--state-dir",
        str(base / "state"),
        "--development-deletion-passkey-dir",
        str(base / "passkeys"),
        "--allow-development-passkey-enrollment",
        "--mcp-port",
        "8001",
    ]
    if not (base / "passkeys").exists():
        command.append("--initialize-development-passkeys")
    denials = base / "connection-denials"
    if denials.is_symlink():
        raise ValueError("Symlink denial registry is not accepted")
    if enable_connections or denials.exists() or denials.is_symlink():
        # Populate this private file only from new verified operation metadata.
        path = base / "observed-client.txt"
        private_path(path)
        if path.stat().st_size > 256:
            raise ValueError("Invalid observed client file")
        client = path.read_text().strip()
        if not 1 <= len(client) <= 255 or any(c.isspace() for c in client):
            raise ValueError("Invalid observed client file")
        if denials.exists():
            private_path(denials, directory=True)
        command.extend(
            [
                "--development-connection-denials-dir",
                str(denials),
                "--development-connection-client-id",
                client,
            ]
        )
        if not denials.exists():
            command.append("--initialize-development-connection-denials")
    return command


def run_runtime(project, base, command, env):
    # Refuse occupied ports rather than interrupting another service.
    for port in (5000, 8001):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(("127.0.0.1", port))
    log = base / "runtime.log"
    if log.exists() or log.is_symlink():
        private_path(log)
    fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "ab") as stream:
        process = subprocess.Popen(command, cwd=project, env=env, stdout=stream, stderr=stream)
        handlers = {}
        try:
            for sig in (signal.SIGINT, signal.SIGTERM):
                handlers[sig] = signal.signal(
                    sig, lambda signum, _frame: process.send_signal(signum)
                )
            print("Persistent synthetic QA starting; private output: " + str(log), flush=True)
            marked = json.loads((base / "qa.json").read_text())["runtime_initialized"]
            while process.poll() is None:
                if not marked and (base / "state/authenticated.sqlite").is_file():
                    # Record first store creation even if a later startup step fails.
                    write_marker(base, True)
                    marked = True
                time.sleep(0.2)
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
            process.wait()
            if (
                not json.loads((base / "qa.json").read_text())["runtime_initialized"]
                and (base / "state/authenticated.sqlite").is_file()
            ):
                write_marker(base, True)
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
        return process.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="release-20261007")
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--enable-connection-controls", action="store_true")
    args = parser.parse_args()
    project = Path(__file__).absolute().parents[1]
    stage = "configuration"
    try:
        env = load_environment(project)
        stage = "persistent-paths"
        base = prepare(project, args.name, initialize=args.initialize)
        stage = "runtime-options"
        command = runtime_command(base, enable_connections=args.enable_connection_controls)
        if args.prepare_only:
            print(json.dumps({"prepared": True, "runtime_started": False, "qa_dir": str(base)}))
            return
        stage = "runtime-launch"
        raise SystemExit(run_runtime(project, base, command, env))
    except Exception:  # noqa: BLE001 - configuration and upstream details remain private
        parser.exit(1, f"QA startup refused at {stage}; existing data retained.\n")


if __name__ == "__main__":
    main()
