"""Loopback-only STEP 02 runtime. Select synthetic credentials or reviewed OIDC."""

import argparse
import json
import secrets
from pathlib import Path

import uvicorn

from .api import create_app
from .provider import ProviderVerifier
from .session import Rejected

parser = argparse.ArgumentParser(description=__doc__)
mode = parser.add_mutually_exclusive_group(required=True)
mode.add_argument("--synthetic-dev", action="store_true")
mode.add_argument("--oidc-config", type=Path)
parser.add_argument(
    "--codex-budget-ledger",
    type=Path,
    help="Enable approved existing-login AI; reuse the same owner-only call ledger",
)
parser.add_argument(
    "--codex-call-limit",
    type=int,
    choices=range(1, 16),
    default=12,
    help="Explicit approved cumulative limit (default 12); must match the existing ledger",
)
parser.add_argument("--codex-model", default="gpt-6.1-sol")
args = parser.parse_args()
if args.codex_call_limit != 12 and not args.codex_budget_ledger:
    parser.error("--codex-call-limit requires --codex-budget-ledger")
store = None
if args.codex_budget_ledger:
    from .interview import CodexInterviewProvider, InterviewSessions

    store = InterviewSessions(
        CodexInterviewProvider(
            args.codex_budget_ledger, model=args.codex_model, call_limit=args.codex_call_limit
        ),
        auth_mode="synthetic_dev" if args.synthetic_dev else "oidc",
    )
if args.synthetic_dev:
    token = secrets.token_urlsafe(32)
    print("합성 개발 전용 연결 코드 (RAM에만 보관):", token, flush=True)
    app = create_app(credentials={token: "synthetic-local-owner"}, sessions=store)
else:
    try:
        verifier = ProviderVerifier(json.loads(args.oidc_config.read_text()))
    except (OSError, ValueError, KeyError, TypeError, Rejected):
        parser.exit(1, "OIDC_CONFIG_OR_PUBLIC_METADATA_FAILED\n")
    app = create_app(oidc_verifier=verifier, sessions=store)
    print("실제 OIDC 토큰 검증 · RAM 전용", flush=True)
print("기존 Codex 로그인 AI 활성" if store else "AI 비활성 · STEP 02", flush=True)
uvicorn.run(
    app,
    host="127.0.0.1",
    port=8765,
    access_log=False,
    log_level="warning",
)
