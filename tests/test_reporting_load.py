"""What identifies a scored run, and how reporting finds one."""

from __future__ import annotations

import pytest

from soda_mmqc.core.eval_manifest import EvalManifest, FieldProfile
from soda_mmqc.reporting.aggregate import summarize_runs
from soda_mmqc.reporting.load import FlatRecord, FlatRun, FlatRuns, RunRef

CHECKLIST = "fig-checklist-exp01"
CHECK = "replication-reporting"
MODEL = "claude-sonnet-5"


def _manifest() -> EvalManifest:
    return EvalManifest(
        checklist=CHECKLIST,
        defaults=FieldProfile(),
        list_alignment={},
        _fields={},
        _field_keys={},
    )


def _run(*, arm: str, replicate: int, records=()) -> FlatRun:
    return FlatRun(
        ref=RunRef(
            checklist=CHECKLIST,
            check=CHECK,
            model=MODEL,
            arm=arm,
            replicate=replicate,
        ),
        records=tuple(records),
        manifest=_manifest(),
    )


def _record(example: str) -> FlatRecord:
    return FlatRecord(
        doc_id=example,
        metadata={"source": example},
        analysis={"instances": [], "by_list": {}},
    )


class TestRunIdentity:
    def test_a_run_is_identified_by_arm_and_replicate(self):
        """The axes the harness produces, not the ones prompts had.

        `prompt` is deleted rather than renamed to `arm`: an arm is a
        different configuration of the same skill set, a prompt was a
        different wording, and code written for one is not correct for
        the other.
        """
        ref = RunRef(
            checklist=CHECKLIST,
            check=CHECK,
            model=MODEL,
            arm="pinned",
            replicate=3,
        )
        assert ref.replicate == 3
        assert not hasattr(ref, "prompt")

    def test_flat_run_still_exposes_the_flat_attributes(self):
        """Consumers read run.check, not run.ref.check."""
        run = _run(arm="pinned", replicate=0)
        assert run.checklist == CHECKLIST
        assert run.check == CHECK
        assert run.model == MODEL
        assert run.arm == "pinned"
        assert run.replicate == 0

    def test_a_ref_is_hashable_so_it_can_key_a_mapping(self):
        refs = {
            _run(arm="pinned", replicate=0).ref,
            _run(arm="pinned", replicate=0).ref,
            _run(arm="pinned", replicate=1).ref,
        }
        assert len(refs) == 2


class TestSummariesGroupByArm:
    @pytest.fixture
    def summaries(self):
        return summarize_runs(
            FlatRuns(
                [
                    _run(arm="pinned", replicate=0, records=[_record("a")]),
                    _run(arm="pinned", replicate=1, records=[_record("a")]),
                    _run(
                        arm=f"{CHECK}@v2",
                        replicate=0,
                        records=[_record("a")],
                    ),
                ]
            )
        )

    def test_arms_are_listed(self, summaries):
        assert set(summaries.arms) == {"pinned", f"{CHECK}@v2"}

    def test_replicates_are_listed(self, summaries):
        assert summaries.replicates == (0, 1)

    def test_for_arm_returns_every_replicate_in_order(self, summaries):
        pinned = summaries.for_arm("pinned")
        assert [s.replicate for s in pinned] == [0, 1]

    def test_summaries_are_keyed_by_ref(self, summaries):
        ref = RunRef(
            checklist=CHECKLIST,
            check=CHECK,
            model=MODEL,
            arm="pinned",
            replicate=1,
        )
        assert summaries[ref].arm == "pinned"
        assert summaries[ref].replicate == 1


def test_the_prompt_axis_is_gone():
    """Not renamed -- removed, so prompt-era assumptions cannot survive."""
    import soda_mmqc.reporting.load as load
    import soda_mmqc.reporting.aggregate as aggregate

    for name in ("normalize_prompt_name", "load_prompt_text"):
        assert not hasattr(load, name), f"{name} belongs to the prompt path"
    assert not hasattr(aggregate.RunSummaries, "for_prompt")
    assert not hasattr(aggregate.RunSummaries, "prompts")
