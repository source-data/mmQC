"""Publishing a production checklist's skills, and loading them back.

A prompt store (Langfuse) is the boundary between the repository a checklist
is developed in and the application that runs it. Only production is
published: the pinned version of each skill, one prompt per skill, named
``skills/<checklist>/<skill>`` and labelled ``production``. The application
loads what carries the label and never sees versions or the repository.

What one prompt holds:

* **text**: the skill's whole ``SKILL.md``, front matter included, so the
  file written back is byte-identical and its content hash is the one the
  benchmark measured;
* **config**, keyed by file name: ``schema`` and ``eval-manifest`` where the
  skill owns them, ``model-defaults`` on the entry point, and ``skill`` --
  checklist, name, version, role, content hash and ``release``, the digest of
  the whole published set.

Loading needs no listing of the store: it fetches the entry point and follows
each skill's ``requires`` to the next. That reaches exactly the published set,
because a production checklist pins nothing its entry point does not reach
(:func:`production_entry_point`). The skills are written back as an ordinary
checklist directory, so validation, assembly and sessions run on them as on
the repository's.

Nothing here imports a client: callers pass one, with ``get_prompt(name,
label=...)`` returning an object carrying ``prompt`` and ``config``, as
Langfuse's does.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping

import yaml

from mmqc_utils.agentic.pinning import (
    MODEL_DEFAULTS_FILENAME,
    VERSION_MANIFEST_FILENAME,
    checklist_pins,
    resolve_skill_set,
    skill_content_hash,
    validate_version_manifest,
)
from mmqc_utils.agentic.skills import (
    SKILL_FILENAME,
    call_closure,
    load_skill,
    select_versions,
    validate_skills,
)

__all__ = [
    "PRODUCTION_LABEL",
    "RELEASE_RECORD",
    "SKILLS_NAMESPACE",
    "load_published_checklist",
    "production_entry_point",
    "prompt_name",
    "published_release",
    "pull_checklist",
    "skill_payloads",
    "verify_local_checklist",
]

SKILLS_NAMESPACE = "skills"
PRODUCTION_LABEL = "production"

#: Contract files carried in a prompt's config, under their stem.
CONTRACT_FILES = ("schema.json", "eval-manifest.json")


def prompt_name(checklist: str, skill: str) -> str:
    return f"{SKILLS_NAMESPACE}/{checklist}/{skill}"


def production_entry_point(checklist_dir: Path) -> str:
    """Check the rules a production checklist obeys; return its entry point.

    Beyond what every checklist obeys (:func:`validate_skills`, a complete
    version manifest):

    * **one topology**: every version of a skill declares the same
      ``requires``, so prose may vary across versions and the call graph may
      not;
    * **one entry point**: exactly one pinned skill is called by no other,
      and it owns a ``schema.json``;
    * **nothing unreached**: every pinned skill is reached from it.

    Raises:
        ValueError: Naming every rule broken.
    """
    checklist_dir = Path(checklist_dir)
    skills = validate_skills(checklist_dir)
    pins = checklist_pins(checklist_dir)
    if pins is None:
        raise ValueError(f"{checklist_dir}: a production checklist needs a {VERSION_MANIFEST_FILENAME}")
    validate_version_manifest(skills, pins, checklist_dir)
    problems: List[str] = []

    for name, versions in sorted(skills.items()):
        edges = {version: tuple(sorted(skill.requires)) for version, skill in versions.items()}
        if len(set(edges.values())) > 1:
            problems.append(f"{name}: versions call different skills {edges}; prose may vary, the topology may not")

    selected = select_versions(skills, pins)
    called = {callee for skill in selected.values() for callee in skill.requires}
    roots = sorted(set(selected) - called)
    if len(roots) != 1:
        problems.append(f"expected one entry point (a pinned skill no other calls), found {roots}")
    else:
        entry = roots[0]
        if not (checklist_dir / entry / "schema.json").is_file():
            problems.append(f"{entry}: the entry point owns no schema.json")
        unreached = sorted(set(selected) - call_closure(entry, selected))
        if unreached:
            problems.append(f"pinned but not reached from {entry}: {unreached}")

    if problems:
        raise ValueError(f"{checklist_dir} is not a production checklist:\n  " + "\n  ".join(problems))
    return roots[0]


def skill_payloads(checklist_dir: Path) -> List[Dict[str, Any]]:
    """One prompt per pinned skill of a production checklist, ready to publish.

    Each is ``{name, prompt, config, labels, tags, type}``, the arguments of
    Langfuse's ``create_prompt``.
    """
    checklist_dir = Path(checklist_dir)
    entry = production_entry_point(checklist_dir)
    skills = validate_skills(checklist_dir)
    pins = checklist_pins(checklist_dir)
    release = resolve_skill_set(skills, pins).digest
    checklist = checklist_dir.name

    payloads = []
    for name in sorted(pins):
        skill = skills[name][pins[name]]
        contracts = {
            Path(filename).stem: json.loads((checklist_dir / name / filename).read_text(encoding="utf-8"))
            for filename in CONTRACT_FILES
            if (checklist_dir / name / filename).is_file()
        }
        role = "entry" if name == entry else "leaf" if "schema" in contracts else "shared"
        config: Dict[str, Any] = {
            "skill": {
                "checklist": checklist,
                "name": name,
                "version": pins[name],
                "role": role,
                "content_hash": skill_content_hash(skill),
                "release": release,
            },
            **contracts,
        }
        defaults = checklist_dir / MODEL_DEFAULTS_FILENAME
        if role == "entry" and defaults.is_file():
            config["model-defaults"] = yaml.safe_load(defaults.read_text(encoding="utf-8"))
        payloads.append({
            "name": prompt_name(checklist, name),
            "prompt": skill.path.read_text(encoding="utf-8"),
            "config": config,
            "labels": [PRODUCTION_LABEL],
            "tags": [role],
            "type": "text",
        })
    return payloads


def load_published_checklist(
    client: Any,
    checklist: str,
    entry: str,
    dest: Path,
    *,
    label: str = PRODUCTION_LABEL,
) -> Path:
    """Fetch a published checklist and write it as a checklist directory.

    Returns ``dest/<checklist>``, ready for :func:`validate_skills` and
    assembly.

    Raises:
        ValueError: If the skills do not belong to one release -- a publish
            still in progress, or a mixed store -- or a skill's text does not
            match its recorded content hash.
    """
    root = Path(dest) / checklist
    pins: Dict[str, str] = {}
    configs: Dict[str, Mapping[str, Any]] = {}
    pending = [entry]
    while pending:
        name = pending.pop()
        if name in pins:
            continue
        fetched = client.get_prompt(prompt_name(checklist, name), label=label)
        config = dict(fetched.config or {})
        meta = config.get("skill") or {}
        version = meta.get("version")
        if meta.get("name") != name or not version:
            raise ValueError(f"{prompt_name(checklist, name)}: its config names no skill version")
        path = root / name / version / SKILL_FILENAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(fetched.prompt, encoding="utf-8")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != meta.get("content_hash"):
            raise ValueError(f"{prompt_name(checklist, name)}: text does not match its content hash")
        for stem in (Path(f).stem for f in CONTRACT_FILES):
            if stem in config:
                (root / name / f"{stem}.json").write_text(
                    json.dumps(config[stem], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        pins[name] = version
        configs[name] = config
        pending.extend(load_skill(path).requires)

    releases = {config["skill"].get("release") for config in configs.values()}
    if len(releases) != 1:
        raise ValueError(
            f"{checklist}: the skills fetched belong to {len(releases)} releases; a publish may be "
            "in progress -- retry, and if it persists, republish")
    defaults = configs[entry].get("model-defaults")
    if defaults is not None:
        (root / MODEL_DEFAULTS_FILENAME).write_text(yaml.safe_dump(defaults, sort_keys=False), encoding="utf-8")
    manifest = {"checklist": checklist, "skills": dict(sorted(pins.items()))}
    (root / VERSION_MANIFEST_FILENAME).write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    validate_skills(root)
    return root


#: Written beside a pulled checklist: which release it is, from where, and
#: each skill's content hash, so a local copy can be verified offline.
RELEASE_RECORD = "release.json"


def published_release(client: Any, checklist: str, entry: str, *, label: str = PRODUCTION_LABEL) -> str:
    """The release the store's entry point carries under ``label``."""
    fetched = client.get_prompt(prompt_name(checklist, entry), label=label)
    return ((fetched.config or {}).get("skill") or {}).get("release")


def verify_local_checklist(path: Path) -> Dict[str, Any]:
    """Check a pulled checklist offline; return its release record.

    Integrity: every skill's ``SKILL.md`` matches the content hash recorded
    when it was pulled. Consistency: the production rules hold, with the
    recorded entry point.

    Raises:
        ValueError: Naming every problem.
    """
    path = Path(path)
    record_path = path / RELEASE_RECORD
    if not record_path.is_file():
        raise ValueError(f"{path}: no {RELEASE_RECORD}; not a pulled checklist")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    problems: List[str] = []
    for name, meta in sorted(record["skills"].items()):
        skill_file = path / name / meta["version"] / SKILL_FILENAME
        if not skill_file.is_file():
            problems.append(f"{name}: {skill_file.relative_to(path)} is missing")
        elif hashlib.sha256(skill_file.read_bytes()).hexdigest() != meta["content_hash"]:
            problems.append(f"{name}: {skill_file.relative_to(path)} does not match its content hash")
    if not problems:
        try:
            entry = production_entry_point(path)
            if entry != record["entry"]:
                problems.append(f"entry point is {entry}, the record says {record['entry']}")
        except ValueError as exc:
            problems.append(str(exc))
    if problems:
        raise ValueError(f"{path} failed verification:\n  " + "\n  ".join(problems))
    return record


def pull_checklist(
    client: Any,
    checklist: str,
    entry: str,
    dest: Path,
    *,
    label: str = PRODUCTION_LABEL,
) -> Dict[str, Any]:
    """Bring ``dest/<checklist>`` to the store's release, atomically.

    Does nothing when the local copy already holds that release and verifies.
    Otherwise fetches into a temporary directory beside it, checks it (hashes,
    one release, the production rules, the entry point), records the release,
    and only then swaps it into place -- so a failed update leaves the copy
    that was there.

    Returns:
        The release record, with ``"changed"``: whether anything was replaced.

    Raises:
        ValueError: If what the store holds does not check out.
    """
    from datetime import datetime, timezone
    import os
    import shutil
    import tempfile

    dest = Path(dest)
    target = dest / checklist
    remote = published_release(client, checklist, entry, label=label)
    if (target / RELEASE_RECORD).is_file():
        try:
            record = verify_local_checklist(target)
            if record["release"] == remote:
                return {**record, "changed": False}
        except ValueError:
            pass                                   # replace a copy that fails

    dest.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{checklist}.pull-", dir=dest))
    try:
        loaded = load_published_checklist(client, checklist, entry, staging, label=label)
        if production_entry_point(loaded) != entry:
            raise ValueError(f"{checklist}: the published checklist's entry point is not {entry}")
        pins = checklist_pins(loaded)
        record = {
            "checklist": checklist,
            "entry": entry,
            "label": label,
            "release": remote,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "skills": {
                name: {
                    "version": version,
                    "content_hash": hashlib.sha256(
                        (loaded / name / version / SKILL_FILENAME).read_bytes()).hexdigest(),
                }
                for name, version in sorted(pins.items())
            },
        }
        (loaded / RELEASE_RECORD).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        verify_local_checklist(loaded)
        previous = None
        if target.exists():
            previous = dest / f".{checklist}.previous"
            shutil.rmtree(previous, ignore_errors=True)
            os.replace(target, previous)
        os.replace(loaded, target)
        if previous is not None:
            shutil.rmtree(previous, ignore_errors=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return {**record, "changed": True}
