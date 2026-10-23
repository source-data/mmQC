"""Standing checks on the production checklist's contracts and on the gold.

The contract cleanup (thinking/plans/2026-09-30-contract-cleanup.md, W9)
brought every fig-checklist contract to zero audit findings. These tests keep
it there: a schema, manifest or gold change that breaks a convention fails here
rather than surfacing as a scoring artifact in the next experiment.
"""

from __future__ import annotations

import json

from soda_mmqc.scripts.audit_contracts import _CONTROL, EXAMPLES, audit


def test_the_production_checklist_audits_clean():
    findings = audit(["fig-checklist"])
    assert findings == [], "\n".join(
        f"{f.rule} {f.check} · {f.field}: {f.detail}" for f in findings)


def _strings(node, path=""):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _strings(value, f"{path}[{i}]")


def test_no_gold_holds_control_characters():
    """All gold, whatever checklist its check belongs to.

    The audit's gold-control rule sees only the checks of the checklists it is
    asked about, so gold of a retired check went unseen: 212 vertical tabs in
    micrograph-symbols-defined, found by hand after the audit reported zero.
    """
    damaged = [
        f"{path.relative_to(EXAMPLES)} {where}: {text[:60]!r}"
        for path in sorted(EXAMPLES.glob("**/expected_output.json"))
        for where, text in _strings(json.loads(path.read_text(encoding="utf-8")))
        if _CONTROL.search(text)
    ]
    assert damaged == [], "\n".join(damaged)


# ---------------------------------------------------------------------------
# The entry skill's contract is derived from the checks' own and copied into
# production. A change to one check's contract that is not rederived into the
# entry's would score that check differently in a whole-checklist run than on
# its own.
#
# Production answers panel-major since exp-10 (2026-10-22): one row per panel,
# each check's row fields under its name, derived by
# experiments/exp-10-panel-major-revisited/build_contract.py --target fig-checklist.
# ---------------------------------------------------------------------------

from pathlib import Path  # noqa: E402

_FIG = Path(__file__).resolve().parents[1] / "soda_mmqc" / "data" / "checklist" / "fig-checklist"
_PM = "do-fig-checklist-pm"


def _read(*parts):
    return json.loads((_FIG.joinpath(*parts)).read_text(encoding="utf-8"))


def _checks():
    row = _read(_PM, "schema.json")["format"]["schema"]["properties"]["outputs"]["items"]
    return [name for name in row["properties"] if name not in ("panel_label", "panel_classes")]


def test_the_entry_contract_covers_the_eleven_checks():
    assert len(_checks()) == 11


def test_the_panel_major_contract_holds_each_checks_row_fields_verbatim():
    row = _read(_PM, "schema.json")["format"]["schema"]["properties"]["outputs"]["items"]
    assert list(row["properties"])[:2] == ["panel_label", "panel_classes"]
    for check in _checks():
        own = _read(check, "schema.json")["format"]["schema"]["properties"]["outputs"]["items"]
        assert row["properties"]["panel_label"] == own["properties"]["panel_label"]
        assert row["properties"][check]["properties"] == {
            k: v for k, v in own["properties"].items() if k != "panel_label"}, f"{check}: rederive"
        assert row["properties"][check]["required"] == [
            k for k in own["required"] if k != "panel_label"], f"{check}: rederive"


def test_the_panel_major_manifest_holds_each_checks_fields_under_its_name():
    entry = _read(_PM, "eval-manifest.json")
    assert entry["fields"]["outputs[].panel_classes"] == {"scored": False}
    for check in _checks():
        own = _read(check, "eval-manifest.json")
        for field, profile in own.get("fields", {}).items():
            if field == "outputs[].panel_label":
                assert entry["fields"][field] == profile
                continue
            key = f"outputs[].{check}." + field[len("outputs[]."):]
            assert entry["fields"].get(key) == profile, f"{check} · {field}: rederive"
        for nested, by in own["list_alignment"].items():
            if nested != "outputs":
                assert entry["list_alignment"][f"{check}.{nested}"] == by
