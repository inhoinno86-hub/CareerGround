"""Read-only BrowserOS startup diagnosis; never changes profiles or processes.

Only process states, selected flag presence, profile lock status, and local
endpoint availability are reported. No tab titles, URLs, cookies, credentials,
environment values, or full command lines are printed.
"""

import argparse
import asyncio
import http.client
import ipaddress
import json
import logging
import os
import socket
import struct
from pathlib import Path


def inspect_processes(proc_root=Path("/proc")):
    main, roles = [], {}
    complete = True
    for directory in proc_root.iterdir():
        if not directory.name.isdigit():
            continue
        try:
            if directory.stat().st_uid != os.getuid():
                continue
            if directory.joinpath("comm").read_text().strip() != "browseros":
                continue
            status = directory.joinpath("status").read_text()
            arguments = directory.joinpath("cmdline").read_bytes().split(b"\0")
        except FileNotFoundError:
            # Processes can exit during the read-only snapshot.
            continue
        except OSError:
            complete = False
            continue
        kind = next(
            (a.removeprefix(b"--type=") for a in arguments if a.startswith(b"--type=")), None
        )
        role = {b"gpu-process": "gpu", b"renderer": "renderer"}.get(kind, "other")
        if kind is not None:
            roles[role] = roles.get(role, 0) + 1
            continue
        state = next((s.split()[1] for s in status.splitlines() if s.startswith("State:")), "?")
        explicit_profile = any(a.startswith(b"--user-data-dir=") for a in arguments)
        main.append(
            {
                "pid": int(directory.name),
                "state": state,
                "explicit_profile": explicit_profile,
                "headless_flag": any(
                    a == b"--headless" or a.startswith(b"--headless=") for a in arguments
                ),
                "disable_gpu_flag": b"--disable-gpu" in arguments,
                "ozone_platform_override": any(
                    a.startswith(b"--ozone-platform=") for a in arguments
                ),
            }
        )
    return {"snapshot_complete": complete, "main_processes": main, "child_role_counts": roles}


def inspect_lock(profile, processes):
    lock = profile / "SingletonLock"
    result = {
        "profile_directory_present": profile.is_dir(),
        "lock_symlink_present": lock.is_symlink(),
    }
    if not lock.is_symlink():
        return result
    try:
        host, pid = os.readlink(lock).rsplit("-", 1)
        result["lock_host_matches_this_pc"] = host == socket.gethostname()
        result["lock_pid_is_observed_browser_main"] = any(
            p["pid"] == int(pid) for p in processes["main_processes"]
        )
        result["lock_pid_present"] = Path("/proc", str(int(pid))).exists()
    except (OSError, ValueError):
        result["lock_metadata_readable"] = False
    return result


def inspect_endpoint(port, path, summarize=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        result = {"status": "http_response", "http_status": response.status}
        if summarize is not None and response.status == 200:
            payload = response.read(65537)
            if len(payload) <= 65536:
                try:
                    result.update(summarize(json.loads(payload)))
                except (ValueError, TypeError, AttributeError):
                    result["payload_recognized"] = False
        return result
    except PermissionError:
        return {"status": "permission_denied"}
    except ConnectionRefusedError:
        return {"status": "connection_refused"}
    except TimeoutError:
        return {"status": "timeout"}
    except (OSError, http.client.HTTPException):
        return {"status": "unavailable"}
    finally:
        connection.close()


def inspect_listeners(net_root=Path("/proc/net")):
    listeners = []
    complete = True
    for filename, family in (("tcp", socket.AF_INET), ("tcp6", socket.AF_INET6)):
        try:
            rows = (net_root / filename).read_text().splitlines()[1:]
        except OSError:
            complete = False
            continue
        for row in rows:
            fields = row.split()
            if len(fields) < 4 or fields[3] != "0A":
                continue
            try:
                address, port = fields[1].split(":")
                port = int(port, 16)
                if port not in {9000, 9100, 9201}:
                    continue
                integers = [int(address[i : i + 8], 16) for i in range(0, len(address), 8)]
                packed = struct.pack("=" + "I" * len(integers), *integers)
                ip = ipaddress.ip_address(socket.inet_ntop(family, packed))
            except (ValueError, OSError, struct.error):
                complete = False
                continue
            listeners.append(
                {
                    "port": port,
                    "address": str(ip) if ip.is_loopback or ip.is_unspecified else "non_loopback",
                    "loopback": ip.is_loopback,
                }
            )
    return {"snapshot_complete": complete, "observed": listeners}


async def inspect_mcp():
    # Optional protocol discovery only; no browser tool is executed.
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
    except ImportError:
        return {"status": "dependency_missing", "browser_tools_called": 0}

    async def discover():
        async with (
            streamable_http_client("http://127.0.0.1:9201/mcp") as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            result = await session.list_tools()
            return {
                "status": "connected",
                "listed_tool_count": len(result.tools),
                "more_tools_available": bool(result.next_cursor),
                "browser_tools_called": 0,
            }

    # Report sanitized status, without transport payloads or session headers.
    for name in ("mcp", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
    try:
        return await asyncio.wait_for(discover(), timeout=8)
    except TimeoutError:
        return {"status": "timeout", "browser_tools_called": 0}
    except Exception:  # noqa: BLE001 - never print transport payloads
        return {"status": "connection_failed", "browser_tools_called": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcp-check", action="store_true", help="Initialize and list tools only")
    args = parser.parse_args()
    processes = inspect_processes()
    result = {
        "read_only": True,
        "display_environment": {
            "display_present": bool(os.environ.get("DISPLAY")),
            "wayland_display_present": bool(os.environ.get("WAYLAND_DISPLAY")),
            "session_type": os.environ.get("XDG_SESSION_TYPE")
            if os.environ.get("XDG_SESSION_TYPE") in {"x11", "wayland", "tty"}
            else "unknown",
        },
        "processes": processes,
        "profile": inspect_lock(Path.home() / ".config/browser-os", processes),
        "cdp_version": inspect_endpoint(
            9100,
            "/json/version",
            lambda p: {"devtools_endpoint_advertised": bool(p.get("webSocketDebuggerUrl"))},
        ),
        "cdp_targets": inspect_endpoint(
            9100, "/json/list", lambda p: {"page_count": sum(t.get("type") == "page" for t in p)}
        ),
        "mcp_health": inspect_endpoint(9201, "/system/health"),
        "listeners": inspect_listeners(),
    }
    if args.mcp_check:
        result["mcp_protocol"] = asyncio.run(inspect_mcp())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
