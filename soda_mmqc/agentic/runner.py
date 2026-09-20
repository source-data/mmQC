"""Walking a benchmark: one session per (example, check), and the predictions.

The harness's whole job here is mechanical -- which examples, which check,
where the output goes. Everything about which skills get called, and in what
order, belongs to the agent.
"""

from __future__ import annotations

import dataclasses

import asyncio
import json
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
    validate_intermediates,
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
from soda_mmqc.scripts.run import list_checks

#: Top-level key under which scored records are stored in `analysis.json`.
DEFAULT_RUN_LABEL = "agentic"

__all__ = [
    "run_check_mock",
    "run_check_live",
    "run_checklist_live",
    "default_predictions_dir",
    "resolve_model",
    "PREDICTION_FILENAME",
    "DEFAULT_RUN_LABEL",
    "INTERMEDIATES_DIRNAME",
]


def default_predictions_dir(checklist: str, check: str, model: str) -> Path:
    """Where a run writes its predictions, mirroring the analysis layout."""
    return EVALUATION_DIR / checklist / check / model / "predictions"


def _write_prediction(
    predictions_dir: Path,
    example: str,
    prediction: Dict[str, Any],
    trace: List[Dict[str, Any]],
    skill_set: Optional[SkillSet] = None,
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
                    "skills": [
                        dataclasses.asdict(e)
                        for e in sorted(
                            skill_set.entries, key=lambda e: e.name
                        )
                    ],
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

    predictions_dir = Path(
        output or default_predictions_dir(checklist, check, model)
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
    seed_intermediates: Optional[Mapping[str, Mapping[str, Any]]] = None,
    shared_skill_denials: Optional[Mapping[str, Sequence[str]]] = None,
) -> Tuple[Path, List[Dict[str, Any]]]:
    """Run one real session per example, for each selected SkillSet.

    One sealed runtime and one session per example, assembled fresh and
    removed afterwards unless ``keep_runtime``. A failure on one example is
    recorded and the run continues: a single malformed output should not cost
    the whole batch, and the failures are as interesting as the successes.

    Versions come from the checklist's ``version-manifest.yaml``. ``unpin``
    varies one or more of those pins, producing one SkillSet per combination;
    each gets its own predictions subdirectory named after what it changed, so
    two versions of one skill can be scored against the same gold with the
    same shared ``eval-manifest.json``. With no ``unpin`` there is exactly one
    SkillSet and the output layout is unchanged.

    Returns:
        ``(predictions directory, per-example report)``. With more than one
        SkillSet the directory is the parent holding one subdirectory per set.
    """
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

    report: List[Dict[str, Any]] = []
    for skill_set in skill_sets:
        label = skill_set.label(pins)
        # Keyed on the label, never on how many sets there happen to be.
        # `--unpin X --versions v2` expands to exactly one set, and writing
        # that variant into the baseline directory would silently overwrite
        # the pinned run's predictions with a different SkillSet's answers --
        # the one outcome a version comparison must never produce.
        predictions_dir = (
            root_dir if label == "pinned" else root_dir / label
        )
        versions = skill_set.pins
        for relative_source_path in wanted:
            logger.info(
                "Running %s on %s [%s]", check_name, relative_source_path, label
            )
            entry: Dict[str, Any] = {
                "example": relative_source_path,
                "skill_set": skill_set.digest,
                "label": label,
            }
            try:
                with runtime_session(
                    checklist, check, relative_source_path,
                    keep=keep_runtime, pins=versions,
                ) as layout:
                    seeded = dict((seed_intermediates or {}).get(relative_source_path, {}))
                    for name, payload in seeded.items():
                        path = layout.artifacts_root / f"{name}.json"
                        path.write_text(
                            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8",
                        )
                    options = effective_session_options(
                        layout, skills, defaults=defaults
                    )
                    options["model"] = model
                    denied_shared = set(
                        (shared_skill_denials or {}).get(relative_source_path, ())
                    )
                    client = (
                        _openai_session_client(layout, model)
                        if provider == "openai"
                        else None
                    )
                    session_kwargs: Dict[str, Any] = {
                        "versions": versions,
                        "approver": approver,
                        "options": options,
                        "client": client,
                    }
                    if denied_shared:
                        session_kwargs["denied_shared_skills"] = denied_shared
                    prediction, recorder, audit = asyncio.run(
                        _run_agent_session(
                            layout,
                            **session_kwargs,
                        )
                    )
                    # The file-production contract is gone with the write
                    # tool: nothing the session does touches the filesystem.
                    # What that check protected -- a shared skill that was
                    # declared but never fired -- is answered by the hop
                    # trace below, which reads the session's own tool calls
                    # and needs no artifact to exist.
                    found_intermediates, invalid = validate_intermediates(
                        layout, skills, pins=versions, strict=False
                    )
                    entry["intermediates"] = sorted(found_intermediates)
                    if invalid:
                        raise ValueError(
                            "Session produced invalid intermediate artifact(s): "
                            + "; ".join(invalid)
                        )
                    entry["hops"] = compare_declared_and_observed(
                        checklist_dir, check, recorder.invoked, pins=versions
                    )
                    entry["tools"] = audit.summary()
                    entry["reported_tools"] = audit.session_info.get("tools")
                    _write_prediction(
                        predictions_dir,
                        relative_source_path,
                        prediction,
                        recorder.entries,
                        skill_set,
                    )
                    for name, artifact_path in found_intermediates.items():
                        _copy_sidecar(
                            artifact_path,
                            predictions_dir
                            / relative_source_path
                            / INTERMEDIATES_DIRNAME
                            / f"{name}.json",
                        )
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
            report.append(entry)

    ok = sum(1 for e in report if e["status"] == "ok")
    logger.info(
        "Completed %d/%d session(s) over %d SkillSet(s); predictions in %s",
        ok, len(report), len(skill_sets), root_dir,
    )
    return root_dir, report


def _required_shared_skills(
    check_name: str, selected: Mapping[str, Skill]
) -> Set[str]:
    """Shared skills reachable from `check_name` via declared requirements."""
    entry = selected.get(check_name)
    if entry is None:
        return set()
    pending = list(entry.requires)
    seen: Set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        skill = selected.get(name)
        if skill is None:
            continue
        seen.add(name)
        pending.extend(skill.requires)
    return seen


def _expand_example_selectors(
    benchmark_examples: Sequence[str], selectors: Optional[Sequence[str]]
) -> Optional[List[str]]:
    """Expand doc-level selectors to concrete benchmark example paths."""
    if not selectors:
        return None
    expanded: List[str] = []
    seen: Set[str] = set()
    for selector in selectors:
        selector = selector.strip()
        if not selector:
            continue
        matched = [
            example
            for example in benchmark_examples
            if example == selector or example.startswith(f"{selector}/")
        ]
        for example in matched:
            if example not in seen:
                seen.add(example)
                expanded.append(example)
    return expanded


def run_checklist_live(
    checklist: str,
    *,
    output: Optional[Path] = None,
    model: Optional[str] = None,
    examples: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
    keep_runtime: bool = False,
    approve_tools: bool = False,
    provider: str = "openai",
    unpin: Optional[Mapping[str, Optional[Sequence[str]]]] = None,
) -> Tuple[Path, List[Dict[str, Any]]]:
    """Run all checks in a checklist, reusing shared intermediates per example."""
    if unpin:
        raise ValueError("--all-checks does not support --unpin")

    checklist_dir = config.CHECKLIST_DIR / checklist
    if not checklist_dir.is_dir():
        raise FileNotFoundError(f"Checklist not found: {checklist_dir}")

    checks = sorted(list_checks(checklist_dir))
    if not checks:
        raise ValueError(f"No checks found in checklist: {checklist}")

    selected = select_versions(validate_skills(checklist_dir), checklist_pins(checklist_dir))
    run_model = resolve_model(checklist_dir, provider, model)
    root_dir = Path(
        output
        or EVALUATION_DIR / checklist / "__all-checks__" / run_model / "predictions"
    )

    cache: Dict[str, Dict[str, Any]] = {}
    denied: Dict[str, Set[str]] = {}
    combined: List[Dict[str, Any]] = []
    shared_by_check = {name: _required_shared_skills(name, selected) for name in checks}
    producers: Dict[str, Set[str]] = {
        name: set(selected[name].produces)
        for name in selected
        if selected[name].produces
    }

    for check in checks:
        benchmark = _read_json(checklist_dir / check / "benchmark.json")
        check_examples = _expand_example_selectors(
            benchmark.get("examples") or [],
            examples,
        )
        check_output = root_dir / check
        _, report = run_check_live(
            checklist,
            check,
            output=check_output,
            model=model,
            examples=check_examples,
            limit=limit,
            keep_runtime=keep_runtime,
            approve_tools=approve_tools,
            provider=provider,
            unpin=unpin,
            seed_intermediates=cache,
            shared_skill_denials={k: sorted(v) for k, v in denied.items()},
        )
        for entry in report:
            item = dict(entry)
            item["check"] = check
            combined.append(item)
            if item.get("status") != "ok":
                continue
            example = item["example"]
            produced = set(item.get("intermediates") or ())
            for skill_name in shared_by_check.get(check, set()):
                artifacts = producers.get(skill_name, set())
                available = sorted(artifacts & produced)
                if not available:
                    continue
                denied.setdefault(example, set()).add(skill_name)
                for artifact_name in available:
                    artifact_path = (
                        check_output
                        / example
                        / INTERMEDIATES_DIRNAME
                        / f"{artifact_name}.json"
                    )
                    if artifact_path.is_file():
                        cache.setdefault(example, {})[artifact_name] = _read_json(
                            artifact_path
                        )
    return root_dir, combined


def _copy_sidecar(source: Path, destination: Path) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
