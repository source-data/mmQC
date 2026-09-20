"""Version pinning: the manifest, the SkillSet, and expansion.

A version number is a claim about content; the content hash is the content.
A `SkillSet` carries both, so that a digest mismatch between two runs can be
explained -- "`identify-panels` moved from v1 to v2" -- rather than merely
reported.
"""

from __future__ import annotations

import dataclasses
import itertools
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import yaml

from soda_mmqc import logger
from soda_mmqc.config import AGENTIC_SKILLSET_WARN_THRESHOLD
from soda_mmqc.agentic.skills import (
    SKILL_FILENAME,
    Skill,
    load_skills,
)

__all__ = [
    "VERSION_MANIFEST_FILENAME",
    "MODEL_DEFAULTS_FILENAME",
    "SkillSet",
    "SkillSetEntry",
    "ModelDefaults",
    "skill_content_hash",
    "resolve_skill_set",
    "load_version_manifest",
    "validate_version_manifest",
    "checklist_pins",
    "load_model_defaults",
    "expand_skill_sets",
]


# ---------------------------------------------------------------------------
# Version pinning: the manifest, the SkillSet, and expansion
# ---------------------------------------------------------------------------
#
# Up to here a version is chosen by convention -- the highest ``vN``. That is
# fine for a pilot and wrong for anything whose results get attributed to a
# name. `version-manifest.yaml` replaces the convention with a file someone
# signed off on, and the SkillSet is what that file resolves to: the exact
# set of skill versions a run saw, hashed, so two runs can be compared or
# told apart without trusting a directory listing.

#: Hand-maintained. Pins exactly one version of every skill in the checklist.
VERSION_MANIFEST_FILENAME = "version-manifest.yaml"

#: Hand-maintained. Provider-neutral model and session defaults.
MODEL_DEFAULTS_FILENAME = "model-defaults.yaml"

#: Generated. The machine-readable picture of the graph.
DAG_FILENAME = "dag.yaml"

#: Generated. The same picture, for a person.
GENERATED_README_FILENAME = "README.md"

#: Session option keys `model-defaults.yaml` may not set. These are the
#: containment boundary, which is a property of the runtime rather than of a
#: checklist; letting a checklist file move it would make the Milestone 3
#: profile advisory.
_PROFILE_OWNED_OPTIONS = (
    "allowed_tools",
    "cwd",
    "disallowed_tools",
    "permission_mode",
    "setting_sources",
    "skills",
)


@dataclass(frozen=True)
class SkillSetEntry:
    """One skill as it participates in a SkillSet."""

    name: str
    version: str
    content_hash: str


@dataclass(frozen=True)
class SkillSet:
    """The exact set of skill versions one run is built from.

    Identity is the digest, which covers *content*, not just version labels.
    A version number is a claim about content; the hash is the content. Both
    are carried so that a digest mismatch can be explained ("``shared`` moved
    from v1 to v2") rather than merely reported.
    """

    entries: Tuple[SkillSetEntry, ...]

    @property
    def pins(self) -> Dict[str, str]:
        return {entry.name: entry.version for entry in self.entries}

    @property
    def digest(self) -> str:
        """SHA-256 over the canonical JSON of the sorted entries."""
        canonical = json.dumps(
            [
                {
                    "name": e.name,
                    "version": e.version,
                    "content_hash": e.content_hash,
                }
                for e in sorted(self.entries, key=lambda e: e.name)
            ],
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def label(self, baseline: Mapping[str, str]) -> str:
        """Name this set by what it changes relative to ``baseline``.

        Used for the per-set output directory of an unpinned comparison: the
        interesting thing about a set is never all fifteen pins, it is the
        one that moved.
        """
        differing = sorted(
            f"{e.name}@{e.version}"
            for e in self.entries
            if baseline.get(e.name) != e.version
        )
        return "-".join(differing) if differing else "pinned"


def skill_content_hash(skill: Skill) -> str:
    """SHA-256 of a skill version's ``SKILL.md`` bytes."""
    return hashlib.sha256(skill.path.read_bytes()).hexdigest()


def resolve_skill_set(
    skills: Mapping[str, Mapping[str, Skill]],
    pins: Mapping[str, str],
) -> SkillSet:
    """Resolve pins to the SkillSet they name.

    Raises:
        KeyError: If a pin names a skill or version that is not present.
            Callers that want a readable message validate first.
    """
    return SkillSet(
        entries=tuple(
            SkillSetEntry(
                name=name,
                version=pins[name],
                content_hash=skill_content_hash(skills[name][pins[name]]),
            )
            for name in sorted(pins)
        )
    )


def load_version_manifest(checklist_dir: Path) -> Dict[str, str]:
    """Read ``version-manifest.yaml`` into ``{skill: version}``.

    Completeness is checked separately, by
    :func:`validate_version_manifest`, because that needs the inventory and
    this only needs the file.

    Raises:
        FileNotFoundError: If the manifest is absent.
        ValueError: If it is unparseable, misshapen, or declares a different
            checklist than the directory it sits in.
    """
    checklist_dir = Path(checklist_dir)
    path = checklist_dir / VERSION_MANIFEST_FILENAME
    if not path.is_file():
        try:
            inventory = ", ".join(sorted(load_skills(checklist_dir)))
        except (FileNotFoundError, ValueError):
            inventory = ""
        raise FileNotFoundError(
            f"{checklist_dir}: no {VERSION_MANIFEST_FILENAME}. Every checklist "
            "run agentically needs one, pinning exactly one version of every "
            "skill, because it is the identity results are attributed to. "
            f"Create {path} with a 'skills:' mapping of 'skill-name: vN'"
            + (f" covering: {inventory}" if inventory else "")
        )

    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: not valid YAML: {exc}") from exc

    if not isinstance(document, dict):
        raise ValueError(
            f"{path}: must be a mapping with a 'skills' key, got "
            f"{type(document).__name__}"
        )

    declared = document.get("checklist")
    if declared is not None and declared != checklist_dir.name:
        raise ValueError(
            f"{path}: declares checklist {declared!r} but sits in "
            f"{checklist_dir.name!r}; this manifest belongs somewhere else"
        )

    pins = document.get("skills")
    if not isinstance(pins, dict) or not pins:
        raise ValueError(
            f"{path}: key 'skills' must be a non-empty mapping of skill name "
            "to version"
        )
    bad = sorted(
        str(name) for name, version in pins.items()
        if not isinstance(name, str) or not isinstance(version, str)
    )
    if bad:
        raise ValueError(
            f"{path}: every pin must be 'skill-name: vN'; offending: "
            f"{', '.join(bad)}"
        )
    return {str(name): str(version) for name, version in pins.items()}


def validate_version_manifest(
    skills: Mapping[str, Mapping[str, Skill]],
    pins: Mapping[str, str],
    checklist_dir: Path,
) -> None:
    """Check a manifest against the checklist's inventory.

    Three failures, reported together:

    * a skill with no pin -- a partial manifest is worse than none, because
      it looks authoritative while the unpinned half still drifts;
    * a pin naming a skill that is not there -- usually a rename or a
      deletion the manifest did not follow;
    * a pin naming a version that does not exist.

    Validation is against the **inventory**, not against a reachable closure.
    A skill nothing calls today still has to be pinned: discovery is the
    agent's job and today's graph is not a promise about tomorrow's session.

    Raises:
        ValueError: If any of the three fails.
    """
    path = Path(checklist_dir) / VERSION_MANIFEST_FILENAME
    problems: List[str] = []

    for name in sorted(set(skills) - set(pins)):
        problems.append(
            f"{name!r} has no pin; every skill of the checklist must be "
            f"pinned (available: {', '.join(sorted(skills[name]))})"
        )
    for name in sorted(set(pins) - set(skills)):
        problems.append(
            f"{name!r} is pinned but is not a skill of this checklist; it was "
            "renamed, moved or removed and the manifest did not follow"
        )
    for name in sorted(set(pins) & set(skills)):
        if pins[name] not in skills[name]:
            problems.append(
                f"{name!r} is pinned to {pins[name]!r}, which does not exist; "
                f"available: {', '.join(sorted(skills[name]))}"
            )

    if problems:
        raise ValueError(
            f"{path}: {len(problems)} problem(s):\n"
            + "\n".join(f"  - {problem}" for problem in problems)
        )


def checklist_pins(checklist_dir: Path) -> Optional[Dict[str, str]]:
    """Return the manifest pins, or ``None`` when there is no manifest.

    Falling back is deliberate but never silent: the synthetic checklists the
    tests build have no manifest and should not need one, while a production
    checklist losing its manifest must be visible in the log of the run that
    used the fallback -- not only in a `graph` invocation nobody ran.
    """
    try:
        return load_version_manifest(checklist_dir)
    except FileNotFoundError:
        logger.warning(
            "%s has no %s; falling back to the highest version of each skill. "
            "That is a convention, not a pin: results from this run are not "
            "attributable to a reviewed SkillSet.",
            Path(checklist_dir).name, VERSION_MANIFEST_FILENAME,
        )
        return None


@dataclass(frozen=True)
class ModelDefaults:
    """Provider-neutral defaults for a checklist.

    ``models`` is keyed by provider so that the file names *which* model each
    runtime should use without the file itself taking a side; ``session``
    holds the provider-neutral knobs (turn ceilings and the like) that
    :func:`effective_session_options` folds in.
    """

    models: Mapping[str, str] = dataclasses.field(default_factory=dict)
    session: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def model_for(self, provider: str) -> Optional[str]:
        return self.models.get(provider)


def load_model_defaults(checklist_dir: Path) -> ModelDefaults:
    """Read ``model-defaults.yaml``; an absent file means no defaults.

    Unlike the version manifest, absence is legitimate: a checklist that is
    happy with the runner's defaults has nothing to say here.

    Raises:
        ValueError: If the file is unparseable, misshapen, or tries to set a
            session option the permission profile owns.
    """
    path = Path(checklist_dir) / MODEL_DEFAULTS_FILENAME
    if not path.is_file():
        return ModelDefaults()

    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: not valid YAML: {exc}") from exc
    if document is None:
        return ModelDefaults()
    if not isinstance(document, dict):
        raise ValueError(
            f"{path}: must be a mapping, got {type(document).__name__}"
        )

    models = document.get("models") or {}
    if not isinstance(models, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in models.items()
    ):
        raise ValueError(
            f"{path}: key 'models' must map a provider name to a model name, "
            "e.g. `openai: gpt-5-mini`"
        )

    session = document.get("session") or {}
    if not isinstance(session, dict):
        raise ValueError(
            f"{path}: key 'session' must be a mapping of option name to value"
        )
    owned = sorted(set(session) & set(_PROFILE_OWNED_OPTIONS))
    if owned:
        raise ValueError(
            f"{path}: may not set {', '.join(owned)}. The permission profile "
            "is a property of the sealed runtime, not of a checklist; "
            "widening it is a human gate, not a config edit"
        )
    return ModelDefaults(models=dict(models), session=dict(session))


def expand_skill_sets(
    skills: Mapping[str, Mapping[str, Skill]],
    pins: Mapping[str, str],
    unpin: Mapping[str, Optional[Sequence[str]]],
    *,
    warn_above: int = AGENTIC_SKILLSET_WARN_THRESHOLD,
) -> List[SkillSet]:
    """Expand the manifest into one SkillSet per version combination.

    Every skill not named in ``unpin`` keeps its manifest pin, so a
    comparison varies only what it says it varies. ``unpin`` maps a skill
    name to the versions to try, or ``None`` for all of them.

    Multiple unpinned skills are permitted -- the product of two skills'
    versions is a legitimate thing to want -- but the result is a session
    count multiplied by the number of examples, so crossing ``warn_above``
    says so rather than refusing. Refusing would be the runner making a
    spending decision that is the operator's.

    Raises:
        ValueError: If ``unpin`` names an unknown skill or version.
    """
    unknown = sorted(set(unpin) - set(skills))
    if unknown:
        raise ValueError(
            f"Cannot unpin {', '.join(unknown)}: not a skill of this "
            f"checklist. Known skills: {', '.join(sorted(skills))}"
        )

    choices: List[List[Tuple[str, str]]] = []
    for name in sorted(skills):
        if name in unpin:
            wanted = unpin[name]
            available = sorted(skills[name], key=lambda v: int(v[1:]))
            if wanted is None:
                versions = available
            else:
                missing = sorted(set(wanted) - set(available))
                if missing:
                    raise ValueError(
                        f"Cannot unpin {name!r} to {', '.join(missing)}: no "
                        f"such version. Available: {', '.join(available)}"
                    )
                versions = [v for v in available if v in set(wanted)]
        else:
            versions = [pins[name]]
        choices.append([(name, version) for version in versions])

    sets: List[SkillSet] = []
    for combination in itertools.product(*choices):
        sets.append(resolve_skill_set(skills, dict(combination)))

    if warn_above is not None and len(sets) > warn_above:
        logger.warning(
            "This expansion is %d SkillSets (threshold %d); every example "
            "will be run %d times. Narrow it with --versions if that is not "
            "what you meant.",
            len(sets), warn_above, len(sets),
        )
    return sets
