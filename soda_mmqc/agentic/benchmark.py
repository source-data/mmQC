"""A benchmark example, stated as the content the harness stages.

The one place the harness meets mmQC's example store: where an example
lives (``EXAMPLES_DIR/<example>/content/``), what kind it is (the check's
``benchmark.json`` says, through ``example_class``), and which part of it is
gold (``checks/``, never staged). Runtime assembly takes the result and knows
none of this.
"""

from __future__ import annotations

from pathlib import Path

from soda_mmqc.config import EXAMPLES_DIR
from soda_mmqc.core.examples import EXAMPLE_FACTORY
from soda_mmqc.agentic.runtime import EXAMPLE_GOLD_SUBDIR, ExampleContent
from soda_mmqc.agentic.skills import _read_json, resolve_check_dir

__all__ = ["EXAMPLE_INPUT_SUBDIR", "example_content"]

#: Subdirectory of an example holding its inputs. The only thing staged.
EXAMPLE_INPUT_SUBDIR = "content"


def example_content(checklist: str, check: str, example: str) -> ExampleContent:
    """The content of one benchmark example, for assembling a runtime.

    Raises:
        FileNotFoundError: If the example or its input directory is absent.
        ValueError: If the check's benchmark declares no ``example_class``.
    """
    input_dir = _example_input_dir(example)
    benchmark = _read_json(resolve_check_dir(checklist, check) / "benchmark.json")
    example_class = benchmark.get("example_class")
    if not example_class:
        raise ValueError(
            f"No example_class in {checklist}/{check}/benchmark.json. The "
            "harness cannot state this example's input without knowing what "
            "kind of example it is, and it must not guess from extensions."
        )
    staged = EXAMPLE_FACTORY.create(example, example_class)
    return ExampleContent(
        source_root=input_dir,
        parts=tuple(staged.input_parts()),
        files=staged.supporting_files(),
        label=example,
        exclude=(EXAMPLE_GOLD_SUBDIR,),
    )


def _example_input_dir(example: str) -> Path:
    """Return the directory holding one example's inputs.

    Raises:
        FileNotFoundError: If the example or its input directory is absent.
    """
    example_dir = EXAMPLES_DIR / example
    if not example_dir.is_dir():
        raise FileNotFoundError(f"Example not found: {example_dir}")
    input_dir = example_dir / EXAMPLE_INPUT_SUBDIR
    if not input_dir.is_dir():
        raise FileNotFoundError(
            f"Example {example} has no {EXAMPLE_INPUT_SUBDIR}/ directory: "
            f"{input_dir}"
        )
    return input_dir
