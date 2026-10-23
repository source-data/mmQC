"""Run a structured checklist on one example, in a sealed agent session.

Requires the ``agentic`` extra: ``pip install "mmqc-utils[agentic]"``.

A checklist is a directory of versioned skills (``<skill>/vN/SKILL.md``) that
call each other in their prose. One of them, the entry point, owns a
``schema.json``: the structure of the answer. For one example:

1. state its content as an :class:`ExampleContent`;
2. assemble a sealed runtime for the entry point (:func:`runtime_session`
   assembles one, yields it, and removes it afterwards);
3. run a session in it (:func:`run_session`), which returns the answer,
   validated against the entry point's schema, with the trace of the skills
   the session invoked and an audit of its tool calls and cost.

The modules: :mod:`.skills` (reading skills, the call graph),
:mod:`.pinning` (versions, model defaults), :mod:`.runtime` (assembly and the
session's permission profile), :mod:`.session` (running and auditing a
session), :mod:`.render` (content parts for a provider).
"""

from mmqc_utils.agentic.pinning import (
    SkillSet,
    checklist_pins,
    load_model_defaults,
    skill_content_hash,
)
from mmqc_utils.agentic.runtime import (
    ExampleContent,
    RuntimeLayout,
    assemble_runtime,
    effective_session_options,
    session_options,
)
from mmqc_utils.agentic.session import run_session, runtime_session
from mmqc_utils.agentic.skills import Skill, call_closure, validate_skills

__all__ = [
    "ExampleContent",
    "RuntimeLayout",
    "Skill",
    "SkillSet",
    "assemble_runtime",
    "call_closure",
    "checklist_pins",
    "effective_session_options",
    "load_model_defaults",
    "run_session",
    "runtime_session",
    "session_options",
    "skill_content_hash",
    "validate_skills",
]
