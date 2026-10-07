"""Walking a benchmark: one session per (example, check), and the predictions.

The harness's whole job here is mechanical -- which examples, which check,
where the output goes. Everything about which skills get called, and in what
order, belongs to the agent.
"""

from __future__ import annotations

import dataclasses

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from soda_mmqc.config import DEFAULT_MODEL
from soda_mmqc import config, logger
from soda_mmqc.config import (
    AGENTIC_DEFAULT_MODEL,
    EVALUATION_DIR,
)
from soda_mmqc.core.examples import EXAMPLE_FACTORY
from soda_mmqc.agentic.pinning import (
    validate_version_manifest,
    SkillSet,
    checklist_pins,
    expand_skill_sets,
    load_model_defaults,
)
from soda_mmqc.agentic.runtime import (
    ASSEMBLY_CLOSURE,
    effective_session_options,
    RuntimeLayout,
    _leaf_schema,
    assemble_runtime,
    runtime_skill_set,
)
from soda_mmqc.agentic.session import (
    compare_declared_and_observed,
    INTERMEDIATES_DIRNAME,
    runtime_session,
    PREDICTION_FILENAME,
    SKILL_SET_FILENAME,
    SKILL_TRACE_FILENAME,
    TOOL_AUDIT_FILENAME,
    ToolAuditLog,
    _openai_session_client,
    _run_agent_session,
    interactive_approver,
)
from soda_mmqc.agentic.skills import (
    Skill,
    load_skills,
    _read_json,
    invoked_skills,
    resolve_check_dir,
    select_versions,
    validate_skills,
)
from soda_mmqc.config import list_checks

#: Top-level key under which scored records are stored in `analysis.json`.
DEFAULT_RUN_LABEL = "agentic"

__all__ = [
    "run_check_mock",
    "run_check_live",
    "RunAborted",
    "default_predictions_dir",
    "resolve_model",
    "PREDICTION_FILENAME",
    "DEFAULT_RUN_LABEL",
    "INTERMEDIATES_DIRNAME",
]


class RunAborted(RuntimeError):
    """A session failed for a reason every later session would share.

    An invalid or revoked API key, or an account out of credit, fails each
    session the same way, minutes apiece after the SDK's retries. Recording
    those as per-example failures and carrying on turned an unattended run
    into hours of nothing: exp-04's first full run, 2026-10-05, spent over an
    hour failing 25 sessions on a revoked key before it was noticed.

    ``report`` holds the entries up to and including the failure that ended
    the run; every prediction written before it stays, so rerunning resumes.
    """

    def __init__(self, message: str, report: List[Dict[str, Any]]):
        super().__init__(message)
        self.report = report


#: Errors about the account rather than the example: authentication,
#: permission, credit. A rate limit or an overloaded API is not here -- it
#: passes, and a later session may succeed.
_ACCOUNT_ERROR = re.compile(
    r"\b40[13]\b|failed to authenticate|invalid x-api-key|api key is invalid"
    r"|authentication_error|permission_error|credit balance|billing",
    re.IGNORECASE,
)


def is_account_error(exc: BaseException) -> bool:
    """Whether a session's failure would recur in every later session."""
    return bool(_ACCOUNT_ERROR.search(str(exc)))


def default_predictions_dir(checklist: str, check: str, model: str) -> Path:
    """The root a run writes under, when no ``--output`` is given.

    A root is a directory whose children are arms: the harness appends
    ``<arm>/rep-NN/<example>/`` beneath this. There is no ``predictions``
    segment, because the leaf holds its ``analysis.json`` too -- and
    without it a production root has the same shape as an experiment's
    ``experiments/runs/<exp>/<check>/``, so one walker serves both.
    """
    return EVALUATION_DIR / checklist / check / model


def _write_prediction(
    predictions_dir: Path,
    example: str,
    prediction: Dict[str, Any],
    trace: List[Dict[str, Any]],
    skill_set: Optional[SkillSet] = None,
    arm: str = "pinned",
    replicate: int = 0,
    assembled: Optional[SkillSet] = None,
    assembly: Optional[str] = None,
) -> Path:
    """Write one example's leaf JSON plus its trace sidecar."""
    example_dir = predictions_dir / example
    example_dir.mkdir(parents=True, exist_ok=True)

    prediction_path = example_dir / PREDICTION_FILENAME
    prediction_path.write_text(
        json.dumps(prediction, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    intermediates = example_dir / INTERMEDIATES_DIRNAME
    intermediates.mkdir(exist_ok=True)
    if skill_set is not None:
        (intermediates / SKILL_SET_FILENAME).write_text(
            json.dumps(
                {
                    "digest": skill_set.digest,
                    # Which configuration and which sample, recorded rather
                    # than inferred: the path says the same thing, but a path
                    # can be moved and a sidecar travels with the prediction.
                    "arm": arm,
                    "replicate": replicate,
                    "skills": [
                        dataclasses.asdict(e)
                        for e in sorted(
                            skill_set.entries, key=lambda e: e.name
                        )
                    ],
                    # `skills` is what the arm pinned; this is what the
                    # session actually held. Under closure assembly they
                    # differ, and only the second says what the model saw.
                    **(
                        {
                            "assembly": assembly,
                            "assembled": sorted(
                                e.name for e in assembled.entries
                            ),
                            "assembled_digest": assembled.digest,
                        }
                        if assembled is not None else {}
                    ),
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
    (intermediates / SKILL_TRACE_FILENAME).write_text(
        json.dumps(trace, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return prediction_path


def _mock_trace(checklist_dir: Path, check: str) -> List[Dict[str, Any]]:
    """A deterministic stand-in for the trace a real session would leave.

    It reports the hops the entry point *declares*, which is what a correctly
    behaving session would produce. That makes `--mock` exercise the whole
    path -- including the declared-versus-observed comparison -- without
    credentials.

    It is explicitly **not** evidence that discovery works. Mock traces are
    generated from the frontmatter, so comparing them against the frontmatter
    is circular; only a live run answers that question, which is what gate 4D
    is for. `source: "mock"` marks every entry so the two can never be
    confused in a report.
    """
    skills = load_skills(checklist_dir)
    selected = select_versions(skills, checklist_pins(checklist_dir))
    entry = selected[check]
    return [
        {
            "skill": name,
            "version": selected[name].version,
            "tool_input": {"name": name},
            "tool_use_id": f"mock-{index:04d}",
            "timestamp": None,
            "source": "mock",
        }
        for index, name in enumerate(entry.requires)
    ]


def _as_prediction(gold: Mapping[str, Any], schema: Mapping[str, Any]) -> Dict[str, Any]:
    """Project a gold record onto the fields the output schema declares.

    Gold files carry curation metadata -- ``updated_at`` and friends -- that
    the leaf schema does not allow, because the schema describes what a
    *session* must produce, not what the curation UI stores. Writing gold
    verbatim as a mock prediction therefore produces output that a real
    session would be rejected for, which would make ``--mock`` exercise a
    path the live runner cannot take.

    So the mock writes the contracted fields only. The stripped keys are
    metadata by construction; nothing scored is lost, because the evaluator
    reads the same gold through its own path.
    """
    allowed = set(schema.get("properties") or {})
    if not allowed:
        return dict(gold)
    return {key: value for key, value in gold.items() if key in allowed}


def run_check_mock(
    checklist: str,
    check: str,
    *,
    output: Optional[Path] = None,
    model: str = DEFAULT_MODEL,
    examples: Optional[Sequence[str]] = None,
) -> Path:
    """Write each benchmark example's gold as its prediction, offline.

    This is the credential-free path: it opens no session, contacts no
    provider, and validates nothing it has not been given. Its purpose is to
    let CI exercise prediction layout, trace layout and scoring end to end.

    **It is genuinely offline**, which the legacy ``evaluate --mock`` is not:
    that path validates the model against the provider first and so aborts
    without an API key. Milestone 1's gate 1B recorded that as debt precisely
    because it makes a credential-free gate impossible; this implementation
    does not repeat it.

    Returns:
        The predictions directory.
    """
    check_dir = resolve_check_dir(checklist, check)
    checklist_dir = check_dir.parent
    benchmark = _read_json(check_dir / "benchmark.json")
    schema = _read_json(check_dir / "schema.json")["format"]["schema"]

    check_name = benchmark.get("name", check)
    example_class = benchmark["example_class"]
    wanted = list(examples) if examples else list(benchmark.get("examples") or [])
    if not wanted:
        raise ValueError(f"No examples to run for {check_name}")

    # The same shape as a live run, with no exception for the fact that mock
    # assembles no skills: it is scored by the same command, and one layout
    # means one reader.
    predictions_dir = (
        Path(output or default_predictions_dir(checklist, check, model))
        / "pinned" / "rep-00"
    )
    trace = _mock_trace(checklist_dir, check)

    written = 0
    for relative_source_path in wanted:
        example = EXAMPLE_FACTORY.create(relative_source_path, example_class)
        expected = example.get_expected_output(check_name)
        if not expected:
            logger.warning(
                "No expected output for %s; skipping", relative_source_path
            )
            continue
        _write_prediction(
            predictions_dir,
            relative_source_path,
            _as_prediction(expected, schema),
            trace,
        )
        written += 1

    if not written:
        raise ValueError(
            f"No gold found for any example of {check_name}; nothing written"
        )
    logger.info(
        "Wrote %d mock prediction(s) to %s", written, predictions_dir
    )
    return predictions_dir


def resolve_model(
    checklist_dir: Path, provider: str, model: Optional[str] = None
) -> str:
    """Pick the model: the caller's choice, the checklist default, then ours.

    The checklist default sits in the middle deliberately. A checklist knows
    which model its skills were written and scored against; the runner's
    constant knows nothing except which provider it is talking to.
    """
    if model:
        return model
    return (
        load_model_defaults(checklist_dir).model_for(provider)
        or AGENTIC_DEFAULT_MODEL
    )


def run_check_live(
    checklist: str,
    check: str,
    *,
    output: Optional[Path] = None,
    model: Optional[str] = None,
    examples: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
    keep_runtime: bool = False,
    approve_tools: bool = False,
    provider: str = "openai",
    unpin: Optional[Mapping[str, Optional[Sequence[str]]]] = None,
    replicates: int = 1,
    force: bool = False,
    assembly: str = ASSEMBLY_CLOSURE,
    concurrency: int = 1,
) -> Tuple[Path, List[Dict[str, Any]]]:
    """Run one real session per example, for each selected SkillSet.

    One sealed runtime and one session per example, assembled fresh and
    removed afterwards unless ``keep_runtime``. A failure on one example is
    recorded and the run continues: a single malformed output should not cost
    the whole batch, and the failures are as interesting as the successes.

    Versions come from the checklist's ``version-manifest.yaml``. ``unpin``
    varies one or more of those pins, producing one SkillSet per combination;
    each gets its own arm directory named after what it changed, so two
    versions of one skill can be scored against the same gold with the same
    shared ``eval-manifest.json``.

    ``assembly`` is ``"closure"`` by default: each session holds the entry
    point and what its pinned prose reaches, and nothing else. ``"all"``
    assembles every skill of the checklist, as runs before exp-03 did.

    Every run writes ``<root>/<arm>/rep-NN/<example>/``, with no exception for
    a single arm or a single replicate: one shape means one reader, and a run
    that later wants replicates never has to relocate the one it has.

    ``concurrency`` is how many sessions run at once. 1 -- the default -- runs
    them one after another, as every run before 2026-10-07 did. Above 1,
    sessions run in a pool of that many workers; the report keeps the
    sequential order. Each session records the concurrency it ran at in its
    ``tool_audit.json``, because wall time and prompt-cache hits depend on it.

    Returns:
        ``(run root, per-example report)``. The root holds one directory per
        arm, each holding one per replicate; scoring is pointed at a leaf.
    """
    if replicates < 1:
        raise ValueError(f"replicates must be at least one, got {replicates}")
    if concurrency < 1:
        raise ValueError(f"concurrency must be at least one, got {concurrency}")
    if approve_tools and concurrency > 1:
        # The approver asks at the terminal, one call at a time; concurrent
        # sessions would interleave their questions.
        raise ValueError("approve_tools needs concurrency 1")

    check_dir = resolve_check_dir(checklist, check)
    checklist_dir = check_dir.parent
    benchmark = _read_json(check_dir / "benchmark.json")
    check_name = benchmark.get("name", check)

    wanted = list(examples) if examples else list(benchmark.get("examples") or [])
    if limit is not None:
        wanted = wanted[:limit]
    if not wanted:
        raise ValueError(f"No examples to run for {check_name}")

    skills = validate_skills(checklist_dir)
    pins = checklist_pins(checklist_dir)
    if pins is None:
        pins = {name: s.version for name, s in select_versions(skills).items()}
    else:
        validate_version_manifest(skills, pins, checklist_dir)

    skill_sets = expand_skill_sets(skills, pins, dict(unpin or {}))
    model = resolve_model(checklist_dir, provider, model)
    defaults = load_model_defaults(checklist_dir).session
    root_dir = Path(output or default_predictions_dir(checklist, check, model))
    approver = interactive_approver() if approve_tools else None

    # One unit per session, in the order a sequential run takes them. Every
    # axis is a directory, with no exception for the degenerate case: a run
    # that later wants replicates must not have to relocate the one it has.
    units = [
        (skill_set, skill_set.label(pins), skill_set.pins, replicate,
         root_dir / skill_set.label(pins) / f"rep-{replicate:02d}", example)
        for skill_set in skill_sets
        for replicate in range(replicates)
        for example in wanted
    ]

    def run_one(unit) -> Dict[str, Any]:
        """One session: skipped if done, else run, recorded, never raised."""
        skill_set, label, versions, replicate, predictions_dir, relative_source_path = unit
        entry: Dict[str, Any] = {
            "example": relative_source_path,
            "skill_set": skill_set.digest,
            "label": label,
            "replicate": replicate,
        }
        done = (
            predictions_dir / relative_source_path / PREDICTION_FILENAME
        )
        if done.is_file() and not force:
            # Resumability is not a convenience at this size: a full
            # experiment is thousands of sessions and hours long, so an
            # interruption must cost what it interrupted and not the
            # whole run. `force` is how a deliberate rerun says so.
            logger.info(
                "Skipping %s on %s [%s rep-%02d]: already has a "
                "prediction",
                check_name, relative_source_path, label, replicate,
            )
            entry["status"] = "skipped"
            return entry
        logger.info(
            "Running %s on %s [%s]", check_name, relative_source_path, label
        )
        try:
            with runtime_session(
                checklist, check, relative_source_path,
                keep=keep_runtime, pins=versions, assembly=assembly,
            ) as layout:
                options = effective_session_options(
                    layout, skills, defaults=defaults
                )
                options["model"] = model
                client = (
                    _openai_session_client(layout, model)
                    if provider == "openai"
                    else None
                )
                prediction, recorder, audit = asyncio.run(
                    _run_agent_session(
                        layout,
                        versions=versions,
                        approver=approver,
                        options=options,
                        client=client,
                    )
                )
                # The file-production contract is gone with the write
                # tool: nothing the session does touches the filesystem.
                # What that check protected -- a shared skill that was
                # declared but never fired -- is answered by the hop
                # trace below, which reads the session's own tool calls
                # and needs no artifact to exist.
                entry["hops"] = compare_declared_and_observed(
                    checklist_dir, check, recorder.invoked, pins=versions
                )
                entry["tools"] = audit.summary()
                entry["reported_tools"] = audit.session_info.get("tools")
                # What this session spent, so a caller can total a run
                # without reopening every sidecar.
                if audit.usage:
                    entry["usage"] = dict(audit.usage)
                _write_prediction(
                    predictions_dir,
                    relative_source_path,
                    prediction,
                    recorder.entries,
                    skill_set,
                    arm=label,
                    replicate=replicate,
                    assembled=runtime_skill_set(layout, versions),
                    assembly=assembly,
                )
                # How many sessions ran at once: wall time and prompt-cache
                # hits depend on it, so time and cost are comparable only
                # between runs that share it.
                audit.note_session({**audit.session_info, "concurrency": concurrency})
                _copy_sidecar(
                    audit.path,
                    predictions_dir / relative_source_path
                    / INTERMEDIATES_DIRNAME / TOOL_AUDIT_FILENAME,
                )
                entry["status"] = "ok"
        except Exception as exc:  # noqa: BLE001 - one example must not end the run
            logger.error("%s failed: %s", relative_source_path, exc)
            entry["status"] = "failed"
            entry["error"] = str(exc)
            # ...but an account that cannot run this session cannot run the
            # next one either; the caller stops the run on this flag.
            entry["account_error"] = is_account_error(exc)
        return entry

    def stop(entry: Dict[str, Any], done: List[Dict[str, Any]]) -> None:
        logger.error(
            "Stopping the run: %s is an account error, and every later session "
            "would fail the same way. Predictions written so far are kept; "
            "rerun to resume.",
            entry["example"],
        )
        raise RunAborted(entry.get("error", ""), done)

    report: List[Dict[str, Any]] = []
    if concurrency == 1:
        for unit in units:
            entry = run_one(unit)
            report.append(entry)
            if entry.pop("account_error", False):
                stop(entry, report)
    else:
        # Sessions are independent -- each assembles its own runtime in its own
        # temporary directory and writes its own prediction -- so several can
        # run at once. Each worker thread runs its session's event loop with
        # asyncio.run, exactly as the sequential path does.
        results: Dict[int, Dict[str, Any]] = {}
        aborted: Optional[Dict[str, Any]] = None
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(run_one, unit): i for i, unit in enumerate(units)}
            for future in as_completed(futures):
                if future.cancelled():
                    # Dropped after an account error: it never ran.
                    continue
                entry = future.result()
                results[futures[future]] = entry
                if entry.pop("account_error", False) and aborted is None:
                    aborted = entry
                    # Sessions not yet started are dropped; those running
                    # finish and keep what they write.
                    for pending in futures:
                        pending.cancel()
        report = [results[i] for i in sorted(results)]
        if aborted is not None:
            stop(aborted, report)

    ok = sum(1 for e in report if e["status"] == "ok")
    logger.info(
        "Completed %d/%d session(s) over %d SkillSet(s); predictions in %s",
        ok, len(report), len(skill_sets), root_dir,
    )
    return root_dir, report








def _copy_sidecar(source: Path, destination: Path) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
