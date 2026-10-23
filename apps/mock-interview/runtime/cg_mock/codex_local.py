"""Minimal filesystem for the approved existing-login Codex interview provider.

No account token is parsed, copied, logged, or included in an interview request.
HOME/CODEX_HOME retain their original values inside an empty mount namespace.
Only the installed static CLI and its existing read-only auth file are mounted.
"""

from __future__ import annotations

import copy
import fcntl
import json
import os
import re
import selectors
import shutil
import signal
import stat
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from jsonschema import Draft202012Validator

MAX_APPROVED_CALLS = 18

HOST_DISABLED = (
    "Code Mode is unavailable because code-mode host is disabled. "
    "Code mode will fail closed; enable `features.code_mode_host` "
    "and install `codex-code-mode-host`."
)


class CodexRejected(RuntimeError):
    """Only stable codes cross the runtime boundary; never raw CLI diagnostics."""


class CallBudget:
    """Owner-only count ledger, also locks out concurrent calls across processes.

    This stores counts only, never interview data, credentials or CLI output.
    Reuse the same ledger after restarting the development runtime.
    """

    def __init__(self, ledger: Path, *, limit=12):
        self.ledger, self.limit = Path(ledger), limit
        parent = self.ledger.parent.stat()
        if (
            type(limit) is not int
            or not 1 <= limit <= MAX_APPROVED_CALLS
            or parent.st_uid != os.getuid()
            or parent.st_mode & 0o077
            or not stat.S_ISDIR(parent.st_mode)
        ):
            raise CodexRejected("CODEX_BUDGET_LOCATION")

    @contextmanager
    def reserve(self):
        fd = os.open(self.ledger, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, "r+") as file:
            metadata = os.fstat(file.fileno())
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or metadata.st_mode & 0o077
            ):
                raise CodexRejected("CODEX_BUDGET_LOCATION")
            try:
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise CodexRejected("CODEX_BUSY") from error
            try:
                raw = file.read(4097)
                state = json.loads(raw) if raw else {"attempts": 0, "limit": self.limit}
                used = state["attempts"]
                if (
                    type(used) is not int
                    or used < 0
                    or type(state["limit"]) is not int
                    or state["limit"] != self.limit
                    or len(raw) > 4096
                ):
                    raise CodexRejected("CODEX_BUDGET_INVALID")
                if used >= self.limit:
                    raise CodexRejected("CODEX_BUDGET_EXHAUSTED")
                file.seek(0)
                json.dump(
                    {
                        "attempts": used + 1,
                        "limit": self.limit,
                        "auth_mode": "chatgpt",
                        "paid_api_calls": 0,
                    },
                    file,
                )
                file.truncate()
                file.flush()
                os.fsync(file.fileno())
                yield used + 1
            except (ValueError, KeyError, TypeError) as error:
                raise CodexRejected("CODEX_BUDGET_INVALID") from error
            finally:
                fcntl.flock(file, fcntl.LOCK_UN)


class CliResponse:
    """Reject every tool and unknown event; tolerate one exact startup diagnostic."""

    def __init__(self):
        self.started = self.completed = False
        self.messages = []
        self.diagnostics = 0
        self.usage = {}

    def event(self, raw):
        try:
            event = json.loads(raw)
            kind = event["type"]
            if kind in {"turn.failed", "error"}:
                # Classify diagnostics in RAM without exposing provider text,
                # quoted request material or credentials in logs/UI.
                diagnostic = str(event.get("error", event.get("message", ""))).lower()
                for markers, code in (
                    (("schema",), "CODEX_PROVIDER_SCHEMA_ERROR"),
                    (("rate limit", "usage limit", "quota"), "CODEX_USAGE_LIMIT"),
                    (("authentication", "unauthorized", "login"), "CODEX_AUTH_ERROR"),
                    (("network", "connection", "timeout"), "CODEX_NETWORK_ERROR"),
                ):
                    if any(marker in diagnostic for marker in markers):
                        raise CodexRejected(code)
                raise CodexRejected("CODEX_PROVIDER_ERROR")
            if kind == "thread.started" and not self.started:
                return
            if kind == "turn.started" and not self.started:
                self.started = True
                return
            if kind == "turn.completed" and self.started and not self.completed:
                self.completed = True
                self.usage = {
                    key: value
                    for key, value in event.get("usage", {}).items()
                    if key.endswith("tokens") and type(value) is int and value >= 0
                }
                return
            if kind in {"item.started", "item.updated", "item.completed"} and not self.completed:
                item = event["item"]
                if (
                    kind == "item.completed"
                    and item["type"] == "error"
                    and not self.started
                    and not self.diagnostics
                    and item.get("message") == HOST_DISABLED
                ):
                    self.diagnostics += 1
                    return
                if self.started and item["type"] in {"agent_message", "reasoning"}:
                    if kind == "item.completed" and item["type"] == "agent_message":
                        self.messages.append(item["text"])
                    return
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise CodexRejected("CODEX_EVENT_INVALID") from error
        raise CodexRejected("CODEX_TOOL_OR_ERROR_EVENT")

    def finish(self, schema):
        if not self.completed or len(self.messages) != 1:
            raise CodexRejected("CODEX_INCOMPLETE_RESPONSE")
        try:
            payload = json.loads(self.messages[0])
            Draft202012Validator(schema).validate(payload)
        except Exception as error:
            raise CodexRejected("CODEX_RESPONSE_SCHEMA") from error
        return payload


DISABLED_FEATURES = (
    "apps",
    "browser_use",
    "browser_use_external",
    "computer_use",
    "code_mode",
    "code_mode_host",
    "code_mode_only",
    "code_mode_prewarm",
    "goals",
    "hooks",
    "image_generation",
    "memories",
    "multi_agent",
    "remote_plugin",
    "shell_snapshot",
    "shell_tool",
    "skill_search",
    "skill_mcp_dependency_install",
    "tool_suggest",
    "unified_exec",
    "view_image",
    "workspace_dependencies",
    "daemon_auto_start",
)


class IsolatedCodex:
    def __init__(self):
        executable = shutil.which("codex")
        bubblewrap = shutil.which("bwrap")
        if not executable or not bubblewrap:
            raise RuntimeError("CODEX_ISOLATION_TOOLS_UNAVAILABLE")
        package = Path(executable).resolve().parents[1]
        self.native = (
            package / "node_modules/@openai/codex-linux-x64/vendor/"
            "x86_64-unknown-linux-musl/bin/codex"
        )
        self.bubblewrap = bubblewrap
        self.home = Path(os.environ["HOME"])
        self.codex_home = Path(os.environ.get("CODEX_HOME", str(self.home / ".codex")))
        self.auth = self.codex_home / "auth.json"
        if (
            not self.native.is_file()
            or self.auth.is_symlink()
            or not stat.S_ISREG(self.auth.stat().st_mode)
            or self.auth.stat().st_uid != os.getuid()
        ):
            raise RuntimeError("CODEX_ISOLATION_AUTH_OR_BINARY_UNAVAILABLE")
        # Preserve, rather than replace, the existing auth home. Drop API keys,
        # provider/proxy overrides and all unrelated inherited environment values.
        self.environment = {
            name: os.environ[name] for name in ("HOME", "CODEX_HOME", "PATH") if name in os.environ
        }

    def sandbox(self, *, extra_mounts=(), network=True):
        command = [
            self.bubblewrap,
            "--die-with-parent",
            "--new-session",
            "--unshare-user",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--cap-drop",
            "ALL",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--tmpfs",
            "/run",
            "--dir",
            "/bin",
            "--dir",
            "/cg-interview",
            "--dir",
            str(self.home),
            "--dir",
            str(self.codex_home),
            "--ro-bind",
            str(self.native),
            "/bin/codex",
            "--ro-bind",
            str(self.auth),
            str(self.auth),
            "--chdir",
            "/cg-interview",
        ]
        if not network:
            command.append("--unshare-net")
        for path in ("/etc/ssl/certs", "/etc/resolv.conf", "/etc/hosts", "/etc/nsswitch.conf"):
            if Path(path).exists():
                command.extend(["--ro-bind", path, path])
        for source, destination in extra_mounts:
            command.extend(["--ro-bind", str(source), str(destination)])
        return command

    @staticmethod
    def wire_schema(schema):
        # Provider Structured Outputs accepts a subset of JSON Schema. Keep
        # uniqueness enforcement in the full local validator after generation.
        result = copy.deepcopy(schema)
        pending = [result]
        while pending:
            current = pending.pop()
            if isinstance(current, dict):
                current.pop("uniqueItems", None)
                pending.extend(current.values())
            elif isinstance(current, list):
                pending.extend(current)
        return result

    @staticmethod
    def exec_options():
        options = [
            "exec",
            "--ignore-user-config",
            "--ignore-rules",
            "--strict-config",
            "--ephemeral",
            "--json",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "-c",
            'forced_login_method="chatgpt"',
            "-c",
            'web_search="disabled"',
            "-c",
            "project_doc_max_bytes=0",
            "-c",
            'history.persistence="none"',
            "-c",
            "feedback.enabled=false",
        ]
        for name in DISABLED_FEATURES:
            options.extend(["--disable", name])
        return options

    def generate(self, prompt: str, schema: dict, *, model: str, budget: CallBudget, timeout=90):
        if not re.fullmatch(r"gpt-[a-zA-Z0-9.-]{1,64}", model):
            raise CodexRejected("CODEX_MODEL_INVALID")
        encoded = prompt.encode("utf-8")
        encoded_schema = json.dumps(self.wire_schema(schema)).encode()
        if len(encoded) > 128 * 1024 or len(encoded_schema) > 64 * 1024:
            raise CodexRejected("CODEX_CONTEXT_LIMIT")
        Draft202012Validator.check_schema(schema)
        with (
            budget.reserve() as attempt,
            tempfile.TemporaryDirectory(prefix="cg-codex-schema-") as directory,
        ):
            self.last_attempt = attempt
            # Only a nonpersonal output schema is written here. The prompt and
            # response stay in pipes/RAM; child caches go to disposable tmpfs.
            path = Path(directory) / "schema.json"
            path.write_bytes(encoded_schema)
            command = self.sandbox(extra_mounts=[(path, "/cg-interview/schema.json")]) + [
                "/bin/codex",
                *self.exec_options(),
                "--model",
                model,
                "--output-schema",
                "/cg-interview/schema.json",
                "-",
            ]
            response = self._execute(command, encoded, timeout=timeout)
            return {
                "payload": response.finish(schema),
                "provider": "CodexLocal",
                "requested_model": model,
                "auth_mode": "chatgpt",
                "actual": True,
                "attempt": attempt,
                "startup_diagnostics": response.diagnostics,
                "tool_events": 0,
                "usage": response.usage,
            }

    def _execute(self, command, prompt, *, timeout):
        response = CliResponse()
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.environment,
            start_new_session=True,
        )
        pending, offset, total = bytearray(), 0, 0
        deadline = time.monotonic() + timeout
        try:
            with selectors.DefaultSelector() as selector:
                for stream in (process.stdin, process.stdout, process.stderr):
                    os.set_blocking(stream.fileno(), False)
                    selector.register(
                        stream,
                        selectors.EVENT_WRITE if stream is process.stdin else selectors.EVENT_READ,
                    )
                while selector.get_map():
                    if time.monotonic() >= deadline:
                        raise CodexRejected("CODEX_TIMEOUT")
                    for key, _ in selector.select(
                        timeout=min(0.2, max(0, deadline - time.monotonic()))
                    ):
                        stream = key.fileobj
                        if stream is process.stdin:
                            if offset < len(prompt):
                                offset += os.write(stream.fileno(), prompt[offset : offset + 16384])
                            if offset == len(prompt):
                                selector.unregister(stream)
                                stream.close()
                            continue
                        chunk = os.read(stream.fileno(), 16384)
                        if not chunk:
                            selector.unregister(stream)
                            continue
                        total += len(chunk)
                        if total > 256 * 1024:
                            raise CodexRejected("CODEX_OUTPUT_LIMIT")
                        if stream is process.stdout:
                            pending.extend(chunk)
                            while b"\n" in pending:
                                line, _, rest = pending.partition(b"\n")
                                pending = bytearray(rest)
                                response.event(line)
                        # stderr is bounded and discarded, never logged.
                if pending:
                    response.event(pending)
                if process.wait(timeout=max(0.1, deadline - time.monotonic())) != 0:
                    raise CodexRejected("CODEX_PROCESS_FAILED")
            return response
        except (OSError, subprocess.SubprocessError) as error:
            raise CodexRejected("CODEX_PROCESS_FAILED") from error
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()
