#!/usr/bin/env python3
"""Export a static HTML snapshot of fig-checklist evaluation results.

Example:
  export-fig-report
  export-fig-report --models gpt-5.4,gpt-5-mini-2025-08-07
  export-fig-report --checks stat-significance-level,plot-gap-labeling --no-comparison
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from soda_mmqc.reporting.export_report import export_fig_checklist_report


def _parse_csv_list(value: str | None) -> list[str] | None:
    if value is None or not value.strip():
        return None
    return [part.strip() for part in value.split(",") if part.strip()]


def main(argv: list[str] | None = None) -> int:
    today = date.today().isoformat()
    default_out = Path("reports") / "fig-checklist" / today

    parser = argparse.ArgumentParser(
        description=(
            "Export fig-checklist evaluation charts and score tables to a "
            "static HTML folder (snapshot for sharing/archiving)."
        )
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=default_out,
        help=f"Output directory (default: {default_out})",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help=(
            "Comma-separated model folder names to include, in display order "
            "(default: all models found per check)."
        ),
    )
    parser.add_argument(
        "--checks",
        type=str,
        default=None,
        help="Comma-separated check names (default: all fig-checklist checks with eval data).",
    )
    parser.add_argument(
        "--no-comparison",
        action="store_true",
        help="Skip Layer S / Layer 1 / Layer 2 overlay charts.",
    )
    args = parser.parse_args(argv)

    models = _parse_csv_list(args.models)
    checks = _parse_csv_list(args.checks)
    summaries = export_fig_checklist_report(
        out_dir=args.out,
        models=models,
        checks=checks,
        include_comparison=not args.no_comparison,
    )

    ok = [item for item in summaries if item.skipped_reason is None]
    skipped = [item for item in summaries if item.skipped_reason is not None]
    print(f"Wrote report to {args.out.resolve()}")
    print(f"  checks exported: {len(ok)}")
    print(f"  checks skipped:  {len(skipped)}")
    for item in ok:
        winners = "; ".join(item.winners) if item.winners else "(no winners)"
        print(f"  - {item.check}: {winners}")
    for item in skipped:
        print(f"  - {item.check}: skipped ({item.skipped_reason})")
    print(f"Open {args.out / 'index.html'} in a browser.")
    print(f"Mean-scores overview: {args.out / 'mean-scores.html'}")
    print(f"Key-fields summary: {args.out / 'key-fields.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
