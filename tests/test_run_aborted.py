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

    monkeypatch.setattr(runner, "run_session", fake_session)
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


# ---------------------------------------------------------------------------
# Concurrent runs: the same sessions, the same report, the same stop.
# ---------------------------------------------------------------------------

from mmqc_utils.agentic.session import ToolAuditLog  # noqa: E402


def _examples(n: int) -> list[str]:
    benchmark = json.loads((runner.resolve_check_dir(CHECKLIST, CHECK) / "benchmark.json")
                           .read_text(encoding="utf-8"))
    present = [e for e in benchmark["examples"] if (EXAMPLES_DIR / e).is_dir()]
    if len(present) < n:
        pytest.skip(f"needs {n} benchmark examples on disk")
    return present[:n]


def _answering(monkeypatch, tmp_path: Path, *, fail_on: str | None = None) -> list[str]:
    """A session that answers validly, or fails on one example with an account error."""
    calls: list[str] = []

    class _Recorder:
        invoked: list[str] = []
        entries: list = []

    async def fake_session(layout, *, versions, approver, options, client):
        example = str(layout.example) if hasattr(layout, "example") else str(layout)
        calls.append(example)
        if fail_on is not None and fail_on in example:
            raise RuntimeError(REVOKED)
        audit = ToolAuditLog(tmp_path / f"audit-{len(calls)}.json")
        return {"outputs": []}, _Recorder(), audit

    monkeypatch.setattr(runner, "run_session", fake_session)
    monkeypatch.setattr(runner, "_openai_session_client", lambda layout, model: None)
    return calls


def test_a_concurrent_run_reports_what_a_sequential_one_does(tmp_path: Path, monkeypatch):
    examples = _examples(4)
    _answering(monkeypatch, tmp_path)
    _, one = run_check_live(CHECKLIST, CHECK, output=tmp_path / "seq", examples=examples,
                            replicates=2)
    _, many = run_check_live(CHECKLIST, CHECK, output=tmp_path / "par", examples=examples,
                             replicates=2, concurrency=3)
    key = lambda report: [(e["example"], e["replicate"], e["status"]) for e in report]
    assert key(many) == key(one)
    assert all(e["status"] == "ok" for e in many)


def test_each_session_records_the_concurrency_it_ran_at(tmp_path: Path, monkeypatch):
    examples = _examples(2)
    _answering(monkeypatch, tmp_path)
    root, _ = run_check_live(CHECKLIST, CHECK, output=tmp_path / "par", examples=examples,
                             concurrency=2)
    audits = list(root.rglob("intermediates/tool_audit.json"))
    assert len(audits) == 2
    assert {json.loads(a.read_text())["session"]["concurrency"] for a in audits} == {2}


def test_an_account_error_stops_a_concurrent_run(tmp_path: Path, monkeypatch):
    examples = _examples(6)
    calls = _answering(monkeypatch, tmp_path, fail_on=examples[0])
    with pytest.raises(RunAborted) as stopped:
        run_check_live(CHECKLIST, CHECK, output=tmp_path, examples=examples, replicates=3,
                       concurrency=2)
    # 18 sessions planned; the run stops long before them.
    assert len(calls) < 18
    assert any(e["status"] == "failed" for e in stopped.value.report)


@pytest.mark.parametrize("kwargs", [{"concurrency": 0},
                                    {"concurrency": 2, "approve_tools": True}])
def test_concurrency_is_refused_where_it_cannot_work(tmp_path: Path, kwargs):
    with pytest.raises(ValueError):
        run_check_live(CHECKLIST, CHECK, output=tmp_path, examples=["x"], **kwargs)


def test_a_failed_session_keeps_its_trace_audit_and_error(tmp_path: Path, monkeypatch):
    """exp-07: a session that declined to answer left no record at all."""
    from mmqc_utils.agentic.session import SKILL_TRACE_FILENAME, TOOL_AUDIT_FILENAME
    (example,) = _examples(1)

    async def fake_session(layout, *, versions, approver, options, client):
        intermediates = layout.artifacts_root / "intermediates"
        audit = ToolAuditLog(intermediates / TOOL_AUDIT_FILENAME)
        audit.note_usage({"total_cost_usd": 0.02, "num_turns": 9})
        (intermediates / SKILL_TRACE_FILENAME).write_text('[{"skill": "micrograph-scale-bar"}]')
        raise ValueError("The session's result is not JSON, which means it declined to answer")

    monkeypatch.setattr(runner, "run_session", fake_session)
    monkeypatch.setattr(runner, "_openai_session_client", lambda layout, model: None)
    root, report = run_check_live(CHECKLIST, CHECK, output=tmp_path, examples=[example],
                                  concurrency=1)
    assert [e["status"] for e in report] == ["failed"]
    (kept,) = list(root.rglob("intermediates/failure.json"))
    assert "declined to answer" in json.loads(kept.read_text())["error"]
    audit = json.loads((kept.parent / TOOL_AUDIT_FILENAME).read_text())
    assert audit["usage"]["total_cost_usd"] == 0.02 and audit["session"]["concurrency"] == 1
    assert (kept.parent / SKILL_TRACE_FILENAME).is_file()
    assert not (kept.parent.parent / "prediction.json").exists()


def test_a_kept_failure_is_not_rerun_unless_asked(tmp_path: Path, monkeypatch):
    """exp-07: extending a run must not turn a recorded failure into a success."""
    (example,) = _examples(1)
    calls = _answering(monkeypatch, tmp_path)
    leaf = tmp_path / "pinned" / "rep-00" / example / "intermediates"
    leaf.mkdir(parents=True)
    (leaf / "failure.json").write_text('{"error": "declined to answer"}')
    _, report = run_check_live(CHECKLIST, CHECK, output=tmp_path, examples=[example],
                               retry_failed=False)
    assert calls == [] and [e["status"] for e in report] == ["skipped"]
    _, report = run_check_live(CHECKLIST, CHECK, output=tmp_path, examples=[example])
    assert len(calls) == 1 and [e["status"] for e in report] == ["ok"]


NO_NETWORK = ("Claude Code returned an error result: API Error: Can't reach the API server "
              "\u2014 check your internet or DNS (ENOTFOUND) (exit code: 1)")


def test_a_lost_connection_stops_the_run_and_is_never_kept(tmp_path: Path, monkeypatch):
    """exp-07: 99 sessions failed in seconds on a dropped network."""
    examples = _two_examples()
    calls = _failing_with(monkeypatch, NO_NETWORK)
    assert runner.is_connection_error(RuntimeError(NO_NETWORK))
    assert not runner.is_connection_error(RuntimeError("declined to answer within the schema"))
    with pytest.raises(RunAborted):
        run_check_live(CHECKLIST, CHECK, output=tmp_path, examples=examples)
    assert len(calls) == 1


def test_a_transient_failure_is_rerun_even_when_failures_are_kept(tmp_path: Path, monkeypatch):
    (example,) = _examples(1)
    calls = _answering(monkeypatch, tmp_path)
    leaf = tmp_path / "pinned" / "rep-00" / example / "intermediates"
    leaf.mkdir(parents=True)
    (leaf / "failure.json").write_text(json.dumps({"error": NO_NETWORK, "transient": True}))
    _, report = run_check_live(CHECKLIST, CHECK, output=tmp_path, examples=[example],
                               retry_failed=False)
    assert len(calls) == 1 and [e["status"] for e in report] == ["ok"]
