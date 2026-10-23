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

**Step 2:** Write `figure_content(source_path, caption, ...)` in
`mmqc_utils`, defaulting to production's parameters. Leave out the second
re-encode: soda-curation can drop it when it adopts the builder, so the
builder decides what production's chain becomes. Test that the output is
deterministic: same input, same bytes.

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

*(none yet)*
