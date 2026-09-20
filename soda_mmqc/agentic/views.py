"""The generated views of a checklist: `dag.yaml` and `README.md`.

Generated and drift-checked rather than hand-maintained, so that the
documentation of a skill graph cannot quietly disagree with the skills. The
banners the generators emit name `python -m soda_mmqc.cli graph`, which is
still the entry point; moving this code does not change how it is invoked.
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import yaml

from soda_mmqc import config, logger
from soda_mmqc.scripts.run import (
    EVALUATION_CONTRACT_FILES,
    owns_evaluation_contracts,
)
from soda_mmqc.agentic.pinning import (
    VERSION_MANIFEST_FILENAME,
    load_version_manifest,
    resolve_skill_set,
    skill_content_hash,
    validate_version_manifest,
)
from soda_mmqc.agentic.skills import (
    Skill,
    invoked_skills,
    load_skills,
    validate_skills,
)

__all__ = [
    "DAG_FILENAME",
    "GENERATED_README_FILENAME",
    "render_dag",
    "render_readme",
    "graph_checklist",
]


DAG_FILENAME = "dag.yaml"

#: Generated. The same picture, for a person.
GENERATED_README_FILENAME = "README.md"


# ---------------------------------------------------------------------------
# Generated graph views
# ---------------------------------------------------------------------------
#
# `dag.yaml` and `README.md` are generated and drift-checked rather than
# hand-written, for one reason: a hand-written picture of a graph is correct
# on the day it is written and silently wrong afterwards, and a silently wrong
# picture is what people reason from. The generator is deliberately a pure
# function of the skills plus the manifest -- no timestamps, no absolute
# paths, no filesystem ordering -- because a drift check that reports noise
# teaches people to ignore it, which is the only way it can fail completely.

_GENERATED_BANNER = (
    "This file is generated. Never hand-edit it: run "
    "`python -m soda_mmqc.cli graph {checklist} --write` instead. "
    "`graph {checklist}` fails when it and the skills disagree."
)


def _graph_view_context(
    checklist: str, checklist_dir: Path
) -> Tuple[Dict[str, Dict[str, Skill]], Dict[str, str], SkillSet]:
    skills = validate_skills(checklist_dir)
    pins = load_version_manifest(checklist_dir)
    validate_version_manifest(skills, pins, checklist_dir)
    return skills, pins, resolve_skill_set(skills, pins)


def render_dag(checklist: str, checklist_dir: Path) -> str:
    """Render ``dag.yaml`` for a checklist.

    Edges come from the **prose**, via :func:`invoked_skills`, not from
    ``requires``. Validation has already asserted the two agree, so the two
    sources give the same answer -- but the prose is what actually runs, and a
    generated picture should be drawn from the thing that runs.
    """
    checklist_dir = Path(checklist_dir)
    skills, pins, skill_set = _graph_view_context(checklist, checklist_dir)
    known = sorted(skills)

    entries = []
    for name in known:
        skill = skills[name][pins[name]]
        entries.append(
            {
                "name": name,
                "version": pins[name],
                "content_hash": skill_content_hash(skill),
                "kind": (
                    "check"
                    if owns_evaluation_contracts(skill.skill_dir)
                    else "shared"
                ),
                "description": skill.description,
                "calls": sorted(invoked_skills(skill, known)),
                "produces": sorted(skill.produces),
            }
        )

    document = {
        "checklist": checklist,
        "skill_set": skill_set.digest,
        "skills": entries,
    }
    banner = _GENERATED_BANNER.format(checklist=checklist)
    body = yaml.safe_dump(
        document, sort_keys=False, default_flow_style=False, allow_unicode=True
    )
    return f"# {banner}\n" + body


def _call_tree(
    name: str,
    skills: Mapping[str, Mapping[str, Skill]],
    pins: Mapping[str, str],
    known: Sequence[str],
    depth: int = 0,
    seen: Optional[Tuple[str, ...]] = None,
) -> List[str]:
    seen = seen or ()
    indent = "  " * depth
    if name in seen:
        return [f"{indent}- `{name}` (already shown above)"]
    lines = [f"{indent}- `{name}`"]
    for callee in sorted(invoked_skills(skills[name][pins[name]], known)):
        lines += _call_tree(
            callee, skills, pins, known, depth + 1, seen + (name,)
        )
    return lines


def render_readme(checklist: str, checklist_dir: Path) -> str:
    """Render the human-readable ``README.md`` for a checklist."""
    checklist_dir = Path(checklist_dir)
    skills, pins, skill_set = _graph_view_context(checklist, checklist_dir)
    known = sorted(skills)
    checks = [
        name for name in known
        if owns_evaluation_contracts(skills[name][pins[name]].skill_dir)
    ]
    shared = [name for name in known if name not in checks]

    lines = [
        f"<!-- {_GENERATED_BANNER.format(checklist=checklist)} -->",
        "",
        f"# `{checklist}`",
        "",
        f"{len(checks)} check(s) and {len(shared)} shared skill(s), pinned by "
        f"[`{VERSION_MANIFEST_FILENAME}`]({VERSION_MANIFEST_FILENAME}).",
        "",
        f"- **SkillSet digest:** `{skill_set.digest}`",
        "",
        "A check is a skill that owns the evaluation contracts "
        f"({', '.join(EVALUATION_CONTRACT_FILES)}). Nothing else "
        "distinguishes a check from a shared skill: the hierarchy below is "
        "carried entirely by what each skill's own prose asks for, never by "
        "where its directory sits.",
        "",
        "## Skills",
        "",
        "| skill | version | kind | description |",
        "| --- | --- | --- | --- |",
    ]
    for name in known:
        skill = skills[name][pins[name]]
        kind = "check" if name in checks else "shared"
        description = skill.description.replace("|", "\\|")
        lines.append(
            f"| `{name}` | {pins[name]} | {kind} | {description} |"
        )

    lines += ["", "## Call graph", ""]
    if shared:
        lines += [
            "Each entry is one check and the skills its prose asks for, "
            "transitively.",
            "",
        ]
    for name in checks:
        lines += _call_tree(name, skills, pins, known)
    unreached = [
        name for name in shared
        if not any(
            name in _joined_tree(check, skills, pins, known) for check in checks
        )
    ]
    if unreached:
        lines += [
            "",
            "### Called by no check",
            "",
            "These are pinned and assembled -- every skill's description "
            "competes in every session -- but no check's prose asks for them "
            "today.",
            "",
        ]
        lines += [f"- `{name}`" for name in unreached]
    return "\n".join(lines) + "\n"


def _joined_tree(
    name: str,
    skills: Mapping[str, Mapping[str, Skill]],
    pins: Mapping[str, str],
    known: Sequence[str],
) -> Set[str]:
    reached: Set[str] = set()
    stack = [name]
    while stack:
        current = stack.pop()
        for callee in invoked_skills(skills[current][pins[current]], known):
            if callee not in reached:
                reached.add(callee)
                stack.append(callee)
    return reached


def graph_checklist(checklist: str, *, write: bool = False) -> int:
    """Drift-check or regenerate a checklist's graph views.

    Metadata only: no example is read and no session is opened, so this is
    cheap enough to run in CI on every checklist on every commit -- which is
    the only way the views stay true.

    Returns:
        ``0`` when the committed views match the skills (or were just
        written), ``1`` when they drift.
    """
    checklist_dir = config.CHECKLIST_DIR / checklist
    if not checklist_dir.is_dir():
        raise FileNotFoundError(f"Checklist not found: {checklist_dir}")

    views = {
        DAG_FILENAME: render_dag(checklist, checklist_dir),
        GENERATED_README_FILENAME: render_readme(checklist, checklist_dir),
    }

    if write:
        for filename, text in views.items():
            (checklist_dir / filename).write_text(text, encoding="utf-8")
        print(
            f"wrote {', '.join(sorted(views))} in {checklist_dir}"
        )
        return 0

    drifted = []
    for filename, expected in sorted(views.items()):
        path = checklist_dir / filename
        actual = path.read_text(encoding="utf-8") if path.is_file() else ""
        if actual != expected:
            drifted.append(filename)
            print(f"--- drift in {path} ---")
            print(
                "".join(
                    difflib.unified_diff(
                        actual.splitlines(keepends=True),
                        expected.splitlines(keepends=True),
                        fromfile=f"{filename} (committed)",
                        tofile=f"{filename} (from the skills)",
                    )
                )
            )

    if drifted:
        print(
            f"{len(drifted)} generated view(s) disagree with the skills. "
            f"Run `python -m soda_mmqc.cli graph {checklist} --write` and "
            "commit the result."
        )
        return 1
    print(f"{checklist}: generated views are in sync with the skills")
    return 0


#: Files that must never reach the runtime. The evaluation contracts are the
#: answer key and the list of other examples; `prompts/` is the legacy asset
#: the skills replace. None of them is an input to a session.
