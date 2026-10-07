"""Read-only discovery of retained Phase A QA stores; never restores a store.

Reports file presence and checkpoint counts only. No signing keys, provider
subjects, source text, tokens, or receipts are read. A candidate still needs
the runtime's signature/binding and deletion checks before reuse.
"""

import argparse
import json
import os
import sqlite3
from pathlib import Path

STORE_FILES = {
    ".careerground-authenticated-v1",
    "binding.json",
    "key-digests.json",
    "authenticated.sqlite",
    ".runtime.lock",
    "ledger.json",
    "manifest",
    "admission.key",
    "review.key",
    "presentation.key",
    "ledger.key",
    "status.key",
}


def default_roots(project, user_root):
    roots = []
    for parent, pattern in (
        (Path("/tmp"), "careerground-*"),
        (project, ".careerground*"),
        (user_root / ".cache", "careerground*"),
        (user_root / ".local/share", "careerground*"),
    ):
        if parent.is_dir():
            roots.extend(sorted(parent.glob(pattern)))
    return roots


def inspect_store(path):
    info = {
        "database": str(path),
        "store_files_present": all((path.parent / name).is_file() for name in STORE_FILES),
        "passkey_directory_present": (path.parent.parent / "passkeys").is_dir(),
        "denial_directory_present": (path.parent.parent / "connection-denials").is_dir(),
        "wal_present": Path(str(path) + "-wal").is_file(),
        "runtime_binding_verified": False,
    }
    connection = None
    try:
        # Immutable mode also avoids creating/writing WAL shared-memory files.
        # Counts describe the saved checkpoint, not a live WAL snapshot.
        connection = sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)
        connection.execute("PRAGMA query_only=ON")
        info["profile_status_counts"] = dict(
            connection.execute("SELECT status, count(*) FROM career_profiles GROUP BY status")
        )
        info["checkpoint_readable"] = True
    except sqlite3.Error:
        info["checkpoint_readable"] = False
    finally:
        if connection is not None:
            connection.close()
    return info


def discover(roots, limit=4096):
    stack = [(p.absolute(), 0) for p in roots if p.is_dir() and not p.is_symlink()]
    visited, found = set(), []
    scan_complete = True
    while stack:
        if len(visited) >= limit:
            scan_complete = False
            break
        directory, depth = stack.pop()
        if directory in visited:
            continue
        visited.add(directory)
        try:
            children = sorted(directory.iterdir())
        except OSError:
            scan_complete = False
            continue
        for child in children:
            if child.is_symlink():
                continue
            if child.is_file() and child.name == "authenticated.sqlite":
                if child.stat().st_uid == os.getuid():
                    found.append(inspect_store(child))
            elif child.is_dir():
                if depth < 5:
                    stack.append((child, depth + 1))
                else:
                    scan_complete = False
    return {
        "scan_complete": scan_complete,
        "scope": "selected_careerground_directories_only",
        "directories_visited": len(visited),
        "stores": found,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan-root", type=Path, action="append")
    args = parser.parse_args()
    pointer = Path("/tmp/careerground-release-qa-path")
    roots = args.scan_root or default_roots(Path(__file__).resolve().parents[1], Path.home())
    result = discover(roots)
    result["release_pointer_present"] = pointer.is_file()
    result["original_release_base_present"] = Path("/tmp/careerground-release-qa-reqec5wa").is_dir()
    result["restored_or_initialized"] = False
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
