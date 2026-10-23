"""Bounded, memory-only STEP 02 sessions. No model, URL or shell execution."""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import importlib.util
import json
import math
import re
import secrets
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[4]
REFERENCES = ROOT / "plugins/careerground-portable/references"
# The standalone reference has a sibling import. Restore sys.path after loading it.
sys.path.insert(0, str(REFERENCES))
try:
    spec = importlib.util.spec_from_file_location("cg_mock_exchange", REFERENCES / "exchange.py")
    exchange = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exchange)
finally:
    sys.path.pop(0)

MAX_JSON = 2 * 1024 * 1024
MAX_ATTACHMENT = 10 * 1024 * 1024
MAX_ATTACHMENTS_TOTAL = 20 * 1024 * 1024
MAX_ENVELOPE = 32 * 1024 * 1024
MAX_SESSION = 4 * 1024 * 1024
SCHEMA = ROOT / "apps/mock-interview/contracts/session-0.1.schema.json"


class Rejected(ValueError):
    def __init__(self, *codes, status=400):
        self.codes = sorted(set(codes))
        self.status = status
        super().__init__(", ".join(self.codes))


def unique_pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise Rejected("DUPLICATE_JSON_KEY")
        result[k] = v
    return result


def parse(raw: bytes, limit=MAX_JSON):
    if len(raw) > limit:
        raise Rejected("SIZE_LIMIT", status=413)
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(Rejected("INVALID_JSON")),
        )
        # JSON escapes can carry lone surrogates despite valid UTF-8 input bytes.
        # Reject them before a review can mutate state or an HTTP encoder can fail.
        pending = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, str):
                item.encode("utf-8", errors="strict")
            elif isinstance(item, float) and not math.isfinite(item):
                raise Rejected("INVALID_JSON")
            elif isinstance(item, dict):
                pending.extend(item.keys())
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
        return value
    except Rejected:
        raise
    except (ValueError, RecursionError) as error:
        raise Rejected("INVALID_JSON") from error


def exact(data, fields):
    if not isinstance(data, dict) or set(data) != set(fields):
        raise Rejected("REQUEST_SCHEMA")


def decode(value, limit):
    if not isinstance(value, str) or len(value) > 4 * ((limit + 2) // 3):
        raise Rejected("SIZE_LIMIT", status=413)
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise Rejected("INVALID_BASE64") from error
    if len(raw) > limit:
        raise Rejected("SIZE_LIMIT", status=413)
    return raw


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_selected(raw, attachments):
    """Only validated flat basenames enter a short-lived directory; always cleaned."""
    handoff = parse(raw)
    errors = exchange.validate_handoff(handoff)
    errors = [e for e in errors if e != "ATTACHMENT_NOT_CHECKED"]
    if errors:
        raise Rejected(*errors)
    if not isinstance(attachments, dict) or len(attachments) > 500:
        raise Rejected("REQUEST_SCHEMA")
    expected = {a["path"]: a for a in handoff["workspace"]["attachments"]}
    if len(expected) != len(handoff["workspace"]["attachments"]):
        raise Rejected("DUPLICATE_ATTACHMENT_PATH")
    if set(expected) != set(attachments):
        raise Rejected("ATTACHMENT_SELECTION_MISMATCH")
    total = 0
    for name, data in attachments.items():
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name):
            raise Rejected("ATTACHMENT_PATH")
        if not isinstance(data, bytes) or len(data) > MAX_ATTACHMENT:
            raise Rejected("SIZE_LIMIT", status=413)
        total += len(data)
    if total > MAX_ATTACHMENTS_TOTAL:
        raise Rejected("ATTACHMENT_TOTAL_LIMIT", status=413)
    # Existing validator checks byte hashes and symlinks. No caller-supplied directories.
    with tempfile.TemporaryDirectory(prefix="cg-interview-") as directory:
        folder = Path(directory)
        for name, data in attachments.items():
            (folder / name).write_bytes(data)
        errors = exchange.validate_handoff(handoff, attachment_root=folder)
    if errors:
        raise Rejected(*errors)
    return handoff


def utc_now():
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class Sessions:
    def __init__(self, *, clock=time.monotonic, ttl=1800, capacity=8, auth_mode="synthetic_dev"):
        if auth_mode not in {"synthetic_dev", "oidc"}:
            raise ValueError("Explicit supported session authentication mode required")
        self.auth_mode = auth_mode
        self._items = {}
        self._clock, self.ttl, self.capacity = clock, ttl, capacity

    def _purge(self):
        for sid in list(self._items):
            if self._items[sid]["expires"] <= self._clock():
                del self._items[sid]

    def _get(self, sid, owner):
        self._purge()
        item = self._items.get(sid)
        if item is None or item["owner"] != owner:
            raise Rejected("SESSION_UNAVAILABLE", status=404)
        return item

    def create(self, owner, raw, attachments):
        handoff = validate_selected(raw, attachments)
        self._purge()
        if len(self._items) >= self.capacity:
            raise Rejected("SESSION_CAPACITY", status=429)
        sid = "session-" + secrets.token_hex(16)
        self._items[sid] = {
            "owner": owner,
            "raw": bytes(raw),
            "handoff": copy.deepcopy(handoff),
            "digest": exchange.digest(handoff),
            "attachments": copy.deepcopy(attachments),
            "state": "REVIEW_REQUIRED",
            "review": None,
            "mode": "coaching",
            "expires": self._clock() + self.ttl,
            "created_at": utc_now(),
        }
        return self.view(sid, owner)

    def view(self, sid, owner):
        item = self._get(sid, owner)
        return {
            "session_id": sid,
            "created_at": item["created_at"],
            "state": item["state"],
            "handoff": copy.deepcopy(item["handoff"]),
            "canonical_digest": item["digest"],
            "raw_sha256": sha(item["raw"]),
            "review": copy.deepcopy(item["review"]),
            "mode": item["mode"],
            "auth_mode": self.auth_mode,
            "ai_status": "NOT_IMPLEMENTED",
            "expires_in_seconds": max(0, int(item["expires"] - self._clock())),
        }

    def review(self, sid, owner, digest, record, mode):
        item = self._get(sid, owner)
        if item["state"] != "REVIEW_REQUIRED":
            raise Rejected("STATE_CONFLICT", status=409)
        if digest != item["digest"]:
            raise Rejected("HANDOFF_CONFLICT", status=409)
        if not isinstance(record, str) or not record.strip() or len(record) > 20000:
            raise Rejected("REVIEW_REQUIRED")
        if not isinstance(mode, str) or mode not in {"coaching", "simulation"}:
            raise Rejected("MODE")
        item.update(
            state="READY",
            mode=mode,
            review={
                "record": record,
                "canonical_digest": digest,
                "confirmed_at": utc_now(),
            },
        )
        return self.view(sid, owner)

    def transition(self, sid, owner, action):
        item = self._get(sid, owner)
        transitions = {
            ("READY", "start"): "IN_PROGRESS",
            ("IN_PROGRESS", "pause"): "PAUSED",
            ("PAUSED", "continue"): "IN_PROGRESS",
            ("READY", "abort"): "ABORTED",
            ("IN_PROGRESS", "abort"): "ABORTED",
            ("PAUSED", "abort"): "ABORTED",
        }
        state = transitions.get((item["state"], action))
        if state is None:
            raise Rejected("STATE_CONFLICT", status=409)
        item["state"] = state
        return self.view(sid, owner)

    def export(self, sid, owner):
        item = self._get(sid, owner)
        data = {
            "kind": "career-interview-session",
            "schema_version": "0.1",
            "session_id": sid,
            "owner_binding": owner,
            "created_at": item["created_at"],
            "exported_at": utc_now(),
            "handoff_base64": base64.b64encode(item["raw"]).decode(),
            "handoff_ref": {"id": item["handoff"]["handoff_id"], "sha256": item["digest"]},
            "raw_sha256": sha(item["raw"]),
            "state": item["state"],
            "mode": item["mode"],
            "review": copy.deepcopy(item["review"]),
            "questions": [],
            "answers": [],
            "feedback": [],
            "candidates": [],
            "auth_mode": self.auth_mode,
        }
        raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        validate_session(raw)
        return raw

    def restore(self, owner, raw, attachments):
        data = validate_session(raw)
        if data["owner_binding"] != owner:
            raise Rejected("OWNER_CONFLICT", status=403)
        if data["auth_mode"] != self.auth_mode:
            raise Rejected("AUTH_MODE_CONFLICT", status=403)
        # STEP 02 deliberately cannot restore later step's interview records.
        if any(data[k] for k in ("questions", "answers", "feedback", "candidates")):
            raise Rejected("INTERVIEW_RECORDS_NOT_IMPLEMENTED")
        original = decode(data["handoff_base64"], MAX_JSON)
        handoff = validate_selected(original, attachments)
        if sha(original) != data["raw_sha256"] or data["handoff_ref"] != {
            "id": handoff["handoff_id"],
            "sha256": exchange.digest(handoff),
        }:
            raise Rejected("HANDOFF_CONFLICT")
        view = self.create(owner, original, attachments)
        item = self._get(view["session_id"], owner)
        item["mode"] = data["mode"]
        # Reimport never trusts an unsigned review flag or resurrects terminal sessions.
        if data["state"] in {"COMPLETED", "ABORTED"}:
            item["state"] = data["state"]
        return self.view(view["session_id"], owner)

    def delete(self, sid, owner):
        self._get(sid, owner)
        del self._items[sid]

    def clear_owner(self, owner):
        for sid in list(self._items):
            if self._items[sid]["owner"] == owner:
                del self._items[sid]


def validate_session(raw):
    data = parse(raw, MAX_SESSION)
    schema = json.loads(SCHEMA.read_text())
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    if next(validator.iter_errors(data), None):
        raise Rejected("SESSION_SCHEMA")
    return data
