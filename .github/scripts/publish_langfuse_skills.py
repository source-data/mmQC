#!/usr/bin/env python3
"""Publish the production checklists' skills to Langfuse.

Usage:
    python .github/scripts/publish_langfuse_skills.py --dry-run [--out DIR]
    python .github/scripts/publish_langfuse_skills.py

Which checklists: the `skills` list of
soda_mmqc/data/production_prompts/production.json. Which versions: each
checklist's own version-manifest.yaml. One prompt per pinned skill,
`skills/<checklist>/<skill>`, labelled `production`; what a prompt holds is
mmqc_harness.publication's account (the whole SKILL.md as text, the
contracts and the release in the config).

Per checklist, the script:
1. checks the production rules (one entry point, every pin reached, one
   topology) and builds the payloads;
2. with --dry-run, writes them to DIR as JSON and stops -- no credentials;
3. otherwise skips the checklist if Langfuse's `production` entry point
   already carries this release (the digest of the skill set), else creates
   every prompt;
4. loads the published checklist back, uncached, and checks every skill's
   content hash against the repository's.

Credentials: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL.
Needs mmqc_harness (which brings mmqc_utils and pyyaml) and
langfuse.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mmqc_harness.publication import (
    PRODUCTION_LABEL,
    load_published_checklist,
    production_entry_point,
    prompt_name,
    skill_payloads,
)

REPO = Path(__file__).resolve().parents[2]
CHECKLIST_DIR = REPO / "soda_mmqc" / "data" / "checklist"
MANIFEST = REPO / "soda_mmqc" / "data" / "production_prompts" / "production.json"


class _Uncached:
    """A Langfuse client whose reads bypass the SDK's prompt cache."""

    def __init__(self, client):
        self.client = client

    def get_prompt(self, name, *, label):
        return self.client.get_prompt(name, label=label, cache_ttl_seconds=0)


def _langfuse():
    from langfuse import Langfuse

    return Langfuse(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=os.environ["LANGFUSE_BASE_URL"],
    )


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _published_release(client, checklist: str, entry: str):
    """The release Langfuse's `production` entry point carries, or None."""
    try:
        fetched = client.get_prompt(prompt_name(checklist, entry), label=PRODUCTION_LABEL)
    except Exception:          # not found, on a first publish
        return None
    return ((fetched.config or {}).get("skill") or {}).get("release")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="Write the payloads; publish nothing")
    parser.add_argument("--out", type=Path, default=Path("langfuse-skills-dry-run"),
                        help="Where --dry-run writes the payloads (default: %(default)s)")
    args = parser.parse_args(argv)

    checklists = json.loads(MANIFEST.read_text(encoding="utf-8")).get("skills") or []
    if not checklists:
        print("production.json lists no skill checklists; nothing to publish")
        return 0
    client = None if args.dry_run else _Uncached(_langfuse())

    for checklist in checklists:
        checklist_dir = CHECKLIST_DIR / checklist
        entry = production_entry_point(checklist_dir)
        payloads = skill_payloads(checklist_dir)
        release = payloads[0]["config"]["skill"]["release"]
        print(f"{checklist}: entry point {entry}, {len(payloads)} skills, release {release[:12]}")
        for payload in payloads:
            meta = payload["config"]["skill"]
            print(f"  {payload['name']:<52} {meta['version']:<4} {meta['role']:<7} "
                  f"config: {', '.join(sorted(payload['config']))}")

        if args.dry_run:
            for payload in payloads:
                path = args.out / f"{payload['name']}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"  dry run: payloads written under {args.out / 'skills' / checklist}")
            continue

        if _published_release(client, checklist, entry) == release:
            print("  already published: Langfuse's production entry point carries this release")
            continue
        message = f"release {release[:12]} from {_commit()}"
        for payload in payloads:
            client.client.create_prompt(**payload, commit_message=message)
        print(f"  published {len(payloads)} prompts ({message})")

        with tempfile.TemporaryDirectory() as tmp:
            loaded = load_published_checklist(client, checklist, entry, Path(tmp))
            local = {p["name"]: p["config"]["skill"]["content_hash"] for p in payloads}
            for payload in payloads:
                meta = payload["config"]["skill"]
                text = (loaded / meta["name"] / meta["version"] / "SKILL.md").read_text(encoding="utf-8")
                if text != payload["prompt"]:
                    print(f"  VERIFY FAILED: {payload['name']} differs from the repository")
                    return 1
            print(f"  verified: {len(local)} skills loaded back from Langfuse, identical to the repository")
    return 0


if __name__ == "__main__":
    sys.exit(main())
