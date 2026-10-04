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
