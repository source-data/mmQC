---
title: The example states its own input, then an `agentic/` package
date: 2026-09-20
status: proposed, awaiting review
follows: 2026-09-19-runtime-contract-design.md
---

# The example states its own input, then an `agentic/` package

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every figure-specific mechanic from the agentic harness by
having the `Example` hierarchy state its own input in provider-neutral terms,
delivered to the session up front rather than waited for; then move the
harness out of `cli.py` into a `soda_mmqc/agentic/` package.

**Architecture:** Two changes, in order. First, the agent receives the
example's content in its opening message — the way the legacy API path
already works — while supporting files stay staged for on-demand reading.
`Example` states what its content *is*, in a vocabulary that names no
provider; the drivers render it. Second, the harness becomes a package of
focused modules instead of 3400 lines of `cli.py`.

**Tech Stack:** Python, `pytest`, the Claude Agent SDK (`claude-sdk`
provider, `query(prompt: str | AsyncIterable[dict])`) and the OpenAI provider
(Chat Completions).

**Spec:** this document. Its predecessor is
[`2026-09-19-runtime-contract-design.md`](2026-09-19-runtime-contract-design.md),
which introduced the static `CLAUDE.md` and the `inputs.json` manifest.

---

## Why

### Now

Input reaches the agent by **pull**. The harness stages a copy of the
example's `content/` directory, names some files in `input/inputs.json`, and
waits for the session to call `Read`. The tool result carries the bytes —
`agentic_openai.py:107-113` base64-encodes an image into an `image_url` part
when, and only when, the agent asks for it.

Everything figure-shaped in the harness follows from that choice:

| Site | Assumption | Exists because |
|---|---|---|
| `_resolve_staged_inputs` (`cli.py:1473`) | inputs are discoverable by extension | the harness must name files for the agent to pull |
| `config.AGENTIC_IMAGE_EXTENSIONS` | inputs are images | same |
| `_write_input_manifest` (`cli.py:1523`) | manifest keys are figure roles | same |
| `_session_prompt` (`cli.py:2167`) | *"Apply the `X` check to the **figure** staged in …"* | the prompt must point at files |
| `_assert_the_session_read_the_figure` (`cli.py:2236`) | the must-read file is an image | **a pulled input can go unpulled** |

The last row is the tell. On 2026-09-18 a session failed to guess the image
filename, gave up, and answered from the caption alone: every panel said
`micrograph: "no"`, the gold for that figure is all-negative, and it scored
8/8. The run was recorded as `ok`. The gate exists to catch a failure that is
only possible because the model has to choose to fetch its own input.

Two consequences, one already visible and one not:

- A `word` example cannot be staged at all — `_resolve_staged_inputs` refuses
  it before anything else runs. It stays invisible only because no
  `doc-checklist` check owns a `SKILL.md` yet.
- Nothing converts a document on this path. `prepare_model_input` has three
  callers — `core/curation.py:867`, `lib/api.py:559`, `lib/api.py:863` — all
  legacy; `cli.py` never calls it. A manuscript would arrive as a raw
  `.docx` at a session whose only tools are `Read` and `Skill`.

### Proposed

**The example's content is pushed into the opening message. Supporting files
stay staged and pulled.**

This is what the legacy path already does: `prepare_model_input` builds a
payload and hands it to the API. It is possible on both agentic runtimes —
`claude_agent_sdk.query` accepts `prompt: str | AsyncIterable[dict[str, Any]]`
and streaming dicts carry ordinary content blocks; the OpenAI driver's user
message is `{"role": "user", "content": prompt}` and takes a content-part list.
Only the string happened to be used.

What falls out:

- **The read gate is unnecessary and is deleted.** An input in the opening
  message cannot go unread. The 2026-09-18 failure becomes unrepresentable
  rather than detected.
- **The document problem dissolves.** `WordExample` already converts to HTML
  at load; HTML is text and goes straight into the message. No file is
  written, so the staged copy stays byte-identical.
- **One confound leaves exp-01.** Under pull, a minimal skill can lose
  because it never told the agent to open the image — which is not the
  verbosity effect the experiment is meant to measure.
- **Source data keeps its economy.** This figure example stages seven
  `.xlsx` files. They stay staged and named, so the agent opens what it needs
  instead of paying for all of them on every turn of a 24–30 turn chain.

### `prepare_model_input` is not reused, and is not touched

It is OpenAI-Responses-shaped — `input_text`, `input_image`, `input_file` —
and `_upload_table_and_get_file_id` uploads to OpenAI's Files API for a
`file_id`. Rendering that into Anthropic content blocks would put provider
translation inside the example hierarchy.

So `Example` gains a **provider-neutral** statement of its content, and each
driver renders it — the same separation `model-defaults.yaml` already draws
for models. `prepare_model_input` stays exactly as it is, and the legacy path
is untouched. The two overlap in what they know (a figure is a caption and an
image); unifying them is later work, recorded as open question 2.

### What does not change

- **The staged copy is byte-identical to the source.** No conversion, rename,
  filter or derived file is ever written into the runtime. `WordExample`'s
  HTML exists only in the message.
- **No new agent capability.** No `Bash`, no `Glob`, no subagents. The
  permission profile is untouched.
- **The DAG stays undescribed to the agent.**
- `Example.prepare_model_input`, `load_from_source`, `get_content_hash` and
  `to_dict` are not modified by any task here.

---

## Global Constraints

Every task's requirements implicitly include this section.

- **The runtime is a copy, not a processed copy.** The staged `input/` tree is
  byte-identical to the example's `content/` tree. No task may write a
  derived file into the runtime.
- **`core/examples.py` keeps sole authority** over how examples are read and
  what their content is. Tasks 1–2 add methods; no task modifies
  `load_from_source`, `prepare_model_input`, `get_content_hash` or `to_dict`.
- **`Example` names no provider.** No `input_text`, no `image_url`, no
  `media_type` vocabulary borrowed from an SDK, no base64 encoding. Rendering
  belongs to the drivers.
- **No new agent capability.** `AGENTIC_FORBIDDEN_TOOLS` and the allowlist are
  not edited by any task in this plan.
- **Phase 2 is a pure move.** No behaviour change; `cli.py` re-exports every
  name in its current `__all__`, so the suites pass without edits.
- **Run after every task:** `pytest tests/test_agentic_cli.py tests/test_agentic_integration.py -q`
- **Path contract:** every path an `Example` returns is relative to that
  example's `content/` directory, POSIX-separated. Rebasing onto a runtime is
  the harness's job.

---

## File Structure

**Phase 1**

| File | Responsibility after this phase |
|---|---|
| `soda_mmqc/core/examples.py` | Adds `Example.input_parts()` and `Example.supporting_files()`, abstract, implemented by `FigureExample` and `WordExample`. `FigureExample` retains `caption_path`. |
| `soda_mmqc/agentic_render.py` | New. Renders neutral parts into Anthropic content blocks and OpenAI Chat Completions parts. The only module that knows either vocabulary. |
| `soda_mmqc/cli.py` | Loses `_resolve_staged_inputs` and `_assert_the_session_read_the_figure`. `RuntimeLayout` gains `input_parts`. `_session_prompt` becomes `_session_message`. `_write_input_manifest` names supporting files only. |
| `soda_mmqc/config.py` | Loses `AGENTIC_IMAGE_EXTENSIONS`. |
| `soda_mmqc/agentic_openai.py` | Its user message takes a content-part list. |
| `soda_mmqc/data/agentic/CLAUDE.md` | Generic: no figure, no caption, no `artifacts/`. |
| `tests/test_example_inputs.py` | New. The two example classes' neutral statements. |
| `tests/test_agentic_render.py` | New. Neutral parts → each provider's shape. |
| `tests/test_agentic_cli.py` | Read-gate tests deleted; fake clients take a message instead of a string. |

**Phase 2**

| File | Responsibility |
|---|---|
| `soda_mmqc/agentic/__init__.py` | Package marker. No re-exports; importers name the module they want. |
| `soda_mmqc/agentic/skills.py` | `Skill`, loading, graph building, validation, `select_versions`. |
| `soda_mmqc/agentic/pinning.py` | `SkillSet`, `ModelDefaults`, manifest loading, `expand_skill_sets`. |
| `soda_mmqc/agentic/views.py` | `render_dag`, `render_readme`, `graph_checklist`. |
| `soda_mmqc/agentic/runtime.py` | `RuntimeLayout`, `assemble_runtime`, sealing, permission profile. |
| `soda_mmqc/agentic/render.py` | `soda_mmqc/agentic_render.py` moves here. |
| `soda_mmqc/agentic/session.py` | `runtime_session`, trace, audit, hooks, structured-output validation. |
| `soda_mmqc/agentic/openai_driver.py` | `soda_mmqc/agentic_openai.py` moves here. |
| `soda_mmqc/agentic/runner.py` | `run_check_mock`, `run_check_live`, `run_checklist_live`. |
| `soda_mmqc/agentic/CLAUDE.md` | The orientation template, beside the code that copies it. |
| `soda_mmqc/cli.py` | `argparse`, dispatch, `score_check`, prediction loading, re-exports. |

---

# Phase 1 — the example states its own input

## Task 1: `FigureExample` states its content and its supporting files

**Files:**
- Modify: `soda_mmqc/core/examples.py` (`Example`, `FigureExample`)
- Test: `tests/test_example_inputs.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Example.input_parts(self) -> List[Dict[str, Any]]` — abstract. An ordered
    list of neutral parts. Exactly two kinds:
    `{"kind": "text", "text": str}` and
    `{"kind": "image", "path": str}` where `path` is content-relative.
  - `Example.supporting_files(self) -> Dict[str, Any]` — abstract. Role name →
    content-relative path, `None`, or list of paths.
  - `FigureExample.caption_path: Optional[Path]`

**Why `image` carries a path rather than bytes:** the example says *which*
file is the image; reading and encoding it is the driver's job. Keeping
base64 out of `Example` keeps these methods cheap to call and to assert on,
and keeps provider encodings out of the domain layer.

- [ ] **Step 1: Write the failing test**

Create `tests/test_example_inputs.py`:

```python
"""What an example's content is, stated by the example and no one else."""

import pytest

from soda_mmqc.config import EXAMPLES_DIR
from soda_mmqc.core.examples import EXAMPLE_FACTORY

FIGURE_EXAMPLE = "10.1038_s44318-026-00715-1/content/1"

requires_figure_example = pytest.mark.skipif(
    not (EXAMPLES_DIR / FIGURE_EXAMPLE).is_dir(),
    reason=f"example store has no {FIGURE_EXAMPLE}",
)


@requires_figure_example
class TestFigureExampleStatesItsContent:
    def test_the_parts_are_the_caption_then_the_image(self):
        example = EXAMPLE_FACTORY.create(FIGURE_EXAMPLE, "figure")
        parts = example.input_parts()
        assert [part["kind"] for part in parts] == ["text", "image"]
        assert example.caption in parts[0]["text"]

    def test_the_image_part_names_a_file_under_content(self):
        example = EXAMPLE_FACTORY.create(FIGURE_EXAMPLE, "figure")
        image = next(p for p in example.input_parts() if p["kind"] == "image")
        content = example.source_path / "content"
        assert (content / image["path"]).is_file()
        assert image["path"] == example.image_path.name

    def test_no_part_carries_provider_vocabulary(self):
        """`Example` states content; drivers render it. Neither leaks."""
        example = EXAMPLE_FACTORY.create(FIGURE_EXAMPLE, "figure")
        for part in example.input_parts():
            assert set(part) <= {"kind", "text", "path"}
            assert part["kind"] in {"text", "image"}

    def test_supporting_files_are_the_source_data(self):
        example = EXAMPLE_FACTORY.create(FIGURE_EXAMPLE, "figure")
        supporting = example.supporting_files()
        assert set(supporting) == {"source_data"}
        content = example.source_path / "content"
        assert supporting["source_data"]
        for entry in supporting["source_data"]:
            assert entry.startswith("source_data/")
            assert (content / entry).is_file()

    def test_no_path_escapes_content(self):
        """A path climbing out of content/ would break the runtime's seal."""
        example = EXAMPLE_FACTORY.create(FIGURE_EXAMPLE, "figure")
        paths = [p["path"] for p in example.input_parts() if p["kind"] == "image"]
        paths += example.supporting_files()["source_data"]
        for entry in paths:
            assert not entry.startswith("/")
            assert ".." not in entry.split("/")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_example_inputs.py -q`
Expected: FAIL — `AttributeError: 'FigureExample' object has no attribute 'input_parts'`

- [ ] **Step 3: Add the abstract methods to `Example`**

In `soda_mmqc/core/examples.py`, inside `class Example(ABC)`, after
`prepare_model_input`:

```python
    @abstractmethod
    def input_parts(self) -> List[Dict[str, Any]]:
        """This example's content, in order, as provider-neutral parts.

        What an example *is* -- a caption and a figure, or a manuscript -- is
        a fact about the example class, and stating it in one place is what
        keeps format assumptions from settling in machinery that is supposed
        to be example-class neutral.

        The vocabulary is deliberately tiny and names no provider:

        ``{"kind": "text", "text": str}``
            Literal text. It may be derived -- ``WordExample`` puts its HTML
            conversion here -- because a part is a message, not a file, and
            nothing derived is ever written into a runtime.
        ``{"kind": "image", "path": str}``
            An image file, named by a path relative to this example's
            ``content/`` directory. Reading and encoding it belongs to
            whichever driver is rendering, so that base64 and media types stay
            out of this module.

        This is not :meth:`prepare_model_input`. That method builds one
        provider's payload, embeds a prompt in it, and may upload files to
        that provider; this one only says what the content is.
        """

    @abstractmethod
    def supporting_files(self) -> Dict[str, Any]:
        """Files that accompany the content without being part of it.

        A consumer that can stage files makes these available to be opened on
        demand rather than sending them up front: this figure example carries
        seven spreadsheets, and a check usually needs none of them.

        Returns:
            Role name to a content-relative path, ``None``, or a list of
            content-relative paths.
        """
```

- [ ] **Step 4: Implement on `FigureExample`**

In `FigureExample.__init__`, beside `self.image_path`:

```python
        self.caption_path: Optional[Path] = None
```

In `FigureExample.load_from_source`, retain the path (its existence is
already enforced immediately above):

```python
        self.caption_path = caption_path
```

After `_get_source_data_file_list`:

```python
    def input_parts(self) -> List[Dict[str, Any]]:
        """A figure is its caption and its image, in that order."""
        self._ensure_loaded()
        content = self.source_path / "content"
        return [
            {"kind": "text", "text": f"Figure caption:\n{self.caption}"},
            {
                "kind": "image",
                "path": self.image_path.relative_to(content).as_posix(),
            },
        ]

    def supporting_files(self) -> Dict[str, Any]:
        """Source data: available on request, not sent up front.

        Seven spreadsheets on a single figure is normal here, and a check
        usually needs none of them.
        """
        self._ensure_loaded()
        return {
            "source_data": [
                f"source_data/{name}"
                for name in self._get_source_data_file_list()
            ]
        }
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_example_inputs.py -q`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add soda_mmqc/core/examples.py tests/test_example_inputs.py
git commit -m "FigureExample states its content as provider-neutral parts"
```

---

## Task 2: `WordExample` states its content

The document problem dissolves here: the HTML `load_from_source` already
produces is text, and text is a part.

**Files:**
- Modify: `soda_mmqc/core/examples.py` (`WordExample`)
- Test: `tests/test_example_inputs.py`

**Interfaces:**
- Consumes: the abstract methods from Task 1.
- Produces: `WordExample.input_parts()` returning one text part;
  `WordExample.supporting_files()` returning the `.docx` under `manuscript`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_example_inputs.py`:

```python
WORD_EXAMPLE = "10.1038_embor.2009.217"

requires_word_example = pytest.mark.skipif(
    not (EXAMPLES_DIR / WORD_EXAMPLE).is_dir(),
    reason=f"example store has no {WORD_EXAMPLE}",
)


@requires_word_example
class TestWordExampleStatesItsContent:
    def test_the_content_is_the_converted_html(self):
        example = EXAMPLE_FACTORY.create(WORD_EXAMPLE, "word")
        parts = example.input_parts()
        assert [part["kind"] for part in parts] == ["text"]
        assert parts[0]["text"] == example.content

    def test_the_conversion_is_never_written_to_disk(self):
        """A part is a message, not a file. The example store is unchanged."""
        example = EXAMPLE_FACTORY.create(WORD_EXAMPLE, "word")
        example.input_parts()
        content = example.source_path / "content"
        assert not list(content.glob("*.html"))

    def test_the_docx_is_offered_as_a_supporting_file(self):
        example = EXAMPLE_FACTORY.create(WORD_EXAMPLE, "word")
        supporting = example.supporting_files()
        assert supporting["manuscript"].endswith(".docx")
        content = example.source_path / "content"
        assert (content / supporting["manuscript"]).is_file()

    def test_nothing_here_assumes_an_image(self):
        example = EXAMPLE_FACTORY.create(WORD_EXAMPLE, "word")
        assert all(p["kind"] == "text" for p in example.input_parts())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_example_inputs.py -q -k Word`
Expected: FAIL — `TypeError: Can't instantiate abstract class WordExample`

- [ ] **Step 3: Implement on `WordExample`**

After `WordExample.prepare_model_input`:

```python
    def input_parts(self) -> List[Dict[str, Any]]:
        """A manuscript is its text.

        ``load_from_source`` already converted the document to HTML; that
        conversion is a rendering of this example's content, not a file the
        example is made of, so it travels as a part and is never written
        anywhere.
        """
        self._ensure_loaded()
        return [{"kind": "text", "text": self.content}]

    def supporting_files(self) -> Dict[str, Any]:
        """The document itself, for a consumer that can offer files."""
        self._ensure_loaded()
        content = self.source_path / "content"
        return {
            "manuscript": self.word_file_path.relative_to(content).as_posix()
        }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_example_inputs.py -q`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add soda_mmqc/core/examples.py tests/test_example_inputs.py
git commit -m "WordExample states its content: the HTML travels as a part"
```

---

## Task 3: Render neutral parts into each provider's shape

**Files:**
- Create: `soda_mmqc/agentic_render.py`
- Test: `tests/test_agentic_render.py` (create)

**Interfaces:**
- Consumes: the part vocabulary from Task 1.
- Produces:
  - `render_anthropic(parts, root) -> List[Dict[str, Any]]` — Anthropic content
    blocks.
  - `render_openai(parts, root) -> List[Dict[str, Any]]` — Chat Completions
    content parts.
  - Both take `root: Path`, the directory that `path` values are relative to.

- [ ] **Step 1: Write the failing test**

Create `tests/test_agentic_render.py`:

```python
"""Neutral parts in, one provider's vocabulary out. Nothing else knows both."""

import base64

import pytest

from soda_mmqc.agentic_render import render_anthropic, render_openai

PNG = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
    b"IQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def root(tmp_path):
    (tmp_path / "fig.png").write_bytes(PNG)
    return tmp_path


PARTS = [
    {"kind": "text", "text": "Figure caption:\nA and B."},
    {"kind": "image", "path": "fig.png"},
]


class TestAnthropicRendering:
    def test_text_becomes_a_text_block(self, root):
        blocks = render_anthropic(PARTS, root)
        assert blocks[0] == {"type": "text", "text": "Figure caption:\nA and B."}

    def test_image_becomes_a_base64_source_block(self, root):
        blocks = render_anthropic(PARTS, root)
        assert blocks[1]["type"] == "image"
        source = blocks[1]["source"]
        assert source["type"] == "base64"
        assert source["media_type"] == "image/png"
        assert base64.b64decode(source["data"]) == PNG


class TestOpenAIRendering:
    def test_text_becomes_a_text_part(self, root):
        parts = render_openai(PARTS, root)
        assert parts[0] == {"type": "text", "text": "Figure caption:\nA and B."}

    def test_image_becomes_a_data_uri(self, root):
        parts = render_openai(PARTS, root)
        assert parts[1]["type"] == "image_url"
        url = parts[1]["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")
        assert base64.b64decode(url.split(",", 1)[1]) == PNG


class TestRenderingRefusesWhatItCannotRender:
    def test_an_unknown_kind_is_an_error(self, root):
        with pytest.raises(ValueError, match="unknown part kind 'video'"):
            render_anthropic([{"kind": "video", "path": "x"}], root)

    def test_a_path_outside_the_root_is_refused(self, root):
        with pytest.raises(ValueError, match="outside"):
            render_openai([{"kind": "image", "path": "../escape.png"}], root)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_agentic_render.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'soda_mmqc.agentic_render'`

- [ ] **Step 3: Write the renderer**

Create `soda_mmqc/agentic_render.py`:

```python
"""Render an example's neutral input parts into one provider's vocabulary.

`Example` states what its content is without naming a provider; this module
is the only place that knows what Anthropic content blocks and OpenAI Chat
Completions parts look like. Keeping the translation here is what lets a new
example class be added without touching either driver, and a new driver
without touching `core/examples.py`.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence

__all__ = ["render_anthropic", "render_openai"]


def _resolve(root: Path, relative: str) -> Path:
    """Resolve one part's path, refusing anything outside `root`.

    A part comes from an example's own account of itself, but it addresses a
    file inside a sealed runtime, and the seal is only a seal if it is checked
    at the boundary rather than trusted.
    """
    resolved = (root / relative).resolve()
    if root.resolve() not in resolved.parents and resolved != root.resolve():
        raise ValueError(
            f"Input part path {relative!r} resolves outside {root}"
        )
    if not resolved.is_file():
        raise FileNotFoundError(f"Input part names no file: {resolved}")
    return resolved


def _image_payload(root: Path, relative: str) -> tuple[str, str]:
    path = _resolve(root, relative)
    media_type = mimetypes.guess_type(path.name)[0] or "image/png"
    return media_type, base64.b64encode(path.read_bytes()).decode()


def render_anthropic(
    parts: Sequence[Mapping[str, Any]], root: Path
) -> List[Dict[str, Any]]:
    """Neutral parts to Anthropic content blocks."""
    blocks: List[Dict[str, Any]] = []
    for part in parts:
        kind = part.get("kind")
        if kind == "text":
            blocks.append({"type": "text", "text": part["text"]})
        elif kind == "image":
            media_type, data = _image_payload(root, part["path"])
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": data,
                    },
                }
            )
        else:
            raise ValueError(f"unknown part kind {kind!r}")
    return blocks


def render_openai(
    parts: Sequence[Mapping[str, Any]], root: Path
) -> List[Dict[str, Any]]:
    """Neutral parts to OpenAI Chat Completions content parts."""
    rendered: List[Dict[str, Any]] = []
    for part in parts:
        kind = part.get("kind")
        if kind == "text":
            rendered.append({"type": "text", "text": part["text"]})
        elif kind == "image":
            media_type, data = _image_payload(root, part["path"])
            rendered.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{data}"},
                }
            )
        else:
            raise ValueError(f"unknown part kind {kind!r}")
    return rendered
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_agentic_render.py -q`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add soda_mmqc/agentic_render.py tests/test_agentic_render.py
git commit -m "Render neutral input parts into Anthropic and OpenAI shapes"
```

---

## Task 4: The harness pushes the content and stages the rest

This is the task that deletes the figure-specific machinery.

**Files:**
- Modify: `soda_mmqc/cli.py` — `RuntimeLayout` (~1385); delete
  `_resolve_staged_inputs` (1473-1520); rewrite `_write_input_manifest`
  (1523-1545); `assemble_runtime` (~1547-1650); `_session_prompt` (2158-2170);
  delete `_assert_the_session_read_the_figure` (2236-2267) and its caller;
  `_default_client` (2131-2156); the session call site (~2309)
- Modify: `soda_mmqc/config.py` — delete `AGENTIC_IMAGE_EXTENSIONS` (261)
- Modify: `soda_mmqc/agentic_openai.py` — user message takes a part list (~292)
- Modify: `tests/test_agentic_cli.py`

**Interfaces:**
- Consumes: `Example.input_parts()`, `Example.supporting_files()`,
  `render_anthropic`, `render_openai`.
- Produces:
  - `RuntimeLayout.input_parts: Tuple[Mapping[str, Any], ...]` — neutral parts
    with `path` values rebased to runtime-root-relative.
  - `_session_message(layout) -> List[Dict[str, Any]]` — the instruction part
    followed by the example's parts. Replaces `_session_prompt`.
  - Client contract change: a client is called with
    `(parts: Sequence[Mapping[str, Any]], options)` instead of `(prompt: str, options)`.

**Why the layout carries the parts:** `RuntimeLayout` deliberately keeps no
link back to the skill store or the benchmark, so nothing downstream can
rebuild the `Example` — it has no `example_class`. Assembly is the one place
that knows checklist, check and example at once.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_agentic_cli.py`:

```python
@requires_subpanel_figure
class TestTheContentIsPushedNotPulled:
    def test_the_layout_carries_the_examples_parts(self, assembled):
        kinds = [part["kind"] for part in assembled.input_parts]
        assert kinds == ["text", "image"]

    def test_image_parts_are_rebased_onto_the_runtime(self, assembled):
        image = next(p for p in assembled.input_parts if p["kind"] == "image")
        assert image["path"].startswith(f"{cli.AGENTIC_INPUT_SUBDIR}/")
        assert (assembled.root / image["path"]).is_file()

    def test_the_session_message_leads_with_the_instruction(self, assembled):
        message = cli._session_message(assembled)
        assert message[0]["kind"] == "text"
        assert PILOT_LEAF in message[0]["text"]
        assert "figure" not in message[0]["text"].lower()
        assert message[1:] == list(assembled.input_parts)

    def test_the_manifest_names_supporting_files_only(self, assembled):
        manifest = json.loads(
            (
                assembled.input_root / cli.AGENTIC_INPUT_MANIFEST_FILENAME
            ).read_text(encoding="utf-8")
        )
        assert set(manifest) == {"source_data"}
        for entry in manifest["source_data"]:
            assert (assembled.root / entry).is_file()

    def test_the_read_gate_is_gone(self):
        """An input in the opening message cannot go unread."""
        assert not hasattr(cli, "_assert_the_session_read_the_figure")
        assert not hasattr(cli, "_resolve_staged_inputs")
        assert not hasattr(cli, "AGENTIC_IMAGE_EXTENSIONS")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_agentic_cli.py -q -k TheContentIsPushedNotPulled`
Expected: FAIL — `AttributeError: 'RuntimeLayout' object has no attribute 'input_parts'`

- [ ] **Step 3: Extend `RuntimeLayout`**

In `soda_mmqc/cli.py`, after `example: str`:

```python
    #: The example's content, as provider-neutral parts, with `path` values
    #: rebased onto this runtime. Resolved at assembly because the layout
    #: deliberately keeps no link back to the benchmark that names the
    #: example class.
    input_parts: Tuple[Mapping[str, Any], ...] = ()
```

- [ ] **Step 4: Replace discovery with delegation**

Delete `_resolve_staged_inputs` entirely. Replace `_write_input_manifest`:

```python
def _resolve_example(checklist: str, check: str, example: str) -> Example:
    """Build the `Example` for one benchmark entry.

    Raises:
        ValueError: If the check's benchmark declares no ``example_class``.
    """
    benchmark = _read_json(
        resolve_check_dir(checklist, check) / "benchmark.json"
    )
    example_class = benchmark.get("example_class")
    if not example_class:
        raise ValueError(
            f"No example_class in {checklist}/{check}/benchmark.json. The "
            "harness cannot state this example's input without knowing what "
            "kind of example it is, and it must not guess from extensions."
        )
    return EXAMPLE_FACTORY.create(example, example_class)


def _rebase_into_input(value: Any) -> Any:
    """Move one content-relative path onto the runtime's `input/`."""
    if value is None:
        return None
    if isinstance(value, str):
        return f"{AGENTIC_INPUT_SUBDIR}/{value}"
    if isinstance(value, list):
        return [_rebase_into_input(item) for item in value]
    raise TypeError(
        f"paths must be str, None or list of str; got {type(value).__name__}"
    )


def _rebase_parts(
    parts: Sequence[Mapping[str, Any]]
) -> Tuple[Mapping[str, Any], ...]:
    """Rebase image parts onto the runtime; text parts pass through."""
    rebased = []
    for part in parts:
        if part["kind"] == "image":
            rebased.append({**part, "path": _rebase_into_input(part["path"])})
        else:
            rebased.append(dict(part))
    return tuple(rebased)


def _write_input_manifest(source_root: Path, staged: Example) -> None:
    """Write `input/inputs.json`, naming the files the session may open.

    The example's *content* is not here -- it is in the opening message, so
    it cannot be missed. What remains are files the session may want and
    usually does not: this figure example carries seven spreadsheets, and
    most checks open none of them. That is the whole argument for leaving
    them as files. It is not an argument about *when* something enters
    context -- a file that is read stays in the history exactly as a pushed
    part does -- but about the ones that are never read at all, which cost
    nothing.

    The session has no shell, no glob and no directory listing, so a file
    this does not name is one it can only guess at.
    """
    manifest = {
        role: _rebase_into_input(value)
        for role, value in staged.supporting_files().items()
    }
    path = source_root / AGENTIC_INPUT_SUBDIR / AGENTIC_INPUT_MANIFEST_FILENAME
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
```

Extend the existing import on `cli.py:80` to
`from soda_mmqc.core.examples import EXAMPLE_FACTORY, Example`.

- [ ] **Step 5: Wire it into `assemble_runtime`**

Before the `try:` block:

```python
    staged_example = _resolve_example(checklist, check, example)
```

Replace `_write_input_manifest(staging)` with
`_write_input_manifest(staging, staged_example)`, and add to the
`RuntimeLayout(...)` construction:

```python
            input_parts=_rebase_parts(staged_example.input_parts()),
```

- [ ] **Step 6: Replace the prompt with a message**

Replace `_session_prompt` with:

```python
def _session_message(layout: RuntimeLayout) -> List[Dict[str, Any]]:
    """The request handed to the session: an instruction, then the content.

    It names the entry point and does **not** name the entry point's
    dependencies or order them: reaching them is the agent's job, and
    supplying a closure here would make the trace a measurement of this
    string rather than of the skills' prose.

    The example's content follows the instruction rather than waiting in a
    file. A session cannot fail to fetch what it was already given, which is
    why this plan deletes the gate that used to check.
    """
    instruction = {
        "kind": "text",
        "text": (
            f"Apply the `{layout.entry_point}` check to the example below, "
            f"and answer with the structured output you were given a schema "
            f"for. Supporting files, if any, are named in "
            f"{AGENTIC_INPUT_SUBDIR}/{AGENTIC_INPUT_MANIFEST_FILENAME}."
        ),
    }
    return [instruction, *(dict(part) for part in layout.input_parts)]
```

Delete `_assert_the_session_read_the_figure` and its call in
`_run_agent_session`.

- [ ] **Step 7: Render at each driver boundary**

In `_default_client`, take parts and render them into a streaming message:

```python
async def _default_client(
    parts: Sequence[Mapping[str, Any]], options: Mapping[str, Any]
):
    """Adapter over the Agent SDK's ``query()``.

    ``query`` accepts ``str | AsyncIterable[dict]``. Streaming mode is used
    because the example's content travels with the request, and content
    blocks are how an image gets into an opening message.
    """
    from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, query

    from soda_mmqc.agentic_render import render_anthropic

    payload = dict(options)
    raw_hooks = payload.pop("hooks", None)
    if raw_hooks:
        payload["hooks"] = {
            event: [HookMatcher(hooks=list(callbacks))]
            for event, callbacks in raw_hooks.items()
        }

    root = Path(payload["cwd"])

    async def message_stream():
        yield {
            "type": "user",
            "message": {
                "role": "user",
                "content": render_anthropic(parts, root),
            },
        }

    async for message in query(
        prompt=message_stream(), options=ClaudeAgentOptions(**payload)
    ):
        yield message
```

Change the call site from `run(_session_prompt(layout), options)` to
`run(_session_message(layout), options)`.

In `soda_mmqc/agentic_openai.py`, change the signature to
`async def client(parts, options)` and the user message to:

```python
            {"role": "user", "content": render_openai(parts, root)},
```

importing `render_openai` from `soda_mmqc.agentic_render` and taking `root`
from the runtime root the driver already knows.

- [ ] **Step 8: Delete the extension list**

Delete `AGENTIC_IMAGE_EXTENSIONS` from `soda_mmqc/config.py` and from
`cli.py`'s imports and `__all__`.

- [ ] **Step 9: Update the existing tests**

Delete the read-gate tests (search `read_the_figure` and
`_resolve_staged_inputs` in `tests/test_agentic_cli.py`; the two call sites at
~2725 and ~3219 exist only to satisfy that gate and go with it). Change fake
clients' signatures from `(prompt, options)` to `(parts, options)`.

These edits are expected: this task changes behaviour deliberately. Phase 2's
"no test edits" rule does not apply here.

- [ ] **Step 10: Run the full suite**

Run: `pytest tests/ -q`
Expected: PASS

- [ ] **Step 11: Prove the purge**

```bash
grep -niE "figure|caption|micrograph|\.png|\.webp|\.jpe?g" soda_mmqc/cli.py soda_mmqc/config.py
```

Expected: every hit is inside a docstring recounting the 2026-09-18 or
2026-09-19 incidents. Read each and confirm it is prose, not a condition, a
constant, a key or a path. One live-code hit means the task is not done.

- [ ] **Step 12: Commit**

```bash
git add soda_mmqc/cli.py soda_mmqc/config.py soda_mmqc/agentic_openai.py tests/test_agentic_cli.py
git commit -m "Push the example's content into the opening message; delete the read gate"
```

---

## Task 5: A generic `CLAUDE.md`

**Files:**
- Modify: `soda_mmqc/data/agentic/CLAUDE.md`
- Modify: `tests/test_agentic_cli.py` (~2318-2327)

**Source:** the prose of `tl_dev_agentic:soda_mmqc/agents/CLAUDE.example.md`,
which was written example-class neutral.

**Three removals:**

1. *"Open the figure image…"* — the content now arrives with the request.
2. The `artifacts/` paragraph. It calls `artifacts/` *"the only writable
   location"* while the profile grants only `Read` and `Skill`; the claim is
   false and telling a session to write where it cannot costs turns.
3. *"Read `inputs.json` first"* as the opening instruction. The content is
   already in the conversation; `inputs.json` now lists only supporting files.

- [ ] **Step 1: Write the failing test**

Replace the orientation test at ~2318:

```python
    def test_the_instructions_name_no_example_class(self, assembled):
        text = assembled.orientation_path.read_text(encoding="utf-8").lower()
        for forbidden in ("figure", "caption", "micrograph", "image"):
            assert forbidden not in text

    def test_the_instructions_describe_supporting_files(self, assembled):
        text = assembled.orientation_path.read_text(encoding="utf-8")
        assert "inputs.json" in text
        assert PILOT_LEAF not in text

    def test_the_instructions_promise_no_writable_directory(self, assembled):
        text = assembled.orientation_path.read_text(encoding="utf-8").lower()
        assert "artifacts" not in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_agentic_cli.py -q -k instructions`
Expected: FAIL — `assert 'figure' not in ...`

- [ ] **Step 3: Rewrite the file**

Replace `soda_mmqc/data/agentic/CLAUDE.md` entirely:

```markdown
# mmQC check run

You are running one quality-control check on one example from a scientific
manuscript.

## What you have

The example's content came with the request: read it there. Nothing needs to
be found or opened before you can start.

- `input/inputs.json` — supporting files, if this example has any, and the
  exact path of each. They are available if you need them; most checks do
  not.
- `input/` — those files, under their original names.

Paths outside this directory are not available and not needed. There is no
shell, no file search and no directory listing: if a file matters,
`inputs.json` names it.

## How to work

1. Follow the skill you were dispatched with. If it names another skill,
   invoke that skill rather than reimplementing what it does.
2. Answer with the structured output you were given a schema for. Report what
   you observe; do not guess to fill a field.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_agentic_cli.py tests/test_agentic_integration.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add soda_mmqc/data/agentic/CLAUDE.md tests/test_agentic_cli.py
git commit -m "Generic runtime instructions: content arrives with the request"
```

---

## Task 6: Prove the harness is example-class agnostic

Everything before this could pass while still being figure-only by accident.

**Files:**
- Test: `tests/test_agentic_cli.py` (new class)

- [ ] **Step 1: Write the test**

```python
WORD_EXAMPLE = "10.1038_embor.2009.217"

requires_word_example = pytest.mark.skipif(
    not (EXAMPLES_DIR / WORD_EXAMPLE).is_dir(),
    reason=f"example store has no {WORD_EXAMPLE}",
)


@requires_word_example
class TestANonFigureExampleAssembles:
    """Before this phase `_resolve_staged_inputs` raised on any example
    without a known image extension, so `doc-checklist` could never have run
    agentically whatever its skills said."""

    @pytest.fixture
    def word_checklist(self, tmp_path, monkeypatch):
        root = tmp_path / "checklists"
        check_dir = root / "doc-pilot" / "section-order"
        (check_dir / "v1").mkdir(parents=True)
        (check_dir / "v1" / "SKILL.md").write_text(
            _skill_md("section-order"), encoding="utf-8"
        )
        (check_dir / "benchmark.json").write_text(
            json.dumps(
                {
                    "name": "section-order",
                    "example_class": "word",
                    "examples": [WORD_EXAMPLE],
                }
            ),
            encoding="utf-8",
        )
        (check_dir / "schema.json").write_text(
            json.dumps(
                {
                    "format": {
                        "type": "json_schema",
                        "name": "section-order",
                        "schema": {"type": "object", "properties": {}},
                    }
                }
            ),
            encoding="utf-8",
        )
        (check_dir / "eval-manifest.json").write_text(
            json.dumps({"checklist": "section-order", "fields": {}}),
            encoding="utf-8",
        )
        (root / "doc-pilot" / "version-manifest.yaml").write_text(
            "checklist: doc-pilot\nskills:\n  section-order: v1\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(cli, "CHECKLIST_DIR", root)
        return root

    def test_a_word_example_assembles(self, word_checklist, tmp_path):
        layout = cli.assemble_runtime(
            "doc-pilot", "section-order", WORD_EXAMPLE,
            root=tmp_path / "runtime",
        )
        assert [p["kind"] for p in layout.input_parts] == ["text"]
        assert "<" in layout.input_parts[0]["text"]  # the HTML conversion

    def test_the_document_is_offered_as_a_supporting_file(
        self, word_checklist, tmp_path
    ):
        layout = cli.assemble_runtime(
            "doc-pilot", "section-order", WORD_EXAMPLE,
            root=tmp_path / "runtime",
        )
        manifest = json.loads(
            (
                layout.input_root / cli.AGENTIC_INPUT_MANIFEST_FILENAME
            ).read_text(encoding="utf-8")
        )
        assert (layout.root / manifest["manuscript"]).is_file()

    def test_the_staged_copy_is_identical_to_the_source(
        self, word_checklist, tmp_path
    ):
        """The runtime is a copy, not a processed copy: the HTML conversion
        travels in the message and is never written here."""
        layout = cli.assemble_runtime(
            "doc-pilot", "section-order", WORD_EXAMPLE,
            root=tmp_path / "runtime",
        )
        source = EXAMPLES_DIR / WORD_EXAMPLE / "content"
        staged = sorted(
            p.relative_to(layout.input_root)
            for p in layout.input_root.rglob("*")
            if p.is_file() and p.name != cli.AGENTIC_INPUT_MANIFEST_FILENAME
        )
        original = sorted(
            p.relative_to(source) for p in source.rglob("*") if p.is_file()
        )
        assert staged == original
        for entry in original:
            assert (layout.input_root / entry).read_bytes() == (
                source / entry
            ).read_bytes()
```

- [ ] **Step 2: Run it**

Run: `pytest tests/test_agentic_cli.py -q -k ANonFigureExample`
Expected: PASS. If it fails, the cause is in Task 4 — fix there, not here.

- [ ] **Step 3: Run everything**

Run: `pytest tests/ -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_agentic_cli.py
git commit -m "Prove a word example assembles and its content is its HTML"
```

---

# Phase 2 — the `agentic/` package

No behaviour change. Each task moves one cohesive group out of `cli.py`,
leaves a re-export behind, and is verified by the existing suite passing
**unedited**.

**The re-export rule.** `tests/test_agentic_cli.py` and
`tests/test_agentic_integration.py` reach ~50 names through `cli.<name>`, and
`soda_mmqc/scripts/run.py` imports `main`. Keeping `__all__` intact makes each
move verifiable by a green suite rather than by reading a 3000-line diff.

## Task 7: Create the package and move the skill model

- [ ] **Step 1: Record the baseline**

Run: `pytest tests/test_agentic_cli.py tests/test_agentic_integration.py -q`
Expected: PASS. Note the test count; it must not change in Phase 2.

- [ ] **Step 2: Create the package**

```bash
mkdir -p soda_mmqc/agentic
```

`soda_mmqc/agentic/__init__.py`:

```python
"""The agentic harness: skills, pinning, runtime, rendering, sessions, runs.

Deliberately empty of re-exports, so that an import line names the layer
being used.
"""
```

- [ ] **Step 3: Move the skill model**

Move into `soda_mmqc/agentic/skills.py`, unchanged: `SKILL_FILENAME`,
`_VERSION_DIR`, `_FRONTMATTER`, `_LIST_KEYS`, `SKILL_TOOL`, `Skill`,
`load_skill`, `_required_string`, `_name_list`, `load_skills`, `build_graph`,
`find_cycle`, `invoked_skills`, `_mentions`, `_prose_blocks`,
`_without_self_edges`, `validate_skills`, `select_versions`,
`owns_evaluation_contracts`, `list_checks`, `resolve_check_dir`.

- [ ] **Step 4: Re-export from `cli.py`**

```python
from soda_mmqc.agentic.skills import (  # noqa: F401  (compatibility surface)
    Skill,
    load_skill,
    load_skills,
    build_graph,
    find_cycle,
    invoked_skills,
    validate_skills,
    select_versions,
    resolve_check_dir,
)
```

- [ ] **Step 5: Verify**

Run: `pytest tests/test_agentic_cli.py tests/test_agentic_integration.py -q`
Expected: PASS, same count as Step 1, zero test edits.

- [ ] **Step 6: Commit**

```bash
git add soda_mmqc/agentic soda_mmqc/cli.py
git commit -m "Move the skill model into soda_mmqc/agentic/skills.py"
```

---

## Task 8: Move version pinning

- [ ] **Step 1: Move the definitions**

Into `soda_mmqc/agentic/pinning.py`: `VERSION_MANIFEST_FILENAME`,
`MODEL_DEFAULTS_FILENAME`, `SkillSetEntry`, `SkillSet`, `skill_content_hash`,
`resolve_skill_set`, `load_version_manifest`, `validate_version_manifest`,
`checklist_pins`, `ModelDefaults`, `load_model_defaults`, `expand_skill_sets`.
It imports `Skill` from `.skills`.

- [ ] **Step 2: Re-export from `cli.py`**

```python
from soda_mmqc.agentic.pinning import (  # noqa: F401
    VERSION_MANIFEST_FILENAME,
    MODEL_DEFAULTS_FILENAME,
    SkillSet,
    SkillSetEntry,
    ModelDefaults,
    skill_content_hash,
    resolve_skill_set,
    load_version_manifest,
    validate_version_manifest,
    checklist_pins,
    load_model_defaults,
    expand_skill_sets,
)
```

- [ ] **Step 3: Verify**

Run: `pytest tests/test_agentic_cli.py tests/test_agentic_integration.py -q`
Expected: PASS, same count.

- [ ] **Step 4: Commit**

```bash
git add soda_mmqc/agentic/pinning.py soda_mmqc/cli.py
git commit -m "Move version pinning into soda_mmqc/agentic/pinning.py"
```

---

## Task 9: Move the generated views

- [ ] **Step 1: Move the definitions**

Into `soda_mmqc/agentic/views.py`: `DAG_FILENAME`,
`GENERATED_README_FILENAME`, `render_dag`, `render_readme`, `graph_checklist`
and their private helpers.

The generated banners embed `python -m soda_mmqc.cli graph …`. Leave them
exactly as they are: the CLI entry point is unchanged by this move, and
editing them would make every committed `dag.yaml` and generated `README.md`
drift, failing `graph <checklist>` on all four checklists.

- [ ] **Step 2: Re-export from `cli.py`**

```python
from soda_mmqc.agentic.views import (  # noqa: F401
    DAG_FILENAME,
    GENERATED_README_FILENAME,
    render_dag,
    render_readme,
    graph_checklist,
)
```

- [ ] **Step 3: Verify the views did not drift**

```bash
pytest tests/test_agentic_cli.py tests/test_agentic_integration.py -q
for c in fig-checklist fig-checklist-exp01; do
  python -m soda_mmqc.cli graph "$c" || echo "DRIFT in $c"
done
```

Expected: PASS, and both report *"generated views are in sync"*.

- [ ] **Step 4: Commit**

```bash
git add soda_mmqc/agentic/views.py soda_mmqc/cli.py
git commit -m "Move dag/README generation into soda_mmqc/agentic/views.py"
```

---

## Task 10: Move runtime assembly, rendering, and `CLAUDE.md`

- [ ] **Step 1: Move the definitions**

Into `soda_mmqc/agentic/runtime.py`: `RuntimeLayout`,
`_resolve_example_input_dir`, `_copy_skill`, `_resolve_example`,
`_rebase_into_input`, `_rebase_parts`, `_write_input_manifest`,
`assemble_runtime`, `_assert_sealed`, `session_options`,
`effective_session_options`, `describe_permission_profile`,
`runtime_skill_set`, `session_cache_key`, `EXAMPLE_INPUT_SUBDIR`.

```bash
git mv soda_mmqc/agentic_render.py soda_mmqc/agentic/render.py
```

`tests/test_agentic_render.py` keeps its path; change only its import to
`from soda_mmqc.agentic.render import render_anthropic, render_openai`. That
is the one test edit Phase 2 permits, because the module's import path is
what moved — it is not a behaviour change. Update the two other import sites
(`cli.py`, `agentic_openai.py`) the same way.

- [ ] **Step 2: Move the orientation template beside the code that copies it**

```bash
git mv soda_mmqc/data/agentic/CLAUDE.md soda_mmqc/agentic/CLAUDE.md
rmdir soda_mmqc/data/agentic
```

In `soda_mmqc/config.py`:

```python
#: Template copied verbatim into each runtime as `CLAUDE.md`. It lives beside
#: the harness rather than under `data/` because it is what dictates the
#: agent's general behaviour, not a data asset a checklist owns.
AGENTIC_CLAUDE_TEMPLATE = Path(__file__).resolve().parent / "agentic" / "CLAUDE.md"
```

- [ ] **Step 3: Confirm it is still installed as package data**

No `pyproject.toml` edit is needed: the build is Hatch and
`[tool.hatch.build.targets.wheel]` declares `packages = ["soda_mmqc"]`, which
ships every file under the package directory, not only `*.py` — the same
mechanism that already carries `soda_mmqc/data/`. Confirm:

```bash
python -c "
from soda_mmqc.config import AGENTIC_CLAUDE_TEMPLATE as t
print(t, t.is_file())
"
```

Expected: a path ending `soda_mmqc/agentic/CLAUDE.md`, and `True`.

- [ ] **Step 4: Re-export from `cli.py`**

```python
from soda_mmqc.agentic.runtime import (  # noqa: F401
    RuntimeLayout,
    assemble_runtime,
    session_options,
    effective_session_options,
    describe_permission_profile,
    runtime_skill_set,
    session_cache_key,
)
```

- [ ] **Step 5: Verify**

```bash
pytest tests/test_agentic_cli.py tests/test_agentic_integration.py -q
python -m soda_mmqc.cli assemble fig-checklist-exp01 \
  --check micrograph-scale-bar \
  --example "10.1038_s44318-026-00715-1/content/1"
```

Expected: PASS, and a permission profile printed without error.

- [ ] **Step 6: Commit**

```bash
git add -A soda_mmqc/agentic soda_mmqc/cli.py soda_mmqc/config.py
git commit -m "Move runtime assembly, rendering and CLAUDE.md into soda_mmqc/agentic/"
```

---

## Task 11: Move the session and the runner; leave `cli.py` as the CLI

- [ ] **Step 1: Move the session layer**

Into `soda_mmqc/agentic/session.py`: `runtime_session`, `_run_agent_session`,
`_session_message`, `_default_client`, `SkillTraceRecorder`, `ToolAuditLog`,
`make_pretooluse_hook`, `interactive_approver`, `TOOL_AUDIT_FILENAME`,
`SKILL_SET_FILENAME`, `SKILL_TRACE_FILENAME`, `validate_against_schema`,
`compare_declared_and_observed`, `validate_intermediates`,
`_extract_result_text`.

```bash
git mv soda_mmqc/agentic_openai.py soda_mmqc/agentic/openai_driver.py
```

- [ ] **Step 2: Move the runner**

Into `soda_mmqc/agentic/runner.py`: `run_check_mock`, `run_check_live`,
`run_checklist_live`, `default_predictions_dir`, `PREDICTION_FILENAME`,
`INTERMEDIATES_DIRNAME`, `DEFAULT_RUN_LABEL`, `_expand_example_selectors`.

- [ ] **Step 3: Re-export both from `cli.py`**

```python
from soda_mmqc.agentic.session import (  # noqa: F401
    runtime_session,
    SkillTraceRecorder,
    ToolAuditLog,
    make_pretooluse_hook,
    interactive_approver,
    validate_against_schema,
    compare_declared_and_observed,
    validate_intermediates,
    TOOL_AUDIT_FILENAME,
    SKILL_SET_FILENAME,
    SKILL_TRACE_FILENAME,
)
from soda_mmqc.agentic.runner import (  # noqa: F401
    run_check_mock,
    run_check_live,
    run_checklist_live,
    default_predictions_dir,
    INTERMEDIATES_DIRNAME,
)
```

- [ ] **Step 4: Verify `cli.py` is now the CLI surface**

```bash
pytest tests/ -q
wc -l soda_mmqc/cli.py soda_mmqc/agentic/*.py
```

Expected: PASS with Task 7's baseline count, and `cli.py` reduced to its
`argparse` parser, `main`, `score_check`, prediction loading and re-exports.

- [ ] **Step 5: End-to-end smoke test**

```bash
python -m soda_mmqc.cli graph fig-checklist
python -m soda_mmqc.cli graph fig-checklist-exp01
python -m soda_mmqc.cli assemble fig-checklist-exp01 \
  --check micrograph-scale-bar \
  --example "10.1038_s44318-026-00715-1/content/1"
```

Expected: both graphs in sync; assemble prints a profile.

- [ ] **Step 6: Commit**

```bash
git add soda_mmqc/agentic soda_mmqc/cli.py
git commit -m "Move the session and runner into soda_mmqc/agentic/; cli.py is the CLI"
```

---

## Consequences for exp-01

`fig-checklist-exp01` is built and validated but unrun, and its
preregistration note is unwritten. Phase 1 changes what the agent sees — the
content now arrives with the request, `CLAUDE.md` is rewritten, and the read
gate is gone — so any run before it lands would measure a runtime that no
longer exists.

**exp-01 preregisters after Phase 2.** Nothing is lost by waiting: the commit
ordering that makes preregistration checkable is the note before the runs, not
the note before the refactor.

One confound leaves the experiment. Under pull, a minimal skill could lose
because its prose never told the agent to open the figure — a failure of
navigation rather than of judgement. With the content in the opening message
both arms see the figure unconditionally, so what differs between them is
only what the plan says the independent variable is.

## Open questions for review

1. **Does the model behave differently with content handed to it?** Not a
   cost question: a pulled image does not enter context and leave. Once the
   tool result carrying it is in the message history, every later turn
   resends that history, so a pulled image occupies context for the rest of
   the session exactly as a pushed one does. The only difference is the one
   to three turns before the pull, and it favours pushing on two further
   counts — the opening message is a stable prefix, which is the best case
   for prompt caching, and it guarantees exactly one copy where a pulled
   image can be re-read into the history more than once.

   What is genuinely unknown is behavioural. A model given the figure may
   reason about it differently from one that went and fetched it, and the
   direction is not predictable from first principles. Worth a handful of
   examples run both ways before the full benchmark — the pull behaviour
   stays in git — comparing decisions rather than tokens.
2. **`input_parts` overlaps `prepare_model_input`.** Both know that a figure
   is a caption and an image. `prepare_model_input` stays untouched here
   because it is the legacy path's contract and rewriting it is not this
   plan's job, but the duplication is real: a third consumer would make it
   worse. Unifying them — legacy rendering neutral parts the way the agentic
   drivers do — is the obvious follow-up, and is not scheduled.
3. **The re-export façade.** Phase 2 keeps `cli.py` re-exporting ~50 names so
   the suite verifies each move. Should a later task update the tests to
   import from the new modules and drop the façade, or is a thin
   compatibility surface worth keeping?
4. **`doc-checklist` still has no `SKILL.md`.** Task 6 proves a word example
   assembles and that its content reaches the model as HTML. Converting
   `doc-checklist`'s checks to skills is separate work, not scheduled here —
   but after this plan it is the only thing standing in the way.
