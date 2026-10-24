"""The production checklist publishes, and loads back as it is in the repository.

No network: a dictionary with Langfuse's two calls stands in for the store
(.github/scripts/publish_langfuse_skills.py does the real publishing).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from mmqc_utils.agentic.publication import (
    load_published_checklist,
    production_entry_point,
    skill_payloads,
)

from soda_mmqc.config import CHECKLIST_DIR, production_skill_checklists


class _Store:
    def __init__(self, payloads):
        self.prompts = {p["name"]: json.loads(json.dumps(p)) for p in payloads}

    def get_prompt(self, name, *, label):
        stored = self.prompts[name]
        assert label in stored["labels"]
        return SimpleNamespace(prompt=stored["prompt"], config=stored["config"])


def test_every_production_checklist_publishes_and_loads_back(tmp_path):
    for checklist in production_skill_checklists():
        source = CHECKLIST_DIR / checklist
        entry = production_entry_point(source)
        payloads = skill_payloads(source)
        loaded = load_published_checklist(_Store(payloads), checklist, entry, tmp_path)
        for payload in payloads:
            meta = payload["config"]["skill"]
            assert (loaded / meta["name"] / meta["version"] / "SKILL.md").read_bytes() == \
                (source / meta["name"] / meta["version"] / "SKILL.md").read_bytes()
        assert production_entry_point(loaded) == entry
        assert len(payloads) == len({p.parent.parent.name for p in loaded.glob("*/v*/SKILL.md")})


def test_fig_checklist_is_published_from_its_panel_major_entry_point():
    assert "fig-checklist" in production_skill_checklists()
    assert production_entry_point(CHECKLIST_DIR / "fig-checklist") == "do-fig-checklist-pm"
