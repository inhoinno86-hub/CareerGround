"""Inspect local skills-only sources and synthetic files; never install or deploy."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path

from build_chatgpt_plugin import PORTABLE_SOURCE, portable_files

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = PORTABLE_SOURCE / "references"
sys.path.insert(0, str(REFERENCES))
from exchange import validate_handoff, validate_result
from portable import load_json, validate_workspace


def check():
    files = portable_files()
    allowed_imports = {
        "__future__",
        "argparse",
        "copy",
        "hashlib",
        "json",
        "pathlib",
        "re",
        "portable",
        "jsonschema",
    }
    for name, content in files.items():
        if name.endswith(".py"):
            syntax = ast.parse(content, filename=name)
            for node in ast.walk(syntax):
                imports = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module]
                    if isinstance(node, ast.ImportFrom)
                    else []
                )
                if any(module.split(".")[0] not in allowed_imports for module in imports):
                    raise ValueError("Unreviewed package dependency: " + name)
        if re.search(
            rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|sk-[A-Za-z0-9]{20,}", content
        ):
            raise ValueError("Possible secret in package source")
    fixtures = ROOT / "fixtures/portable"
    results = []
    for name in [
        "empty-v1.json",
        "profile-v1.json",
        "base-resume-v1.json",
        "tailored-resume-v1.json",
    ]:
        errors = validate_workspace(load_json(fixtures / name))
        results.append({"file": name, "errors": errors, "passed": not errors})
    handoff = load_json(fixtures / "handoff-v1.json")
    errors = validate_handoff(handoff)
    results.append({"file": "handoff-v1.json", "errors": errors, "passed": not errors})
    errors = validate_result(load_json(fixtures / "result-v1.json"), handoff)
    results.append({"file": "result-v1.json", "errors": errors, "passed": not errors})
    errors = validate_handoff(load_json(fixtures / "handoff-missing-source.json"))
    results.append(
        {
            "file": "handoff-missing-source.json",
            "errors": errors,
            "passed": "MISSING_REFERENCE" in errors,
        }
    )
    errors = validate_result(load_json(fixtures / "result-conflict.json"), handoff)
    results.append(
        {"file": "result-conflict.json", "errors": errors, "passed": errors == ["HANDOFF_CONFLICT"]}
    )
    # Validate skill frontmatter using a stdlib check; skill-creator's YAML checker
    # is also run separately when its already-installed PyYAML is available.
    for name, content in files.items():
        if name.endswith("SKILL.md"):
            match = re.match(
                r"---\nname: ([a-z0-9-]+)\ndescription: ([^\n]+)\n---", content.decode()
            )
            if not match or match[1] != Path(name).parent.name or not match[2].strip():
                raise ValueError("Invalid skill header: " + name)
    return {
        "status": "LOCAL_PASS" if all(r["passed"] for r in results) else "LOCAL_FAIL",
        "scope": "offline_schema_references_package_and_authored_synthetic_fixtures",
        "inventory": [
            {"path": name, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
            for name, content in sorted(files.items())
        ],
        "fixture_checks": results,
        "career_backend_imports": False,
        "server_bindings": False,
        "installed_host_model_evaluation": "NOT_RUN",
        "actual_chatgpt_installation": "NOT_RUN",
        "actual_app_roundtrip": "NOT_RUN_STEP_08_EXCLUDED",
        "product_acceptance": "PENDING_HOST_INSTALLATION_AND_EVALUATION",
        "host_critical_failure_count": None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = check()
    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        # Preserve any earlier evidence rather than overwriting an existing report.
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(content)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "report": str(args.output),
                    "members": len(report["inventory"]),
                }
            )
        )
    else:
        print(content)
    raise SystemExit(report["status"] != "LOCAL_PASS")


if __name__ == "__main__":
    main()
