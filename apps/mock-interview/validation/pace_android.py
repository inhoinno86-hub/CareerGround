"""Validate the integrated debug app on the dedicated synthetic AVD, never a phone.

Run with the existing project venv after building app and androidTest APKs.
Uses actual loopback HTTP and a deterministic mock provider. No Codex/OIDC calls.
"""

import argparse
import hashlib
import json
import os
import runpy
import secrets
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/mock-interview/runtime"))
import uvicorn
from cg_mock.api import create_app
from cg_mock.interview import InterviewSessions

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument(
    "--configurations",
    nargs="+",
    choices=["phone-light", "wide-dark", "large-font", "keyboard"],
    default=["phone-light", "wide-dark", "large-font"],
)
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
tools = Path.home() / ".local/share/careerground-android"
sdk = tools / "sdk"
adb = sdk / "platform-tools/adb"
serial = "emulator-5580"
app_id = "dev.careerground.interview.dev"
android = ROOT / "apps/mock-interview/android"
token = secrets.token_urlsafe(32)
result = {"baseline": "25bf5b012fdcce34e916ce544f27031338369c26", "runs": []}
emulator = None
server = None
thread = None
reverse_added = False


def record(state):
    result["state"] = state
    (output / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")


def run(command, timeout=120, binary=False):
    process = subprocess.run(command, check=False, capture_output=True, timeout=timeout)
    if process.returncode:
        message = (
            (process.stdout + process.stderr)
            .decode(errors="replace")
            .replace(token, "<synthetic-credential>")
        )
        raise RuntimeError(message[-12000:])
    return process.stdout if binary else process.stdout.decode(errors="replace")


def device(*command, **kwargs):
    return run([str(adb), "-s", serial, *command], **kwargs)


def instrument(label, expected, runtime_only=False):
    record(label)
    command = [
        "shell",
        "am",
        "instrument",
        "-w",
        "-e",
        "pace_synthetic_join",
        token,
        "-e",
        "pace_capture",
        "true",
    ]
    if runtime_only:
        command += ["-e", "class", "dev.careerground.interview.PaceRuntimeUiTest"]
    if label == "keyboard":
        command += ["-e", "pace_keyboard", "true"]
    command += [app_id + ".test/androidx.test.runner.AndroidJUnitRunner"]
    log = device(*command, timeout=600).replace(token, "<synthetic-credential>")
    (output / (label + "-instrumentation.log")).write_text(log)
    if f"OK ({expected} tests)" not in log:
        raise RuntimeError(f"{label} instrumentation did not pass; see sanitized log")
    result["runs"].append({"configuration": label, "passed": expected})
    names = device("shell", "run-as", app_id, "ls", "cache/pace-validation").splitlines()
    for name in names:
        if name.endswith(".png") and "/" not in name:
            data = device(
                "exec-out", "run-as", app_id, "cat", "cache/pace-validation/" + name, binary=True
            )
            (output / (label + "-" + name)).write_bytes(data)
    print(f"{label}: {expected} instrumentation tests PASS", flush=True)
    record(label + "-passed")


try:
    record("starting")
    provider_type = runpy.run_path(str(ROOT / "tests/test_mock_interview_engine.py"))[
        "MockProvider"
    ]
    app = create_app(
        credentials={token: "pace-synthetic-owner"}, sessions=InterviewSessions(provider_type())
    )
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, access_log=False, log_level="warning")
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("Synthetic loopback server did not start")

    existing = subprocess.run(
        [str(adb), "-s", serial, "get-state"], check=False, capture_output=True, timeout=10
    )
    if existing.returncode:
        env = os.environ.copy()
        env["ANDROID_SDK_ROOT"] = str(sdk)
        env["ANDROID_AVD_HOME"] = str(tools / "avd-pace-20261012")
        with (output / "emulator.log").open("ab") as log:
            emulator = subprocess.Popen(
                [
                    str(sdk / "emulator/emulator"),
                    "-avd",
                    "careerground-pace-api36",
                    "-port",
                    "5580",
                    "-memory",
                    "1536",
                    "-cores",
                    "2",
                    "-no-window",
                    "-no-audio",
                    "-no-boot-anim",
                    "-no-snapshot",
                    "-gpu",
                    "swiftshader",
                    "-feature",
                    "-Vulkan",
                    "-no-metrics",
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
            )
        result["owned_emulator_pid"] = emulator.pid
    record("booting")
    for _ in range(120):
        boot = subprocess.run(
            [str(adb), "-s", serial, "shell", "getprop", "sys.boot_completed"],
            check=False,
            capture_output=True,
            timeout=5,
        )
        if boot.stdout.strip() == b"1":
            break
        if emulator and emulator.poll() is not None:
            raise RuntimeError("Dedicated emulator exited during boot")
        time.sleep(2)
    else:
        raise RuntimeError("Dedicated AVD boot timeout")
    if "careerground-pace-api36" not in device("emu", "avd", "name"):
        raise RuntimeError("Refusing to use another AVD or a physical device")
    print("Dedicated synthetic AVD ready", flush=True)
    record("installing")
    device("reverse", "tcp:8765", f"tcp:{port}")
    reverse_added = True
    for path in [
        "app/build/outputs/apk/debug/app-debug.apk",
        "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk",
    ]:
        device("install", "-r", str(android / path))
    device("shell", "wm", "density", "420")
    for label in args.configurations:
        device("shell", "wm", "size", "1768x2208" if label == "wide-dark" else "1080x2340")
        device("shell", "cmd", "uimode", "night", "yes" if label == "wide-dark" else "no")
        device(
            "shell",
            "settings",
            "put",
            "system",
            "font_scale",
            "1.5" if label == "large-font" else "1.0",
        )
        device(
            "shell",
            "settings",
            "put",
            "secure",
            "show_ime_with_hard_keyboard",
            "1" if label == "keyboard" else "0",
        )
        instrument(label, 15 if label == "phone-light" else 2, runtime_only=label != "phone-light")
    result["status"] = "PASS"
    result["passed"] = sum(r["passed"] for r in result["runs"])
    result["actual_provider_calls"] = 0
    result["keyboard_observed"] = "keyboard" in args.configurations
    result["limits"] = [
        "Synthetic runtime credentials/provider and files only",
        "File URI read/write; system SAF picker not automated",
        "No personal OIDC, microphone speech, real AI or physical foldable regression",
        "Screen captures temporarily clear FLAG_SECURE only in the synthetic instrumentation test",
    ]
    apk = android / "app/build/outputs/apk/debug/app-debug.apk"
    result["apk_sha256"] = hashlib.sha256(apk.read_bytes()).hexdigest()
except Exception as error:  # noqa: BLE001 -- redact credentials from all driver failures.
    result["status"] = "FAILED"
    result["error"] = str(error).replace(token, "<synthetic-credential>")
    raise RuntimeError(result["error"]) from None
except KeyboardInterrupt:
    result["status"] = "INTERRUPTED"
    raise
finally:
    if reverse_added:
        for command in [
            ("shell", "am", "force-stop", app_id),
            ("reverse", "--remove", "tcp:8765"),
            ("shell", "wm", "size", "reset"),
            ("shell", "wm", "density", "reset"),
            ("shell", "settings", "put", "system", "font_scale", "1.0"),
            ("shell", "settings", "put", "secure", "show_ime_with_hard_keyboard", "0"),
            ("shell", "cmd", "uimode", "night", "no"),
        ]:
            subprocess.run(
                [str(adb), "-s", serial, *command], check=False, capture_output=True, timeout=15
            )
    if emulator:
        subprocess.run(
            [str(adb), "-s", serial, "emu", "kill"], check=False, capture_output=True, timeout=15
        )
        try:
            emulator.wait(timeout=20)
        except subprocess.TimeoutExpired:
            emulator.terminate()
        result["owned_emulator_stopped"] = True
    if server:
        server.should_exit = True
    if thread:
        thread.join(timeout=10)
    record({"PASS": "complete", "INTERRUPTED": "interrupted"}.get(result.get("status"), "failed"))
