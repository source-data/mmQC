"""The skill model: reading `SKILL.md`, and the graph its frontmatter declares.

A skill's identity is its frontmatter ``name``, never its directory, so the
graph is path-independent: renaming a skill's directory, moving it under its
caller or burying it three levels deep leaves the resolved graph identical.

`CHECKLIST_DIR` is read from :mod:`soda_mmqc.config` at call time rather than
bound at import. The agentic code is spread over several modules now, and a
bound copy per module would mean a caller redirecting one of them and silently
not the others.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import json

import yaml

from soda_mmqc import config
from soda_mmqc.scripts.run import (
    EVALUATION_CONTRACT_FILES,
    list_checks,
    owns_evaluation_contracts,
)

__all__ = [
    "_read_json",
    "SKILL_FILENAME",
    "SKILL_TOOL",
    "Skill",
    "load_skill",
    "load_skills",
    "build_graph",
    "find_cycle",
    "invoked_skills",
    "validate_skills",
    "select_versions",
    "resolve_check_dir",
]


#: Name of a skill's instruction file. One per version directory.
SKILL_FILENAME = "SKILL.md"

#: The tool a skill's prose tells the agent to use when calling a sub-skill.
SKILL_TOOL = "Skill"

#: A version directory is named ``v`` followed by digits. Only ``SKILL.md`` is
#: versioned; the evaluation contracts stay at the skill level so that two
#: versions of one skill remain comparable.
_VERSION_DIR = re.compile(r"^v\d+$")

#: Frontmatter is a YAML block delimited by ``---`` lines at the top of the
#: file, in the convention the Agent SDK uses for skills.
_FRONTMATTER = re.compile(r"\A---\r?\n(?P<yaml>.*?)\r?\n---[ \t]*\r?\n?(?P<body>.*)\Z", re.DOTALL)

#: Frontmatter keys that hold a list of names.
_LIST_KEYS = ("requires", "produces", "needs")


def resolve_check_dir(checklist: str, check: str) -> Path:
    """Return the directory of ``check`` within ``checklist``.

    Raises:
        FileNotFoundError: If the checklist or the check directory is absent.
        ValueError: If the directory exists but is not a check, i.e. it does
            not own the evaluation contracts (a shared skill, for instance).
    """
    checklist_dir = config.CHECKLIST_DIR / checklist
    if not checklist_dir.is_dir():
        raise FileNotFoundError(f"Checklist not found: {checklist_dir}")

    check_dir = checklist_dir / check
    if not check_dir.is_dir():
        known = ", ".join(sorted(list_checks(checklist_dir))) or "none"
        raise FileNotFoundError(
            f"Check not found: {check_dir}. Known checks: {known}"
        )
    if not owns_evaluation_contracts(check_dir):
        raise ValueError(
            f"{check_dir} is not a check: it does not own "
            f"{' and '.join(EVALUATION_CONTRACT_FILES)}. Shared skills sit "
            "beside the checks but cannot be scored."
        )
    return check_dir

@dataclass(frozen=True)
class Skill:
    """One version of one skill, as read from a ``SKILL.md`` file.

    ``name`` comes from the frontmatter, never from the directory the file
    sits in. That is deliberate: the hierarchy is carried by skill-to-skill
    calls, not by the filesystem, so moving or renaming a skill directory must
    leave the resolved graph untouched.
    """

    name: str
    version: str
    path: Path
    description: str
    body: str
    requires: Tuple[str, ...] = ()
    produces: Tuple[str, ...] = ()
    needs: Tuple[str, ...] = ()

    @property
    def directory(self) -> Path:
        """Directory holding this version's ``SKILL.md``."""
        return self.path.parent

    @property
    def skill_dir(self) -> Path:
        """Directory holding every version of this skill.

        This is also where the shared, unversioned assets live -- the runtime
        ``schema.json`` and, for a leaf, the evaluation contracts.
        """
        return self.path.parent.parent


def load_skill(path: Path) -> Skill:
    """Read one ``SKILL.md`` file into a :class:`Skill`.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the frontmatter is missing, unparseable, or does not
            carry a usable ``name`` and ``description``; if the body is empty;
            or if the version directory is not named ``vN``. Every message
            names the offending file.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Skill file not found: {path}")

    version = path.parent.name
    if not _VERSION_DIR.match(version):
        raise ValueError(
            f"{path}: a skill version directory must be named 'v' followed by "
            f"digits (v1, v2, ...), got {version!r}"
        )

    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if match is None:
        raise ValueError(
            f"{path}: no YAML frontmatter. A SKILL.md must open with a '---' "
            "line, the frontmatter, and a closing '---' line"
        )

    try:
        front = yaml.safe_load(match.group("yaml"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: frontmatter is not valid YAML: {exc}") from exc

    if front is None:
        front = {}
    if not isinstance(front, dict):
        raise ValueError(
            f"{path}: frontmatter must be a mapping, got "
            f"{type(front).__name__}"
        )

    name = _required_string(front, "name", path)
    description = _required_string(front, "description", path)
    body = match.group("body").strip()
    if not body:
        raise ValueError(f"{path}: the skill body is empty")

    lists = {key: _name_list(front, key, path) for key in _LIST_KEYS}
    return Skill(
        name=name,
        version=version,
        path=path,
        description=description,
        body=body,
        **lists,
    )


def _required_string(front: Mapping[str, Any], key: str, path: Path) -> str:
    value = front.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{path}: frontmatter key {key!r} must be a non-empty string"
        )
    return " ".join(value.split())


def _name_list(front: Mapping[str, Any], key: str, path: Path) -> Tuple[str, ...]:
    value = front.get(key)
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(
            f"{path}: frontmatter key {key!r} must be a list of non-empty "
            "names"
        )
    names = tuple(item.strip() for item in value)
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ValueError(
            f"{path}: frontmatter key {key!r} lists {', '.join(duplicates)} "
            "more than once"
        )
    return names


def load_skills(checklist_dir: Path) -> Dict[str, Dict[str, Skill]]:
    """Load every skill of a checklist, keyed by skill name and version.

    Discovery walks the checklist directory for ``SKILL.md`` files and takes
    each skill's identity from its frontmatter, so the returned mapping is
    independent of where the directories sit.

    Raises:
        FileNotFoundError: If ``checklist_dir`` is not a directory.
        ValueError: If a skill file is malformed, or if two files declare the
            same name and version.
    """
    checklist_dir = Path(checklist_dir)
    if not checklist_dir.is_dir():
        raise FileNotFoundError(f"Checklist not found: {checklist_dir}")

    skills: Dict[str, Dict[str, Skill]] = {}
    for skill_file in sorted(checklist_dir.rglob(SKILL_FILENAME)):
        skill = load_skill(skill_file)
        versions = skills.setdefault(skill.name, {})
        if skill.version in versions:
            first, second = sorted(
                [versions[skill.version].path, skill_file]
            )
            raise ValueError(
                f"Two files declare skill {skill.name!r} version "
                f"{skill.version!r}: {first} and {second}. A skill's identity "
                "comes from its frontmatter, not its directory, so renaming "
                "one of the directories does not resolve this -- change one "
                "file's `name`, or delete it"
            )
        versions[skill.version] = skill
    return skills


def build_graph(
    skills: Mapping[str, Mapping[str, Skill]]
) -> Dict[str, Set[str]]:
    """Resolve the skill graph, as declared by ``requires``.

    Edges are keyed by skill *name*, unioned over that skill's versions --
    version pinning is Milestone 6's job, and a cycle that exists in any
    version is a cycle worth refusing.
    """
    graph: Dict[str, Set[str]] = {}
    for name, versions in skills.items():
        edges = graph.setdefault(name, set())
        for skill in versions.values():
            edges.update(skill.requires)
    return graph


def find_cycle(graph: Mapping[str, Set[str]]) -> Optional[List[str]]:
    """Return one cycle in ``graph`` as a list of names, or None if acyclic.

    The returned path starts and ends with the same name, so it reads as the
    loop it is.
    """
    visiting: Set[str] = set()
    done: Set[str] = set()
    stack: List[str] = []

    def walk(node: str) -> Optional[List[str]]:
        if node in done:
            return None
        if node in visiting:
            start = stack.index(node)
            return stack[start:] + [node]
        visiting.add(node)
        stack.append(node)
        for neighbour in sorted(graph.get(node, ())):
            cycle = walk(neighbour)
            if cycle is not None:
                return cycle
        stack.pop()
        visiting.discard(node)
        done.add(node)
        return None

    for node in sorted(graph):
        cycle = walk(node)
        if cycle is not None:
            return cycle
    return None


def invoked_skills(skill: Skill, known_names: Sequence[str]) -> Set[str]:
    """Return the known skill names that ``skill``'s prose mentions.

    Prose is what actually executes -- a sentence telling the agent to call
    another skill with the ``Skill`` tool -- so this is the observed half of
    the graph, against which the declared ``requires`` is checked. A skill
    mentioning its own name does not count as invoking itself.
    """
    return {
        name
        for name in known_names
        if name != skill.name and _mentions(skill.body, name)
    }


def _mentions(text: str, name: str) -> bool:
    # Hyphens are part of a skill name, so a plain word boundary would match
    # 'identify-panels' inside 'identify-panels-v2'.
    pattern = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")
    return pattern.search(text) is not None


#: A markdown list item starts a new prose block even without a blank line
#: before it, so a leaf that lists its hops as bullets is checked per hop.
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _prose_blocks(body: str) -> List[str]:
    """Split a skill body into the units a sub-skill call has to fit inside.

    A block is a paragraph, except that each markdown list item is its own
    block. Line wrapping inside a block is ignored, so an instruction that
    wraps across two source lines is still one block.

    The unit matters because "does the prose actually ask the agent to call
    this skill?" is a question about one requirement, not about the file. A
    leaf with two requirements must instruct the agent twice; a single
    ``Skill`` mention somewhere else in the file does not vouch for both.
    """
    blocks: List[str] = []
    for paragraph in re.split(r"\n\s*\n", body):
        current: List[str] = []
        for line in paragraph.splitlines():
            if _LIST_ITEM.match(line) and current:
                blocks.append(" ".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append(" ".join(current))
    return [block for block in blocks if block.strip()]


def _without_self_edges(graph: Mapping[str, Set[str]]) -> Dict[str, Set[str]]:
    # A skill that requires itself is a cycle, but it already gets its own,
    # clearer message. Reporting it twice makes the shorter message harder to
    # find, so cycle detection ignores self-edges.
    return {node: edges - {node} for node, edges in graph.items()}


def validate_skills(checklist_dir: Path) -> Dict[str, Dict[str, Skill]]:
    """Load a checklist's skills and check that its graph is consistent.

    Four things are asserted, and every failure names the offending file:

    * every name in ``requires`` is a skill of this checklist, and is not the
      skill itself;
    * the graph is acyclic;
    * every name in ``requires`` also appears in the prose body, in a block
      that also tells the agent to use the ``Skill`` tool -- a declared edge
      that no sentence asks for would never fire at runtime, and a bare mention
      is not a call. The check is per requirement, so a leaf with two
      requirements has to instruct the agent twice;
    * no skill mentioned in the prose is missing from ``requires`` -- an
      undeclared edge is invisible to the DAG documentation.

    Returns:
        The loaded skills, so a caller can validate and use in one step.

    Raises:
        ValueError: If any check fails. All problems are reported at once.
    """
    skills = load_skills(checklist_dir)
    known = sorted(skills)
    problems: List[str] = []

    for name in known:
        for version in sorted(skills[name]):
            skill = skills[name][version]
            declared = set(skill.requires)
            blocks = _prose_blocks(skill.body)

            for requirement in skill.requires:
                if requirement == name:
                    problems.append(
                        f"{skill.path}: {name!r} requires itself"
                    )
                    continue
                if requirement not in skills:
                    problems.append(
                        f"{skill.path}: requires unknown skill "
                        f"{requirement!r}; known skills are "
                        f"{', '.join(known)}"
                    )
                    continue

                asking = [
                    block for block in blocks if _mentions(block, requirement)
                ]
                if not asking:
                    problems.append(
                        f"{skill.path}: declares requires: {requirement!r} but "
                        "never asks for it in the prose; frontmatter documents "
                        "the graph, prose runs it"
                    )
                elif not any(
                    _mentions(block, SKILL_TOOL) for block in asking
                ):
                    problems.append(
                        f"{skill.path}: mentions {requirement!r} but never "
                        f"tells the agent to use the {SKILL_TOOL!r} tool on "
                        "it; a bare mention is not a call"
                    )

            for invoked in sorted(invoked_skills(skill, known) - declared):
                problems.append(
                    f"{skill.path}: prose invokes {invoked!r} but it is "
                    "missing from requires"
                )

    cycle = find_cycle(_without_self_edges(build_graph(skills)))
    if cycle is not None:
        problems.append(
            f"{checklist_dir}: the skill graph has a cycle: "
            f"{' -> '.join(cycle)}"
        )

    if problems:
        raise ValueError(
            f"{len(problems)} problem(s) in the skills of {checklist_dir}:\n"
            + "\n".join(f"  - {problem}" for problem in problems)
        )
    return skills


def select_versions(
    skills: Mapping[str, Mapping[str, Skill]],
    pins: Optional[Mapping[str, str]] = None,
) -> Dict[str, Skill]:
    """Choose exactly one version of each skill.

    Version *pinning* by manifest is Milestone 6. Until then the default is
    the highest ``vN``, which keeps the runtime deterministic without
    pretending to be the manifest.

    Raises:
        ValueError: If a pin names a skill or a version that does not exist.
    """
    pins = dict(pins or {})
    unknown = sorted(set(pins) - set(skills))
    if unknown:
        raise ValueError(
            f"Pinned skill(s) not in the checklist: {', '.join(unknown)}"
        )

    selected: Dict[str, Skill] = {}
    for name, versions in skills.items():
        if name in pins:
            version = pins[name]
            if version not in versions:
                raise ValueError(
                    f"Pinned version {version!r} of {name!r} does not exist; "
                    f"available: {', '.join(sorted(versions))}"
                )
        else:
            version = max(versions, key=lambda v: int(v[1:]))
        selected[name] = versions[version]
    return selected


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)
