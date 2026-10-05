"""A run stops at the first account error, and carries on past any other.

exp-04's first full run (2026-10-05) failed 25 sessions in a row on a revoked
API key, three minutes apiece, before anyone looked. A failure about the
example is recorded and the run continues; a failure about the account
cannot be outlived by the next session, so it ends the run.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soda_mmqc.agentic import runner
from soda_mmqc.agentic.runner import RunAborted, is_account_error, run_check_live
from soda_mmqc.config import EXAMPLES_DIR

CHECKLIST, CHECK = "fig-checklist", "micrograph-scale-bar"

REVOKED = ("Claude Code returned an error result: Failed to authenticate. "
           "API Error: 401 API key is invalid. (exit code: 1)")


def _two_examples() -> list[str]:
    benchmark = json.loads((runner.resolve_check_dir(CHECKLIST, CHECK) / "benchmark.json")
                           .read_text(encoding="utf-8"))
    present = [e for e in benchmark["examples"] if (EXAMPLES_DIR / e).is_dir()]
    if len(present) < 2:
        pytest.skip("needs two benchmark examples on disk")
    return present[:2]


def _failing_with(monkeypatch, message: str) -> list[str]:
    calls: list[str] = []

    async def fake_session(layout, *, versions, approver, options, client):
        calls.append(str(layout))
        raise RuntimeError(message)

    monkeypatch.setattr(runner, "_run_agent_session", fake_session)
    monkeypatch.setattr(runner, "_openai_session_client", lambda layout, model: None)
    return calls


@pytest.mark.parametrize("message, account", [
    (REVOKED, True),
    ("Error code: 401 - {'type': 'error', 'error': {'type': 'authentication_error'}}", True),
    ("Your credit balance is too low to access the Anthropic API.", True),
    ("Error code: 403 - permission_error", True),
    ("Error code: 429 - rate_limit_error", False),
    ("Error code: 529 - overloaded_error", False),
    ("prediction does not validate against schema.json", False),
])
def test_which_errors_are_about_the_account(message, account):
    assert is_account_error(RuntimeError(message)) is account


def test_an_account_error_stops_the_run(tmp_path: Path, monkeypatch):
    examples = _two_examples()
    calls = _failing_with(monkeypatch, REVOKED)
    with pytest.raises(RunAborted) as stopped:
        run_check_live(CHECKLIST, CHECK, output=tmp_path, examples=examples)
    assert len(calls) == 1
    assert [e["status"] for e in stopped.value.report] == ["failed"]
    assert stopped.value.report[0]["example"] == examples[0]


def test_any_other_failure_is_recorded_and_the_run_goes_on(tmp_path: Path, monkeypatch):
    examples = _two_examples()
    calls = _failing_with(monkeypatch, "prediction does not validate against schema.json")
    _, report = run_check_live(CHECKLIST, CHECK, output=tmp_path, examples=examples)
    assert len(calls) == 2
    assert [e["status"] for e in report] == ["failed", "failed"]
