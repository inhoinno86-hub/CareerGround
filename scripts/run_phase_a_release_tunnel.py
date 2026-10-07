"""Restart the existing reviewed tunnel only; no new resources or model calls.

Run from the project root with python -m scripts.run_phase_a_release_tunnel.
Configuration, credential files, and existing tunnel ID are never changed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

from scripts.run_phase_a_release_qa import load_environment, prepare, private_path


def scalar(config, name):
    rows = re.findall(r"^\s*" + re.escape(name) + r":\s*([^\n]+)$", config, re.MULTILINE)
    if len(rows) != 1:
        raise ValueError("Expected one existing tunnel configuration field")
    value = shlex.split(rows[0], comments=True)
    if len(value) != 1:
        raise ValueError("Unexpected tunnel configuration")
    return value[0]


def tunnel_settings(project, user_root):
    settings = load_environment(project)
    config_path = user_root / ".config/tunnel-client/careerground-dev-poc.yaml"
    key_path = user_root / ".config/tunnel-client/careerground-dev-poc.env"
    private_path(config_path)
    private_path(key_path)
    config = config_path.read_text()
    resource = urlsplit(settings["CAREERGROUND_POC_RESOURCE_URL"])
    control = urlsplit(scalar(config, "base_url"))
    tunnel_id = scalar(config, "tunnel_id")
    if (
        not re.fullmatch(r"tunnel_[0-9a-f]{32}", tunnel_id)
        or resource.scheme != "https"
        or resource.username
        or resource.password
        or resource.query
        or resource.fragment
        or control.scheme != "https"
        or not resource.hostname
        or not control.hostname
        or control.username
        or control.password
        or control.path not in {"", "/"}
        or control.query
        or control.fragment
        or resource.path != "/v1/mcp/" + tunnel_id
        or scalar(config, "api_key") != "env:CONTROL_PLANE_API_KEY"
    ):
        raise ValueError("Existing reviewed tunnel/resource binding required")
    env = os.environ.copy()
    env.pop("CONTROL_PLANE_API_KEY", None)
    for line in key_path.read_text().splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "CONTROL_PLANE_API_KEY":
            values = shlex.split(value, comments=True)
            if len(values) != 1 or not values[0]:
                raise ValueError("Invalid existing tunnel credential")
            env[name.strip()] = values[0]
    if not env.get("CONTROL_PLANE_API_KEY"):
        raise ValueError("Existing tunnel credential required")
    command = [
        str(user_root / ".local/bin/tunnel-client"),
        "run",
        "--config",
        str(config_path),
        "--mcp.server-url",
        "url=http://127.0.0.1:8001/mcp",
        "--health.listen-addr",
        "127.0.0.1:18081",
        "--allow-remote-ui=false",
        "--open-web-ui=false",
        "--log.http-raw-unsafe=false",
        "--log.level",
        "warn",
        "--log.file",
        "",
    ]
    return command, env


def owned_runtime(base, project):
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid() or (proc / "cwd").resolve() != project:
                continue
            args = [v.decode() for v in (proc / "cmdline").read_bytes().split(b"\0") if v]
            if (
                not args
                or not Path(args[0]).name.startswith("python")
                or "careerground.auth0_development_runtime" not in args
                or args.count("--state-dir") != 1
            ):
                continue
            if args[args.index("--state-dir") + 1] == str(base / "state"):
                return proc
        except (OSError, UnicodeError, IndexError):
            continue
    raise ValueError("Start the owned persistent QA runtime first")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="release-20261007")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    project = Path(__file__).absolute().parents[1]
    process, handlers = None, {}
    try:
        base = prepare(project, args.name)
        command, env = tunnel_settings(project, Path.home())
        if args.prepare_only:
            print(json.dumps({"existing_tunnel_binding_valid": True, "tunnel_started": False}))
            return
        runtime = owned_runtime(base, project)
        with urlopen("http://localhost:5000/health/live", timeout=3) as response:
            if response.status != 200:
                raise ValueError("Owned QA health required")
        log = base / "tunnel.log"
        if log.exists() or log.is_symlink():
            private_path(log)
        fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "ab") as stream:
            process = subprocess.Popen(command, cwd=project, env=env, stdout=stream, stderr=stream)
            for sig in (signal.SIGINT, signal.SIGTERM):
                handlers[sig] = signal.signal(
                    sig, lambda signum, _frame: process.send_signal(signum)
                )
            print("Existing release tunnel starting; raw HTTP logging disabled.", flush=True)
            while process.poll() is None and runtime.exists():
                time.sleep(0.5)
    except Exception:  # noqa: BLE001 - existing credentials and upstream payloads are private
        parser.exit(1, "Existing tunnel startup refused; configuration unchanged.\n")
    finally:
        if process is not None:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
            process.wait()
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    if process is not None:
        raise SystemExit(process.returncode)


if __name__ == "__main__":
    main()
