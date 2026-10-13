"""Offline decision references for synthetic workflow checks; no host integration."""

import argparse
import json
import re
from pathlib import Path


def selection_reply(action):
    messages = {
        "choose_empty_start": "기준 파일이 없다면 초기 작성 여부를 선택해 주세요.",
        "choose_baseline": "사용할 기준 JSON의 workspace/profile ID와 버전을 선택해 주세요.",
        "end_careerground": "요청하신 대로 CareerGround 작업을 종료합니다.",
    }
    return messages[action]


def final_reply(decision, proposed_reply):
    """Apply the selected-data prerequisite; project use is a recommendation."""
    if not isinstance(proposed_reply, str) or len(proposed_reply.encode("utf-8")) > 20000:
        raise ValueError("INVALID_PROPOSED_REPLY")
    return proposed_reply if decision["collect_career"] else decision["reply"]


def onboarding(
    status,
    *,
    baseline_count=0,
    selected=False,
    project_advice_seen=False,
    general_chat_requested=False,
):
    known = {"outside", "unknown", "ready", "declined", "unsupported", "move_failed"}
    if status not in known:
        raise ValueError("UNKNOWN_PROJECT_STATE")
    if baseline_count < 0:
        raise ValueError("INVALID_BASELINE_COUNT")
    if general_chat_requested:
        action = "end_careerground"
    elif baseline_count == 0:
        action = "start_empty" if selected else "choose_empty_start"
    else:
        action = "resume_selected" if selected else "choose_baseline"
    collect = selected and not general_chat_requested
    return {
        "action": action,
        "collect_career": collect,
        "ask_ready": False,
        "project_optional": True,
        "project_verified": False,
        "recommend_project": status in {"outside", "unknown"} and not project_advice_seen,
        "reply": None if collect else selection_reply(action),
    }


def public_search_query(conditions, *, user_approved=False):
    """Accept only user-reviewed public search fields, never a profile/statement."""
    allowed = {"role", "region", "work_mode", "level"}
    if not user_approved or not conditions or set(conditions) - allowed:
        raise ValueError("PUBLIC_CONDITIONS_REQUIRED")
    if any(
        not isinstance(v, str)
        or not v.strip()
        or len(v) > 100
        or re.search(r"@|https?://|\d{3,}|[\r\n]", v)
        for v in conditions.values()
    ):
        raise ValueError("PRIVATE_QUERY_REJECTED")
    return " ".join(conditions[k].strip() for k in sorted(conditions)) + " 채용"


def discovery_fallback(access, status="unknown"):
    if access in {"search_unavailable", "unavailable", "login_required"}:
        return "manual_jd_with_uncertainty"
    if status == "closed":
        return "exclude_closed_or_use_as_reference"
    if status == "unknown":
        return "show_status_unknown"
    return "show_observed_source_and_date"


def change_route(*, changes_facts):
    return "fact_candidate_review" if changes_facts else "wording_review"


def main():
    parser = argparse.ArgumentParser(description="CareerGround project entry decision; offline.")
    parser.add_argument(
        "status", choices=["outside", "unknown", "ready", "declined", "unsupported", "move_failed"]
    )
    parser.add_argument("--baseline-count", type=int, default=0)
    parser.add_argument("--selected", action="store_true")
    parser.add_argument("--project-advice-seen", action="store_true")
    parser.add_argument("--general-chat-requested", action="store_true")
    parser.add_argument("--reply-only", action="store_true")
    parser.add_argument("--proposed-reply", type=Path)
    args = parser.parse_args()
    result = onboarding(
        args.status,
        baseline_count=args.baseline_count,
        selected=args.selected,
        general_chat_requested=args.general_chat_requested,
        project_advice_seen=args.project_advice_seen,
    )
    if args.reply_only:
        proposed = ""
        if result["collect_career"] and args.proposed_reply:
            path = args.proposed_reply
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 20000:
                raise ValueError("INVALID_PROPOSED_REPLY")
            proposed = path.read_text(encoding="utf-8")
        print(final_reply(result, proposed))
    else:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
