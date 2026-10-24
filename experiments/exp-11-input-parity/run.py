"""Run exp-11: the figure as production sends it, against the stored file.

`fig-checklist-exp11` -- a copy of the production checklist -- run on every
figure, the same day, with Sonnet 5.5, once per input
(thinking/experiments/exp-11-input-parity.md):

    stored      the figure's file as stored, sent as it is (every earlier run)
    converted   the same file through mmqc_utils' figure_image_part:
                300 dpi, 2,048 px, JPEG 80, converted once, sent as bytes

The skills, contracts and gold are the same; only the image bytes differ.

Output:

    experiments/runs/exp-11-input-parity/{stored,converted}/pinned/rep-NN/<example>/

    python experiments/exp-11-input-parity/run.py --smoke
    python experiments/exp-11-input-parity/run.py --dry-run
    python experiments/exp-11-input-parity/run.py

222 sessions: 2 inputs x 37 figures x 3 replicates, at concurrency 38.
Re-running skips what already has a prediction and leaves a kept failure
alone; an account or connection error stops the run. Scoring is the
notebook's, against `gold-v7`, after it has checked from each session's image
fingerprint that the arm sent what it claims.

The converted arm needs ImageMagick (`MAGICK_HOME` on macOS with Homebrew).

**Gate 4B (2026-10-24) adopted the converted input**: `FigureExample` now
sends the converted figure, and the temporary switch that ran the stored
arm is gone. The runs cannot be repeated from this commit -- check out
24e99b665 for that. What the notebook needs still works: the constants, and
the image each arm must have sent (computed from the stored file).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from soda_mmqc import logger                                      # noqa: E402
from soda_mmqc.agentic.runner import RunAborted, run_check_live   # noqa: E402
from soda_mmqc.core.examples import EXAMPLE_FACTORY               # noqa: E402
from mmqc_utils.agentic import figure_image_part                  # noqa: E402
from mmqc_utils.agentic.runtime import ASSEMBLY_CLOSURE            # noqa: E402
from soda_mmqc.config import resolve_check_dir                    # noqa: E402

#: The commit that can still run both arms.
RUNNABLE_AT = "24e99b665"

CHECKLIST = "fig-checklist-exp11"
ENTRY = "do-fig-checklist-pm"
#: arm -> example class override (None: the benchmark's own, `figure`)
ARMS: Dict[str, Optional[str]] = {"stored": None, "converted": "figure-converted"}
#: In D's order.
CHECKS = (
    "micrograph-scale-bar", "image-annotation-defined", "single-channel-for-overlay",
    "individual-data-points", "error-bars-defined", "plot-axis-units", "plot-gap-labeling",
    "stat-significance-level", "stat-test", "replication-reporting",
    "panel-image-matches-caption",
)
CLASSIFY = "classify-panels"

MODEL = "claude-sonnet-5-5"
PROVIDER = "claude-sdk"
GOLD_TAG = "gold-v7"
ASSEMBLY = ASSEMBLY_CLOSURE
REPLICATES = 3
CONCURRENCY = 38
ARM_DIR = "pinned"

RUNS = REPO / "experiments" / "runs" / "exp-11-input-parity"


def benchmark_examples() -> List[str]:
    return json.loads((resolve_check_dir(CHECKLIST, ENTRY) / "benchmark.json")
                      .read_text(encoding="utf-8"))["examples"]


def expected_image_sha256(arm: str, example: str) -> str:
    """The SHA-256 of the image this arm must have sent for this figure.

    Stored: the stored file's bytes. Converted: `figure_image_part` on that
    file, re-converted now -- so a change in ImageMagick since the run shows.
    """
    stored = EXAMPLE_FACTORY.create(example, "figure").image_path
    data = stored.read_bytes() if arm == "stored" else figure_image_part(stored)["data"]
    return hashlib.sha256(data).hexdigest()


def preflight() -> bool:
    """The converted arm converts with ImageMagick; fail before any session if it cannot."""
    try:
        expected_image_sha256("converted", benchmark_examples()[0])
    except ImportError as exc:
        logger.error("The converted arm cannot convert: %s", str(exc).splitlines()[0])
        logger.error("Set MAGICK_HOME (Homebrew: export MAGICK_HOME=/opt/homebrew/opt/imagemagick).")
        return False
    return True


def run(root: Path, *, replicates: int, limit: Optional[int], force: bool) -> List[str]:
    failures: List[str] = []
    for arm, example_class in ARMS.items():
        logger.info("--- %s: %s, %d replicate(s) ---", arm, example_class or "figure", replicates)
        _, report = run_check_live(
            CHECKLIST, ENTRY, output=root / arm, model=MODEL, provider=PROVIDER, limit=limit,
            replicates=replicates, force=force, assembly=ASSEMBLY,
            concurrency=CONCURRENCY, retry_failed=False,
        )
        logger.info("  %d ran, %d skipped, %d failed",
                    sum(e["status"] == "ok" for e in report),
                    sum(e["status"] == "skipped" for e in report),
                    sum(e["status"] == "failed" for e in report))
        failures += [f"{arm} rep-{e['replicate']:02d} {e['example']}: {e.get('error', '')}"
                     for e in report if e["status"] == "failed"]
    return failures


def report_smoke(root: Path) -> int:
    """Per session: dispatch, cost, and whether the image sent is the arm's."""
    worst = 0
    for arm in ARMS:
        leaf = root / arm / ARM_DIR / "rep-00"
        found = sorted(leaf.glob("**/prediction.json"))
        if not found:
            logger.error("  %s: no sessions", arm)
            worst = 1
            continue
        for prediction in found:
            example = str(prediction.parent.relative_to(leaf))
            intermediates = prediction.parent / "intermediates"
            skills = [e.get("skill") for e in json.loads((intermediates / "skill_trace.json").read_text())]
            audit = json.loads((intermediates / "tool_audit.json").read_text())
            usage = audit.get("usage") or {}
            sent = audit.get("inputs") or []
            image_ok = (len(sent) == 1 and sent[0]["sha256"] == expected_image_sha256(arm, example))
            called = list(dict.fromkeys(k for k in skills if k in CHECKS))
            answer = json.loads(prediction.read_text())
            logger.info("  %-9s %-38s %2d/11 checks  $%.3f  %d turns  %d in  image %s %s %s",
                        arm, example, len(called), usage.get("total_cost_usd") or 0,
                        usage.get("num_turns") or 0, (usage.get("usage") or {}).get("input_tokens") or 0,
                        sent[0]["media_type"] if sent else "-", sent[0]["dimensions"] if sent else "-",
                        "ok" if image_ok else "WRONG")
            if set(answer) != {"outputs"} or not image_ok:
                worst = 1
    return worst


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Both inputs on a few figures, one replicate")
    args = parser.parse_args(argv)

    if not args.dry_run:
        logger.error("exp-11 cannot be rerun from this commit: gate 4B made the converted input "
                     "the only one. Check out %s to rerun either arm.", RUNNABLE_AT)
        return 2
    if not preflight():
        return 2

    if args.smoke:
        root = RUNS / "smoke"
        limit = args.limit or 3
        logger.info("exp-11 smoke test: both inputs, %d figure(s), 1 replicate", limit)
        try:
            failures = run(root, replicates=1, limit=limit, force=True)
        except RunAborted as stopped:
            logger.error("smoke test stopped on an account or connection error: %s", stopped)
            return 2
        for line in failures:
            logger.error("  %s", line)
        return report_smoke(root) or (1 if failures else 0)

    n = len(benchmark_examples())
    n = min(n, args.limit) if args.limit else n
    logger.info("exp-11: up to %d session(s), concurrency %d", len(ARMS) * n * REPLICATES, CONCURRENCY)
    if args.dry_run:
        for arm, example_class in ARMS.items():
            print(f"  {arm:9} {CHECKLIST} {ENTRY} ({example_class or 'figure'}), "
                  f"{REPLICATES} replicates -> {RUNS / arm / ARM_DIR}")
        return 0
    try:
        failures = run(RUNS, replicates=REPLICATES, limit=args.limit, force=args.force)
    except RunAborted as stopped:
        logger.error("exp-11 stopped on an account or connection error: %s", stopped)
        logger.error("Fix the API key, the account or the network, then rerun the same command: "
                     "predictions already written are skipped.")
        return 2
    if failures:
        logger.error("%d session(s) failed:", len(failures))
        for line in failures:
            logger.error("  %s", line)
        return 1
    logger.info("exp-11 complete; runs under %s", RUNS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
