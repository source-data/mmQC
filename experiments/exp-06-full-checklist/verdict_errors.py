"""exp-06's error-analysis candidates: recurring disagreements on each check's verdict.

Decided with the author, 2026-10-11: the error analysis starts from what a
reader acts on -- each check's verdict, its `decision`, or the property that
plays that part where a check has none -- and puts aside the text extractions
scored by semantic comparison.

Reads the scored instances (`analysis.json`) of the baseline arrangement,
`A|B <- C_i <- D` (arm `pinned`), and keeps every verdict instance that is a
layer-1 applicability error or a layer-2 disagreement. Grouped by (figure,
check, panel, property, gold value): how many of the five replicates got it
wrong, the commonest wrong prediction, the outcomes; then those wrong in at
least MIN_SESSIONS replicates, with the gold row and one wrong predicted row
of that check for that panel, so each can be sorted with the whole answer in
view.

    python experiments/exp-06-full-checklist/verdict_errors.py
    python experiments/exp-06-full-checklist/verdict_errors.py --force   # rewrite

Writes `error_analysis_verdicts.csv` beside this script, with empty `sorting`
(model error | gold error | ambiguous) and `note` columns for the manual pass.
It refuses to overwrite an existing file unless --force, so annotations are not
lost to a rerun. Run the notebook first: it writes the analyses this reads.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from soda_mmqc.reporting.styles import (  # noqa: E402
    LAYER1_OUTLIER_OUTCOMES as LAYER1_ERRORS,
    LAYER2_ERROR_OUTCOMES as LAYER2_ERRORS,
)
LEAF_ROOT = REPO / "experiments" / "runs" / "exp-06-full-checklist" / "pinned"
OUT = HERE / "error_analysis_verdicts.csv"
MIN_SESSIONS = 3

#: Each check's verdict: its decision, or what plays that part.
VERDICTS: Dict[str, List[str]] = {
    "micrograph-scale-bar": ["scale_bar_on_image", "scale_bar_defined_in_caption",
                             "scale_bar_defined_in_image"],
    "image-annotation-defined": ["annotation_defined_in_caption"],
    "single-channel-for-overlay": ["all_channels_shown_separately"],
    "individual-data-points": ["decision"],
    "error-bars-defined": ["decision"],
    "plot-axis-units": ["decision"],
    "plot-gap-labeling": ["decision"],
    "stat-significance-level": ["decision"],
    "stat-test": ["decision"],
    "replication-reporting": ["decision"],
    "panel-image-matches-caption": ["image_matches_caption"],
}


def owner(leaf_property: str) -> Optional[str]:
    return next((c for c in VERDICTS if leaf_property.startswith(f"{c}[")), None)


def row_index(path: str) -> Optional[int]:
    head = path.split("].", 1)[0]
    return int(head.rsplit("[", 1)[1]) if "[" in head else None


def compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--force", action="store_true", help="Overwrite an existing file")
    args = parser.parse_args(argv)
    if OUT.exists() and not args.force:
        print(f"{OUT.name} exists; annotations may be in it. Use --force to rewrite.")
        return 1

    groups: Dict[tuple, Dict[str, Any]] = defaultdict(lambda: {"reps": set(), "preds": Counter(),
                                                             "outcomes": Counter(), "pred_row": None})
    for analysis_path in sorted(LEAF_ROOT.glob("rep-*/analysis.json")):
        replicate = analysis_path.parent.name
        for record in json.loads(analysis_path.read_text(encoding="utf-8")).get("flat", []):
            example = (record.get("metadata") or {}).get("source")
            gold, pred = record.get("expected_output") or {}, record.get("model_output") or {}
            for inst in (record.get("analysis") or {}).get("instances", []):
                check = owner(inst["leaf_property"])
                if check is None:
                    continue
                prop = inst["leaf_property"][len(check) + 3:].split("[", 1)[0]
                if prop not in VERDICTS[check]:
                    continue
                l1, l2 = inst.get("layer1"), inst.get("layer2")
                score = inst.get("score")
                # A list-valued verdict (image-annotation-defined's, one entry
                # per annotation) carries no layer label, only a score.
                list_error = l1 is None and l2 is None and score is not None and score < 1
                if l1 not in LAYER1_ERRORS and l2 not in LAYER2_ERRORS and not list_error:
                    continue
                outcome = (l1 if l1 in LAYER1_ERRORS else l2 if l2 in LAYER2_ERRORS
                           else f"list score {score:.2f}")
                i = row_index(inst["path"])
                gold_rows = gold.get(check) or []
                gold_row = gold_rows[i] if i is not None and i < len(gold_rows) else {}
                panel = gold_row.get("panel_label")
                key = (example, check, panel, prop, compact(inst.get("exp_value")))
                g = groups[key]
                g["reps"].add(replicate)
                g["preds"][compact(inst.get("pred_value"))] += 1
                g["outcomes"][outcome] += 1
                g["gold_row"] = gold_row
                if g["pred_row"] is None:
                    g["pred_row"] = next((r for r in pred.get(check) or []
                                          if r.get("panel_label") == panel), {})

    rows = []
    for (example, check, panel, prop, exp_value), g in groups.items():
        if len(g["reps"]) < MIN_SESSIONS:
            continue
        rows.append({
            "check": check, "property": prop, "example": example, "panel": panel,
            "sessions_wrong": len(g["reps"]), "gold_value": exp_value,
            "commonest_prediction": g["preds"].most_common(1)[0][0],
            "outcome": g["outcomes"].most_common(1)[0][0],
            "gold_row": compact(g["gold_row"]), "a_wrong_predicted_row": compact(g["pred_row"]),
            "sorting": "", "note": "",
        })
    order = {c: n for n, c in enumerate(VERDICTS)}
    rows.sort(key=lambda r: (order[r["check"]], -r["sessions_wrong"], r["example"], str(r["panel"])))
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["check"])
        writer.writeheader()
        writer.writerows(rows)
    per_check = Counter(r["check"] for r in rows)
    print(f"{len(rows)} recurring verdict disagreements (wrong in >= {MIN_SESSIONS} of 5 replicates) "
          f"written to {OUT.relative_to(REPO)}")
    for check in VERDICTS:
        print(f"  {check:<28} {per_check.get(check, 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
