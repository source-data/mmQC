---
title: The harness in mmqc_utils — implementation plan
date: 2026-10-23
status: planned
---

# The harness in `mmqc_utils` — implementation plan

**Goal:** soda-curation can install `mmqc-utils[agentic]` and run a
structured checklist exactly as mmQC benchmarks it:

- the same harness;
- the same message built from the same source files;
- the same skills, published to Langfuse.

**Background:** the reasoning, the vocabulary and the open decisions are in
[`harness-production-integration.md`](../harness-production-integration.md).
This plan is the schedule; that note is the reasoning. Read it before
starting a milestone.

**Scope:** mmQC and `mmqc_utils` only. The changes in soda-curation are a
handover brief (Milestone 6), not work done here.

**Non-goals:**

- staged files opened during a session (they come with `ref-checklist`);
- new input kinds (Word, Excel, CSV, code), until a checklist needs them;
- guideline reviews;
- the OpenAI driver's structured-output defect
  ([`openai-agentic-structured-output.md`](../openai-agentic-structured-output.md)).

## Delivery order

The riskiest part is the refactor that makes the harness independent of
mmQC, not the move into `mmqc_utils`. Done inside mmQC first, it is covered
by the existing 972 tests, and mmQC is its first caller. The move afterwards
is then mechanical.

| # | Milestone | Leaves behind |
|---|---|---|
| 0 | mmQC runs the in-repo `mmqc_utils` | one source of conversion code, its effect on outputs known |
| 1 | The seam: assembly takes content and a checklist path | a harness with no reference to `EXAMPLES_DIR`, `EXAMPLE_FACTORY` or `benchmark.json` |
| 2 | Configuration as an object; no import-time effects | a harness that can be imported by an application |
| 3 | Move into `mmqc_utils.agentic` | `mmqc-utils[agentic]` 0.4.0, used by mmQC |
| 4 | Input parity with production (exp-11) | one figure-content builder, and a benchmark that describes production |
| 5 | Skill sources and Langfuse publishing | production skills in Langfuse, loaded back with matching hashes |
| 6 | Handover to soda-curation | an integration brief and a runnable example |

Milestones 0 to 3 change no scores. Milestone 4 may change them, by design,
and is measured as an experiment. Milestone 5 is the first step visible
outside the repository.

## Gate protocol

As in [`2026-09-02-agentic-checklist-skills.md`](2026-09-02-agentic-checklist-skills.md#gate-protocol):

- Every milestone ends with an automatic gate: the full suite,
  `uv run pytest`.
- A human gate is a stop point. It names a **decision**, an **artifact**
  handed over to decide it, and what it **blocks**.
- Each decision is recorded under its milestone as it happens.

| Gate | Sits before | Decision |
|---|---|---|
| 0A | switching mmQC to the in-repo `mmqc_utils` | Are the differences from 0.3.3 to 0.3.5 in curated outputs acceptable? |
| 1A | Milestone 2 | Do assembled runtimes match the old ones byte for byte? |
| 3A | moving any code | Does the maintainer of `mmqc-utils` agree to the subpackage, the extra, and its dependencies? |
| 3B | releasing 0.4.0 | Is the public interface the one we want applications to depend on? |
| 4A | the exp-11 runs | Preregistration: hypothesis, arms, decision criterion, budget. |
| 4B | adopting re-converted images | Does the result say to switch the benchmark? |
| 5A | the first publish | Is the payload of each prompt right, and is the namespace right? Approve credentials. |
| 6A | handover | Is the brief complete enough for someone outside mmQC to integrate from? |

---

## Milestone 0: mmQC runs the in-repo `mmqc_utils`

**Why:** mmQC's environment has `mmqc-utils` **0.3.3 from PyPI**, while
`mmqc_utils/` in this repository is **0.3.5**. If the harness moves into
`mmqc_utils/` while mmQC keeps installing the PyPI release, mmQC no longer
tests what it ships. 0.3.4 added HTML post-processing to
`document_to_html`, so switching can change the HTML that `WordExample`
produces.

**Files:**

- Modify: `pyproject.toml`. Add `[tool.uv.sources] mmqc-utils = { path =
  "mmqc_utils", editable = true }`.
- Modify: `uv.lock`.

**Step 1:** Record the HTML of every `WordExample` under 0.3.3:
`doc-checklist` examples, and the documents in `data/examples/`. Store one
hash per example plus the full text, in the scratchpad.

**Step 2:** Switch to the path source. Run the suite.

**Step 3: Human gate 0A.**

- **Decision:** are the HTML differences between 0.3.3 and 0.3.5 acceptable
  for curated and benchmarked documents?
- **Artifact:** for each document whose HTML changed: a diff, and whether a
  gold field quotes text from the changed part. Quotes are aligned against
  the HTML, so a changed character can move a span.
- **Blocks:** Milestone 1.

> **Decision — 2026-10-23, Thomas Lemberger: accepted.** Removing images
> from the HTML is wanted, not merely tolerated. As model input, it also
> removes a place to hide an invisible prompt injection. The mmQC curation
> document view should not show images either. Milestone 1 may start.
>
> **Artifact produced — 2026-10-23.**
>
> **What changed in the code from 0.3.3 to 0.3.5:**
> - `images.py` was refactored and gained a `tifffile` fallback, which runs
>   only when ImageMagick fails on a TIFF.
> - `document_to_html` now always runs `postprocess_html`.
> - `quote.py` and `text.py` are identical.
>
> **Found in 0.3.4, and fixed here** (`html_cleanup.py`, with a regression
> test, CHANGELOG "Unreleased"): `postprocess_html` serialized the top-level
> nodes with `str()`, which turns `<!DOCTYPE html>` into the text `html`.
> Every converted manuscript therefore began with a stray word, and HTML
> comments lost their delimiters. Production is not affected: soda-curation
> locks 0.3.3.
>
> **Before and after, with the fix:**
>
> | | Result |
> |---|---|
> | Image conversion (`convert_to_bounded_jpeg`, `compress_to_bounded_jpeg`) | byte-identical — **see the correction below** |
> | Visible text of the 15 `.docx` examples | identical in all 15 |
> | Markup | 34 empty `<p>` removed across 12 documents |
> | `EMBOR-2025-61250V2` | 12 embedded images (`data:image`) removed, with their paragraphs: 5.6 MB → 93 KB |
> | Gold strings of 20+ characters for these documents | 480 in total; 164 appear verbatim in the text, all 164 still do; no gold stores character offsets |
>
> **For the decision:**
>
> - **The image removal is a side effect.** `remove_empty_elements` deletes
>   a `<p>` with no visible text, and a paragraph holding only an `<img>`
>   has none.
> - **As model input it is a gain.** `WordExample` sends the HTML as a
>   text part, so this manuscript sent 5.5 MB of base64 to the model.
> - **For a viewer of the HTML it is a loss.** The figures disappear
>   ([`curation-document-viewer.md`](../curation-document-viewer.md)).
> - **The maintainer should say whether it is intended.**
>
> **Correction — 2026-10-24.** The image row above was not measured on
> 2026-10-23.
>
> - **What went wrong:** mmQC's environment cannot load ImageMagick
>   without `MAGICK_HOME`. The comparison script recorded a failed
>   conversion as an error string, so it compared three identical
>   `ImportError`s and reported them as "identical".
> - **Re-measured:** with `MAGICK_HOME` set, against a genuine 0.3.3 in an
>   isolated environment. The script now fails on any error instead of
>   recording it. Over 77 sources (the 37 benchmark figures and 40
>   `mmqc_utils` test fixtures), each through `convert_to_bounded_jpeg`
>   with default and production parameters and through
>   `compress_to_bounded_jpeg`, **all 231 outputs are byte-identical.**
> - **The conclusion stands;** the evidence for it dates from today.

> **Environment changes from switching:**
>
> - `uv sync` added `tifffile` (needed by 0.3.5) and `websockets`;
> - it removed `toml` and `watchdog`, which had been installed outside the
>   lock (`watchdog` is only Streamlit's auto-reload);
> - `uv.lock` is gitignored;
> - the root suite passes: 972 passed, 7 skipped;
> - the `mmqc_utils` suite passes (83) with
>   `MAGICK_HOME=/opt/homebrew/opt/imagemagick`. Without it, 6 image tests
>   fail to load ImageMagick, before and after the fix alike.

**Automatic gate:** `uv run pytest`.

---

## Milestone 1: The seam — assembly takes content and a checklist path

**Deliverable:** runtime assembly no longer knows what a benchmark is. It
takes the checklist directory, the entry point, the content parts and the
supporting files. The benchmark runner converts a benchmark example into
that input.

**Files:**

- Modify: `soda_mmqc/agentic/runtime.py`
  - `assemble_runtime(checklist_dir, check, content, ...)`, where `content`
    is a small value type: `parts`, a `files` map (role → paths) and a
    `source_root` they are relative to;
  - drop `_resolve_example`, `_resolve_example_input_dir`, and the
    `benchmark.json` read.
- Modify: `soda_mmqc/agentic/skills.py`. `resolve_check_dir` gets a variant
  that takes a path; the name-based form stays as a thin wrapper for the
  CLI.
- Modify: `soda_mmqc/agentic/session.py` (`runtime_session`) and
  `soda_mmqc/agentic/runner.py`. The runner builds `content` from
  `EXAMPLE_FACTORY`, exactly as `_resolve_example` does today.
- Modify: `soda_mmqc/cli.py`, `tests/test_agentic_cli.py`.

**Step 1:** Write a test that assembles runtimes the old way for one figure
example and one Word example, and records each file's path and hash. Then
write the same test for the new call. Do this before changing any code.

**Step 2:** Introduce the content type and the path-based signatures. Keep
the old name-based entry points as wrappers until the CLI and tests are
moved over, then delete them. Leave nothing deprecated behind.

**Step 3:** Exclude gold from the staged files by **what is staged**, not by
the example layout. The `checks/` exclusion becomes the benchmark adapter's
job. `_assert_sealed` stays in the harness as defence in depth.

**Step 4: Human gate 1A.**

- **Decision:** are the assembled runtimes identical to before?
- **Artifact:** the Step 1 comparison across all `fig-checklist` and
  `doc-checklist` examples, plus one mock run (`mmqc run --mock`) whose
  predictions and sidecars match the previous ones byte for byte.
- **Blocks:** Milestone 2.

> **Decision — 2026-10-23, Thomas Lemberger: accepted.** Milestone 2 may
> start.
>
> **Artifact produced — 2026-10-23.**
>
> **What changed:**
>
> - `assemble_runtime(checklist_dir, check, content)` and
>   `runtime_session(...)` take the checklist's directory and an
>   `ExampleContent`. That type holds `source_root`, `parts`, `files`,
>   `label`, and `exclude`, the names the caller leaves out of the staged
>   copy.
> - `runtime.py` no longer imports `EXAMPLES_DIR`, `EXAMPLE_FACTORY` or
>   `Example`, and reads no `benchmark.json`.
> - The benchmark side is a new module,
>   [`agentic/benchmark.py`](../../soda_mmqc/agentic/benchmark.py).
>   `example_content(checklist, check, example)` finds the example under
>   `EXAMPLES_DIR`, reads `example_class` from the check's
>   `benchmark.json`, builds the parts through `EXAMPLE_FACTORY`, and
>   excludes `checks/`.
> - `skills.check_dir_in(checklist_dir, check)` is the path-based lookup;
>   `resolve_check_dir` wraps it.
> - The runner and the `assemble` command call the adapter. No name-based
>   wrapper is left in the harness.
> - `_assert_sealed` still refuses any `checks/`, whatever the caller
>   excluded.
>
> **Byte-identical runtimes.** A snapshot script recorded every runtime the
> harness assembles, before and after the change:
>
> - every `fig-checklist` check over its benchmark, 457 runtimes, closure
>   assembly;
> - `fig-checklist-exp02`'s `micrograph-scale-bar` on 5 examples, with
>   `assembly="all"`;
> - the 15 Word examples, through a one-check checklist built for the
>   snapshot.
>
> For each runtime it recorded every file's path and SHA-256, the
> directories, every layout field (input parts included), and the session
> options with the root replaced. Result: **493 runtimes and 12,238 files;
> the two JSON records are byte-identical.**
>
> The mock run (`run_check_mock`) assembles no runtime, so it does not
> exercise this change. The snapshot stands in for it.
>
> **Tests.** 972 passed, 7 skipped. The tests reach assembly through two
> helpers, `_assemble` and `_session`, which call the adapter as the runner
> does.
>
> The opt-in live test `tests/test_agentic_integration.py` was already
> broken before this milestone: it called `cli.session_options`,
> `cli._default_client` and `cli._extract_*`, which `cli` no longer has,
> and passed a prompt string where `_default_client` takes parts. It now
> imports from the modules that define them, and it is collected. It was
> not run, because it spends credit.

**Automatic gate:** `uv run pytest`.

---

## Milestone 2: Configuration as an object; no import-time effects

**Deliverable:** the harness modules import nothing from `soda_mmqc.config`
or `soda_mmqc.logger`. An application imports them without loading `.env`,
writing log files, or resolving `API_PROVIDER`.

**What moves where:**

| Today in `soda_mmqc.config` | Becomes |
|---|---|
| layout names: `AGENTIC_RUNTIME_PREFIX`, `*_SUBDIR`, `AGENTIC_ORIENTATION_FILENAME`, `AGENTIC_INPUT_MANIFEST_FILENAME` | module constants in the harness: fixed by the harness, not configurable |
| containment: `AGENTIC_BASE_TOOLS`, `AGENTIC_ALLOWED_TOOL_NAMES`, `AGENTIC_FORBIDDEN_TOOLS`, `AGENTIC_PERMISSION_MODE`, `AGENTIC_SETTING_SOURCES`, `AGENTIC_MAX_BUFFER_BYTES` | module constants in the harness. Deliberately not configurable: the boundary is a property of the harness (see the `model-defaults.yaml` rule) |
| `AGENTIC_CLAUDE_TEMPLATE` | package data next to the session module |
| `AGENTIC_RUNTIME_DIR`, `AGENTIC_DEFAULT_MODEL`, `AGENTIC_SKILLSET_WARN_THRESHOLD` | fields of a `HarnessOptions` object the caller passes. mmQC builds it from its environment variables, as now |
| `resolve_agentic_runtime_root()` | the harness keeps the cloud-sync check. The "not inside the repository" check takes the repository root as an optional argument, which mmQC passes |
| `logger` | `logging.getLogger(__name__)`; the application configures handlers |

**Files:** `soda_mmqc/agentic/*.py`, `soda_mmqc/config.py`,
`soda_mmqc/cli.py`, tests.

**Step 1:** Write a test that imports the harness modules in a subprocess
with an empty environment and a read-only working directory. It asserts
that `soda_mmqc` is not in `sys.modules` and that no file was written.

**Step 2:** Make the move in the table. Tests that patch config constants
patch the options object instead.

**Automatic gate:** `uv run pytest`, including the Step 1 test.

> **Done — 2026-10-23.** Two deviations from the steps above:
>
> - **No `HarnessOptions` object.** Of its three proposed fields, the
>   default model belongs to the runner (`resolve_model`), and the
>   skill-set warning threshold belongs to `--unpin` expansion.
>   `expand_skill_sets` now warns only when the caller passes
>   `warn_above`; the runner passes mmQC's `AGENTIC_SKILLSET_WARN_THRESHOLD`.
>   That leaves one setting, where runtimes are created, and it became the
>   `parent` argument of `assemble_runtime` and `runtime_session`. The
>   harness defaults to the system temp directory. mmQC passes
>   `resolve_agentic_runtime_root()`, which keeps the repository and
>   cloud-sync refusals in `config.py`, since only mmQC knows its
>   repository.
> - **The clean-subprocess import test waits for Milestone 3.** While the
>   modules live inside `soda_mmqc`, importing any of them runs
>   `soda_mmqc/__init__.py`, which loads `.env` and opens a log file.
>   Instead, `tests/test_harness_boundary.py` asserts by AST that
>   `skills`, `pinning`, `runtime`, `session` and `render` import nothing
>   from `soda_mmqc` outside themselves, lazy imports included. That
>   property is what makes the move mechanical.
>
> **What moved:**
>
> - **Into `runtime.py`, with their comments:** the layout and containment
>   constants (`AGENTIC_*_SUBDIR`, tools, permission mode, setting sources,
>   buffer size, `CLAUDE.md` template path).
> - **Into `config.py`, beside `list_checks`:** `resolve_check_dir` and
>   `check_dir_in`. They are mmQC's checklist lookup and require
>   `benchmark.json`.
> - **In their place, the harness checks only** that the entry point is a
>   skill of the checklist and has a `schema.json`, its answer's contract.
>   Production will publish no `benchmark.json`.
> - **Into `runner.py`:** the OpenAI client factory
>   (`_openai_session_client`), since the OpenAI driver stays in mmQC.
> - **Logging:** each harness module uses `logging.getLogger(__name__)`.
>   Under `soda_mmqc.agentic.*` these propagate to mmQC's handlers, so the
>   console and the log file are unchanged. After the move, mmQC will
>   configure `mmqc_utils.agentic`.
>
> **Checks:**
>
> - 978 passed, 7 skipped (972 plus the 6 boundary tests);
> - the gate 1A snapshot is still byte-identical (493 runtimes);
> - `mmqc assemble` logs as before.

---

## Milestone 3: Move into `mmqc_utils.agentic`

**Deliverable:** `mmqc-utils` 0.4.0 with an `agentic` subpackage behind the
`[agentic]` extra. `soda_mmqc` imports the harness from it.

**What moves:** skill loading and validation, pinning and model defaults,
runtime assembly, the Claude session (tool audit, skill trace, schema
validation), Anthropic rendering, `CLAUDE.md`.

**What stays in `soda_mmqc`:**

- `runner.py`: arms, replicates, `--unpin`, mock runs, the predictions
  layout;
- `views.py`: `dag.yaml`, README, `mmqc graph`;
- the benchmark adapter (example to content);
- the OpenAI driver, which is research-only, with an open defect, and not
  wanted by production. It plugs into the session through the client
  argument that already exists.

> **Decision — 2026-10-23, Thomas Lemberger: proceed; consult the
> maintainer when the work is done.** Nothing is published to PyPI before
> then: mmQC uses the in-repo package (Milestone 0), and the integration
> with soda-curation may still change the harness. Gate 3B still blocks
> any release.

**Step 1: Human gate 3A — the maintainer's agreement.**

- **Decision:** does the maintainer of `mmqc-utils` agree to add an
  `agentic` subpackage, an `[agentic]` extra that pins `claude-agent-sdk`
  exactly, and the dependencies `pyyaml` and `jsonschema`?
- **Artifact:** this plan, the interface sketch from Step 2, and the
  dependency list with sizes. The SDK bundles the Claude Code CLI.
- **Blocks:** everything else in this milestone.

**Step 2:** Write down the public interface in `mmqc_utils/README.md`. At
most:

- `load_checklist(source)`;
- `assemble_runtime(...)`;
- `run_session(...) -> (prediction, trace, audit)`;
- `HarnessOptions`;
- the content type;
- `skill_content_hash`.

Everything else is private.

**Step 3:** Move the modules with their tests into `mmqc_utils/tests/`.
Leave no re-export shims behind in `soda_mmqc/agentic/`; update the
imports.

**Step 4:** Make `mmqc_utils`' own tests pass without `soda_mmqc` installed,
so the package stands alone. Tests that need a real checklist use a small
fixture checklist inside `mmqc_utils/tests/fixtures/`, not `fig-checklist`.

**Step 5: Human gate 3B — the interface before release.**

- **Decision:** is this the interface applications will depend on?
- **Artifact:** the README section, the CHANGELOG entry for 0.4.0, and
  `uv run --directory mmqc_utils pytest` passing in a fresh environment
  with only the `[agentic]` extra.
- **Blocks:** publishing 0.4.0 to PyPI. Until then, mmQC uses the path
  source from Milestone 0.

**Automatic gate:** both suites. `uv run pytest` at the root, and the
`mmqc_utils` suite on its own.

> **Done to the release gate — 2026-10-23.** Gate 3A was deferred by
> decision (above), and gate 3B (release) is open. Nothing is published.
>
> **What moved:**
>
> - `skills`, `pinning`, `runtime`, `session`, `render` and `CLAUDE.md` are
>   now `mmqc_utils/src/mmqc_utils/agentic/`, moved with `git mv`.
> - The only edits were their imports and two docstrings that named mmQC
>   modules.
> - No re-export shims are left in `soda_mmqc/agentic/`. It keeps
>   `benchmark`, `runner`, `views` and `openai_driver`, and its docstring
>   says so.
>
> **Interface (Step 2):**
>
> - `mmqc_utils.agentic` re-exports the interface applications use:
>   `ExampleContent`, `RuntimeLayout`, `runtime_session`,
>   `assemble_runtime`, `run_session`, `session_options`,
>   `effective_session_options`, `validate_skills`, `call_closure`,
>   `checklist_pins`, `load_model_defaults`, `skill_content_hash`, `Skill`,
>   `SkillSet`.
> - `_run_agent_session` became `run_session`, since an application must
>   call it.
> - Documented in `mmqc_utils/README.md` with a worked example.
>   `CHANGELOG.md` records it under "Unreleased".
>
> **Packaging:**
>
> - The `agentic` extra pins `claude-agent-sdk==0.2.165`, a pin that has
>   moved from the root `pyproject.toml` so there is one, and adds
>   `jsonschema` (until now an indirect dependency) and `pyyaml`.
> - `CLAUDE.md` is package data.
> - mmQC depends on `mmqc-utils[agentic]`.
> - A wheel built from the tree contains the subpackage, the template and
>   the extra.
>
> **Logging:** mmQC attaches its console and file handlers to the
> `mmqc_utils` logger as well (`soda_mmqc/__init__.py`). The test
> fixture that lets `caplog` see `soda_mmqc` records now does the same for
> `mmqc_utils`.
>
> **Tests:**
>
> - `mmqc_utils/tests/test_agentic.py`: 16 tests on a toy checklist built
>   in the test (closure vs all, the manifest picking prose, explicit pins,
>   staging and the inputs manifest, `parent`, the entry-point schema rule,
>   refusing gold unless excluded, atomicity, teardown, the permission
>   profile, Anthropic rendering, and a session with a replaying client:
>   validated answer and trace, an answer outside the schema, a prose
>   answer).
> - `mmqc_utils/tests/test_agentic_boundary.py` (replacing the root's
>   `test_harness_boundary.py`): no harness module imports `soda_mmqc`. In a
>   subprocess with an empty environment and a `.env` in its working
>   directory, importing `mmqc_utils.agentic` writes no file, reads no
>   `.env`, loads no `soda_mmqc` and does not import the SDK. That is the
>   test Milestone 2 deferred.
> - `test_agentic_cli.py` stays at the root: it tests the harness through
>   mmQC's benchmark, and its imports now name `mmqc_utils.agentic`.
>
> **Checks:**
>
> - root suite: 972 passed, 7 skipped;
> - `mmqc_utils` suite: 107 passed, 1 skipped, in its own environment with
>   only the extra (`soda_mmqc` not installed; `MAGICK_HOME` set for the
>   image tests);
> - the gate 1A snapshot is byte-identical (493 runtimes);
> - `mmqc assemble` logs to mmQC's console and file.

---

## Milestone 4: Input parity with production (exp-11)

**Deliverable:** one function in `mmqc_utils` turns a source figure into
content parts: conversion parameters, encoding, caption-then-image order.
The benchmark and production both build their input with it, and exp-11
measures whether past scores carry over.

**The two chains today:**

- **soda-curation 3.8.2:**
  1. `convert_to_bounded_jpeg(rasterization_dpi=300, max_dimension=2048)`,
     quality 80;
  2. decoded to PIL and re-encoded as JPEG at quality 80.
- **The benchmark:** stored jpg, png or webp files, sent unchanged. How
  they were made is not recorded.

**Step 1:** Find out where the benchmark figures came from. Are the source
files (TIFF, PDF, EPS) available? Record the answer in the design note
(decision 5).

> **Step 1 finding — 2026-10-23.**
>
> **The benchmark figures are published figures, not author
> submissions.** All 37 come from journal websites:
>
> - Springer Nature's web renderings (`…_Fig1_HTML.webp`, `…_fig1_html.png`);
> - Wiley's medium-size images (`…-fig-0001-m.jpg`);
> - supplementary-material images (`…_esm.jpg`);
> - JCS PNGs.
>
> Some examples also hold the publisher's PowerPoint export. None holds a
> submitted TIFF, PDF or EPS. Production processes submissions, so its
> figures were never typeset: different labelling, layout, resolution and
> text rendering.
>
> **The encoding gap is modest.**
>
> - Stored formats: 15 png, 14 webp, 8 jpg. The longest side is
>   1419–3041 px for png, 2111–2750 px for webp, and 750–5372 px for jpg;
>   30 of 37 exceed 2048 px.
> - The API downscales anyway. Claude Sonnet 5.5 is in the
>   high-resolution tier: images are downscaled to at most 2,576 px on the
>   long edge and 4,784 visual tokens of 28×28 px (vision docs,
>   2026-10-23). The model therefore sees a median of 3.7 megapixels of a
>   benchmark figure today.
> - Through production's chain (2048 px long edge, then the API's
>   limits), it would see 0.63 to 1.00 times as many pixels (median 0.93;
>   within 2% for 13 of 37 figures). Wide figures lose most.
> - Production also compresses twice (JPEG quality 80, decoded and
>   re-encoded at 80). The vision docs warn that multiple compression
>   passes can introduce artefacts detrimental to performance.
>
> **What this means for exp-11.** Re-converting the stored images measures
> only the encoding gap: a modest resolution loss plus double compression.
> The larger gap, between published and submitted figures, can only be
> measured with the submitted files of the benchmark manuscripts. Seven of
> the eight journals are EMBO Press titles; JCS is not.

**Step 2:** Write `figure_content(source_path, caption, ...)` in
`mmqc_utils`, defaulting to production's parameters. Leave out the second
re-encode: soda-curation can drop it when it adopts the builder, so the
builder decides what production's chain becomes. Test that the output is
deterministic: same input, same bytes.

> **Decided — 2026-10-24, with Thomas Lemberger:**
>
> - The benchmark processes its figures as if they were submissions,
>   through exactly production's chain and compressed once. Some authors
>   do submit JPEGs.
> - The converted image travels in the request as bytes, not as a file
>   staged in the runtime.
> - The harness records a fingerprint of every image it sends (media type,
>   size, dimensions, SHA-256). It does not keep the image: with the hash,
>   a re-conversion can be checked, and how production shows what the
>   model saw is soda-curation's call.
> - The double compression is soda-curation's, not `mmqc_utils`':
>   `compress_to_bounded_jpeg` re-encodes from the source at each attempt.
>   An issue was drafted for soda-curation.
>
> **Step 2 done — 2026-10-24.**
>
> - **Builder:** `mmqc_utils.agentic.content`, with `figure_image_part`
>   and `figure_parts`. Production's parameters are constants there
>   (300 dpi, 2048 px, quality 80), and the source is converted once.
> - **Image parts carrying bytes:**
>   `{"kind": "image", "media_type": ..., "data": bytes}` is accepted by
>   assembly (never written into the runtime), by both renderers, and by
>   `session_cache_key` (added to the key only when present, so existing
>   keys are unchanged). An image part names a file or carries bytes,
>   exactly one of the two.
> - **Fingerprint:** `render.image_fingerprints`. `run_session` records it
>   in `tool_audit.json` under `inputs` before anything is sent, so a
>   failed session still records what the model was shown.
> - **Not yet changed:** the benchmark's `FigureExample` still sends the
>   stored file. exp-11 compares the two inputs, and gate 4B decides.
> - **Checks:** 7 new package tests (single conversion and determinism,
>   bounding, inline vs staged, the part rule, fingerprints for both
>   kinds); `mmqc_utils` 114 passed; root 972 passed; the gate 1A snapshot
>   is still byte-identical.

**Step 3: Human gate 4A — preregistration.** Write
`thinking/experiments/exp-11-input-parity.md` before any run.

- **Hypothesis:** `fig-checklist` scores on re-converted images are
  non-inferior to scores on the stored images.
- **Arms:** stored vs re-converted; replicates as in exp-10;
  concurrency 38.
- **Decision criterion:** a margin per layer, as in exp-10.
- **Budget:** stated up front.
- **Artifact:** the preregistration and a dry run (`--mock`).
- **Blocks:** the live runs.

**Step 4:** Run, score, and write the results into the experiment note and
`notebooks/experiments/exp-11-input-parity.ipynb`.

**Cleanup after exp-11 (decided 2026-10-24).** Remove the `figure-converted`
example class and the `example_class` override of `run_check_live`: they
exist only to run exp-11's converted arm. If the builder is adopted, it
becomes `FigureExample`'s image path directly.

**Step 5: Human gate 4B.**

- **Decision:** does the benchmark switch to re-converted images? If the
  scores differ, past results describe stored images, not production.
- **Artifact:** the results, per layer and per check.
- **Blocks:** making the builder the benchmark's only image path.

**Automatic gate:** `uv run pytest`.

---

## Milestone 5: Skill sources and Langfuse publishing

**Deliverable:** production skills are published from mmQC to Langfuse
under `skills/<checklist>/<skill>` with the label `production`. The harness
loads them from either the filesystem or Langfuse, with matching content
hashes.

**Files:**

- `mmqc_utils/src/mmqc_utils/agentic/sources.py`: `FilesystemSource` and
  `LangfuseSource`. Both yield the same skill and contract records, and
  everything after loading is shared.
- `soda_mmqc/data/production_prompts/production.json`: add
  `"skills": ["fig-checklist"]`.
- `.github/scripts/build_langfuse_checklist.py` and its workflow: publish
  the skills, or a script of its own (design-note decision 1).
- Tests use a fake Langfuse client. No live call is made in the suite.

**Step 1: Validation for production checklists.** These rules apply only to
checklists named in `production.json`:

- **Reachability:** every pinned skill is in `call_closure` of the single
  entry point (`do-*`).
- **Topology:** every version of a skill declares the same `requires`.

Run both from `mmqc graph` and from the publisher. `fig-checklist` passes
both today.

**Step 2: The payload.** For each pinned skill:

- **prompt text:** the whole `SKILL.md`;
- **config:** keyed by file name, as the existing publisher does:
  - `schema` and `eval-manifest` where the skill owns them;
  - `model-defaults` on the entry point;
  - `skill`: name, mmQC version, content hash, release ID (the commit SHA);
- **tags:** `entry`, `leaf` or `shared`.

Test that writing a payload back out gives a byte-identical `SKILL.md` and
`schema.json`.

**Step 3: `LangfuseSource`.** It loads `skills/<checklist>/*` at a label. If
the release IDs differ across the set, the publish is still in progress: it
retries, then refuses (design-note decision 3).

**Step 4: Human gate 5A — the first publish.**

- **Decision:** is each prompt's payload right, and is the namespace right?
  Approve the use of Langfuse credentials.
- **Artifact:** the payloads as JSON, from a dry run of the publisher, for
  all 13 skills.
- **Blocks:** the first real publish.

**Step 5:** Publish, through CI or by hand. Then verify: run a sample of the
benchmark with `LangfuseSource` and assert that every content hash equals
the filesystem's.

**Automatic gate:** both suites.

---

## Milestone 6: Handover to soda-curation

**Deliverable:** what soda-curation needs to integrate, without mmQC writing
its code.

- `mmqc_utils/examples/run_figure_checklist.py`: from a figure file and
  caption to a validated panel-major prediction. It uses `LangfuseSource`,
  and mocks the session when run with `--mock`.
- The section "Changes in soda-curation" of the design note, completed into
  an integration brief:
  - output mapping (panel-major rows to `figures.<fig>.panels[].qc_checks[]`);
  - `passed` from verdict fields and `eval-manifest` N/A values;
  - concurrency across figures;
  - Docker (SDK, bundled CLI, a writable runtime directory, the API key);
  - `qc_check_metadata` from content hashes;
  - side-by-side running before switching.

**Human gate 6A.**

- **Decision:** can someone outside mmQC integrate from the brief and the
  example alone?
- **Artifact:** the brief and the example, run once in a clean container
  built from soda-curation's base image (`python:3.12-slim-bookworm`) with
  only `mmqc-utils[agentic]` installed.
- **Blocks:** handing over.

---

## Decisions recorded

- **0A, 2026-10-23: accepted.** mmQC runs the in-repo `mmqc_utils`, with
  the doctype fix. Image removal from converted documents is wanted (model
  input, injection surface, curation view).
- **1A, 2026-10-23: accepted.** Assembly takes a checklist directory and an
  `ExampleContent`. The benchmark adapter is `agentic/benchmark.py`. The
  493 assembled runtimes are byte-identical to the ones before the change.
- **3A, 2026-10-23: deferred by decision.** Implementation proceeds; the
  maintainer of `mmqc-utils` is consulted when it is done, before any
  release.
