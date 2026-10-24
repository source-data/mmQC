"""``mmqc-skills``: keep a local copy of a published checklist current and sound.

    mmqc-skills pull   fig-checklist --entry do-fig-checklist-pm --dest skills/
    mmqc-skills verify skills/fig-checklist
    mmqc-skills status skills/fig-checklist

``pull`` brings ``<dest>/<checklist>`` to the release Langfuse labels
``production`` (or ``--label``), atomically, and does nothing when it is
already there. ``verify`` checks a local copy offline: each ``SKILL.md``
against the hash recorded when it was pulled, and the production rules.
``status`` compares the local release with the published one.

Exit codes: 0 fine (``status``: up to date); 1 a check failed (``status``:
an update is available); 2 a usage or configuration error.

Credentials for ``pull`` and ``status``: ``LANGFUSE_PUBLIC_KEY``,
``LANGFUSE_SECRET_KEY`` and ``LANGFUSE_BASE_URL`` (or ``LANGFUSE_HOST``).
Requires the ``langfuse`` package, which ``verify`` does not.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional

from mmqc_utils.agentic.publication import (
    PRODUCTION_LABEL,
    RELEASE_RECORD,
    published_release,
    pull_checklist,
    verify_local_checklist,
)


class _Uncached:
    """Langfuse reads that bypass the SDK's prompt cache: a release check must
    see the store as it is now."""

    def __init__(self, client: Any):
        self.client = client

    def get_prompt(self, name: str, *, label: str):
        return self.client.get_prompt(name, label=label, cache_ttl_seconds=0)


def langfuse_client() -> Any:
    try:
        from langfuse import Langfuse
    except ImportError as exc:
        raise SystemExit(f"mmqc-skills: {exc}; install the `langfuse` package") from exc
    missing = [v for v in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY") if not os.environ.get(v)]
    host = os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST")
    if missing or not host:
        raise SystemExit("mmqc-skills: set " + ", ".join(missing + ([] if host else ["LANGFUSE_BASE_URL"])))
    return _Uncached(Langfuse(public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
                              secret_key=os.environ["LANGFUSE_SECRET_KEY"], host=host))


def main(argv: Optional[List[str]] = None, *, client_factory: Callable[[], Any] = langfuse_client) -> int:
    parser = argparse.ArgumentParser(prog="mmqc-skills", description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    pull = commands.add_parser("pull", help="bring a local copy to the published release")
    pull.add_argument("checklist")
    pull.add_argument("--entry", required=True, help="the checklist's entry point")
    pull.add_argument("--dest", type=Path, required=True, help="directory holding local checklists")
    pull.add_argument("--label", default=PRODUCTION_LABEL)

    verify = commands.add_parser("verify", help="check a local copy offline")
    verify.add_argument("path", type=Path)

    status = commands.add_parser("status", help="compare a local copy with the published release")
    status.add_argument("path", type=Path)

    args = parser.parse_args(argv)

    if args.command == "verify":
        try:
            record = verify_local_checklist(args.path)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 1
        print(f"{args.path}: release {record['release'][:12]}, {len(record['skills'])} skills, verified")
        return 0

    if args.command == "pull":
        try:
            record = pull_checklist(client_factory(), args.checklist, args.entry, args.dest, label=args.label)
        except ValueError as exc:
            print(f"pull refused; the local copy is unchanged:\n{exc}", file=sys.stderr)
            return 1
        verb = "updated to" if record["changed"] else "already at"
        print(f"{args.dest / args.checklist}: {verb} release {record['release'][:12]} "
              f"({len(record['skills'])} skills, label {record['label']})")
        return 0

    record_path = args.path / RELEASE_RECORD
    if not record_path.is_file():
        print(f"{args.path}: no {RELEASE_RECORD}; pull it first", file=sys.stderr)
        return 2
    local = json.loads(record_path.read_text(encoding="utf-8"))
    remote = published_release(client_factory(), local["checklist"], local["entry"], label=local["label"])
    if remote == local["release"]:
        print(f"{args.path}: up to date (release {remote[:12]})")
        return 0
    print(f"{args.path}: release {local['release'][:12]} locally, {str(remote)[:12]} published -- pull to update")
    return 1


if __name__ == "__main__":
    sys.exit(main())
