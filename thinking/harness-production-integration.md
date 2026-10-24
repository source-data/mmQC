---
title: Harness in production (design note)
date: 2026-10-23
tags: [harness, production, soda-curation, mmqc-utils, langfuse, packaging]
status: draft
sources:
  - /Users/lemberge/code/soda-curation (tag 3.8.2)
---

# The harness in production — design note

Planning only. No code has moved. This note covers how the agentic harness in
[`soda_mmqc/agentic/`](../soda_mmqc/agentic/) becomes a package that
soda-curation installs, so that production and mmQC run one harness on one
input format and one skill set. It also covers what soda-curation has to
change, how skills reach production through Langfuse, and the checks that
show benchmark scores still describe production.

Open decisions are collected in [Decisions needed](#decisions-needed).

## Vocabulary

Two kinds of QC run in production. The names keep them apart.

- **Structured check.** The input is an example's content at some level. The
  output is a JSON answer that a schema constrains, so it can be scored
  against gold. This is what mmQC builds and measures. It does not depend on
  the level: `fig-checklist` works on figures, `doc-checklist` (contracts
  exist, skills not yet written) will work on manuscripts, and later
  checklists, such as [`ref-checklist`](ref-checklist-design.md), will work
  on other units.
- **Guideline review.** The input is a full set of guidelines plus the
  manuscript. The output is a prose report. soda-curation runs these at the
  document level (the acceptance-guidelines step). They are outside mmQC's
  scope.

"Agentic" names how a check is run (a session that invokes skills). It does
not name what kind of check it is. Do not use it as a synonym for
"structured".

## Where things stand

**mmQC.** The harness is about 3.8k lines. Most of it does not depend on the
benchmark:

- skill loading and validation: [`skills.py`](../soda_mmqc/agentic/skills.py)
- version pinning and model defaults: [`pinning.py`](../soda_mmqc/agentic/pinning.py)
- sealed runtime assembly: [`runtime.py`](../soda_mmqc/agentic/runtime.py)
- the session, tool audit and skill trace: [`session.py`](../soda_mmqc/agentic/session.py)
- provider rendering: [`render.py`](../soda_mmqc/agentic/render.py) and [`openai_driver.py`](../soda_mmqc/agentic/openai_driver.py)

Four couplings tie it to mmQC:

1. Every module imports `soda_mmqc.config` and `soda_mmqc.logger` at import
   time. Importing `soda_mmqc` loads `.env`, writes log files into the
   package directory, and resolves `API_PROVIDER`.
2. `assemble_runtime(checklist, check, example)` finds the input files under
   `EXAMPLES_DIR` and reads `example_class` from `benchmark.json`. It then
   builds the content through `EXAMPLE_FACTORY`. Production has no benchmark
   and no examples directory.
3. `resolve_check_dir` looks a checklist up by name under `CHECKLIST_DIR`.
4. [`runner.py`](../soda_mmqc/agentic/runner.py) handles arms, replicates,
   unpinning, the predictions layout and mock runs. These are evaluation
   concerns.

**soda-curation at 3.8.2.**

- QC is a separate synchronous CLI (`python -m src.soda_curation.qc.main`).
  It reads the `figure_data.json` and `zip_structure.pickle` that the main
  pipeline writes.
- Each of the 11 panel checks is one model call per figure. The calls run
  one after another. Prompts and schemas come from Langfuse
  (`checklists/{checklist}/{check}`, label `production`).
- The runner (`qc_pipeline`, `base_analyzers`, `model_api`, `providers`) is
  soda-curation's own code. Its only mmQC imports are the conversion
  functions in `mmqc_utils`.
- `passed` on a panel check means "the model returned a non-empty dict for
  this panel" (`base_analyzers.py:298`). It does not mean that the check
  passed.
- The Docker image (`python:3.12-slim-bookworm`) has no agent SDK.

## Target layout

`mmqc_utils` gains a subpackage, `mmqc_utils.agentic`, shipped as an
optional extra, `mmqc-utils[agentic]`. The extra pulls in `claude-agent-sdk`
(pinned exactly, as now), `pyyaml` and `jsonschema`. Users who only need
conversion do not get the SDK.

| Into `mmqc_utils` | Stays in `soda_mmqc` |
|---|---|
| skill loading, validation, call closure | benchmark walking: arms, replicates, `--unpin`, mock runs (`runner.py`) |
| version pinning, model defaults, content hashes | DAG and README rendering (`views.py`) |
| runtime assembly, taking content parts and a checklist source | gold, `benchmark.json`, `eval-manifest.json`, scoring, reporting |
| session, tool audit, skill trace, schema validation | the adapter from a benchmark `Example` to content parts |
| provider rendering, the runtime `CLAUDE.md`, the session's permission profile | |
| **content builders for each level**: figure, manuscript, later others | |
| **skill sources**: filesystem and Langfuse | |

Configuration comes in as an options object (runtime root, model, permission
profile). Nothing is read from the environment at import time.

`mmqc-utils` is maintained by Thomas Eidens. The subpackage needs their
agreement before any release.

## The seam: content separate from gold

`Example` already describes its content in a provider-neutral way:
`input_parts()` returns `text` and `image` parts, and `supporting_files()`
names the files that are staged but not sent. The split follows that line:

- **Content** is how a figure, a manuscript or a later unit becomes parts and
  files. It moves to `mmqc_utils`. soda-curation calls the same builders on
  its own data.
- **Gold and checks** stay in mmQC. A benchmark example becomes a thin
  wrapper that calls the shared builder and adds its gold.

Assembly then takes `(checklist source, entry point, parts, files)`. mmQC is
the first caller of the new interface, and the existing tests cover the
refactor before anything moves.

## Model input parity

A benchmark score describes production only if production sends the model
the same input. It does not do so today.

| | Production (soda-curation 3.8.2) | mmQC agentic path |
|---|---|---|
| Conversion | `mmqc_utils.convert_to_bounded_jpeg(rasterization_dpi=300, max_dimension=2048)`, quality 80 (`object_detection.py:63`) | none: [`render.py`](../soda_mmqc/agentic/render.py) base64-encodes the stored file unchanged |
| Re-encode | decoded to PIL, then saved again as JPEG quality 80 (`match_caption_panel_base.py:225`) | none |
| Stored format | — | 47 jpg/jpeg, 15 png, 14 webp across the benchmark figures; how they were made is not recorded |
| Message | caption text, then image | caption text, then image |

The figure content builder in `mmqc_utils` defines this chain once:
conversion parameters, encoding, and part order. Production and the
benchmark-building step both call it.

**Sanity check (to do).** Run the chain on the benchmark figures, then run
`fig-checklist` on both versions of the images (stored and re-converted) and
compare scores, as a regular experiment with replicates. If the scores
match, past results carry over to production. If they do not, the
re-converted set becomes the benchmark from then on. Before this can run:

- find out whether the original files for the benchmark figures exist
  (TIFF, PDF, EPS);
- if they do not, decide whether to apply the chain to the stored rasters.

## Input kinds

Today the parts format has two kinds, `text` and `image`. Planned checks need
more: PDF, Word, Excel, CSV, and possibly code. Each format can be delivered
in one of two ways now:

1. **Convert to a text part.** For example, `document_to_html` for Word and
   PDF, or a table rendered as text for CSV and Excel. This works for every
   provider and is what `WordExample` does now. It loses layout, and for PDF
   it loses figures.
2. **Native part.** For example, an Anthropic `document` block for PDF.
   Fidelity is higher, but support differs by provider, so it needs a
   fallback for each provider in `render.py`.
**Out of scope for now: staged files opened when needed.** A session has
only the `Skill` tool, so the supporting files listed in `inputs.json` cannot
be opened. File access will be added with
[`ref-checklist`](ref-checklist-design.md), or with whichever checklist first
needs it, as part of that checklist's tool and capability design.

The builder for each format decides which delivery it uses. This keeps the
choice in shared code, so production and the benchmark cannot drift apart.

## Skills in Langfuse

Langfuse is the boundary between R&D and production. mmQC pushes **only the
production versions** and labels them `production`. The application loads
whatever carries that label. It does not pin versions, track them, or know
about the repository. This is how prompts reach production today, and skills
follow the same path.

### What decides what is published

Agreed 2026-10-23:

- **`fig-checklist` holds the production topology.** It contains the
  production entry point, the skills it reaches, and their contracts. Those
  fix which skill calls which, and what each check answers. A skill may
  have several prose versions, as long as every version keeps the same
  `requires` (the same edges) and is scored against the same contract.
  [`version-manifest.yaml`](../soda_mmqc/data/checklist/fig-checklist/version-manifest.yaml)
  picks which prose version is production. `--unpin` varies the prose
  within that topology. A different topology (other skills, other edges,
  another answer shape) belongs in a `fig-checklist-expNN` copy. History
  lives in those copies and in git.
- **[`production.json`](../soda_mmqc/data/production_prompts/production.json)
  is a short list of checklist names** for skills, with no versions, for
  example `{"skills": ["fig-checklist"]}`. It is the release file CI
  watches, for both runners. Changing it is the deliberate act of
  releasing. Until the prompt-based runner is retired, its per-check prompt
  versions stay in the same file.

No version appears in both files.

**Why the manifest did not mean production before the cleanup.**
`fig-checklist` pinned more than production ran:

- **the check-major entry point**, `do-fig-checklist-cm`, kept for
  comparison with earlier runs;
- **the `v1` checks**, which stayed in their folders unpinned;
- **`identify-panels` and `classify-plot-panels`**, which only those `v1`
  checks call.

The manifest had to pin these last two:
[`validate_version_manifest`](../soda_mmqc/agentic/pinning.py) checks
against the folder's inventory, not against what is reachable, so every
skill in the folder needs a pin. Reachable here is relative to the pins
anyway: `--unpin` back to a `v1` check reaches them again.

**Topology check (proposed).** Today a skill's versions may declare
different `requires`: `call_closure` follows the pinned version, so a `v3`
that delegates and a `v1` that does not simply assemble different
runtimes. That is useful in experiment copies. For a production checklist,
"vary prose, not topology" would be enforced by one more validation rule:
every version of a skill has the same `requires`. The `v1` checks removed
in the cleanup broke that rule, because they called `classify-plot-panels`
and `identify-panels`, not `classify-panels`. The rule needs a way to mark
a checklist as production. Being named in `production.json` is the obvious
one.

**Why cm and pm are two skills, not two versions of one.** A check's
contracts (`schema.json`, `eval-manifest.json`, `benchmark.json`, gold)
sit above its version folders and are shared by every version. That is
what makes an `--unpin` comparison like-for-like. cm and pm answer in
different shapes, so they have different contracts. `--unpin` is for
prose variants that share a contract. A change of output shape needs a
new skill or a separate checklist copy, as exp-10 used.

**Cleanup (done 2026-10-23).** Removed from `fig-checklist`:

- `do-fig-checklist-cm`;
- the `v1` version folders of the checks;
- `identify-panels` and `classify-plot-panels`.

No snapshot was taken, because the milestone 5–6 runs are far enough back.
Each check's `prompts/` stayed, because the prompt-based runner reads them
through `production.json`. Check-major lives on in `fig-checklist-exp10`.

The tests that used the removed skills went with them:

- the check-major contract checks;
- the two-entry-points-differ-only-by-name check;
- four pilot-era checks on `micrograph-scale-bar` v1's prose. Those
  required the prose to name every schema field, and `output_format` has
  enforced the schema since 2026-09-19.

`build_contract.py` (exp-10) now writes contracts only for the entry
points its target pins.

**Publisher.** For each checklist named in `production.json`, the
publisher publishes every skill its manifest pins. As a guard, it first
checks that every pinned skill is reached from the entry point (the
checklist's single `do-*` skill), and refuses to publish otherwise. The
guard reuses
[`call_closure`](../soda_mmqc/agentic/skills.py), the function runtime
assembly uses, and refuses when the pinned set minus the closure is not
empty. It does not parse `dag.yaml`. That file is generated from the same
pinned graph and drift-checked by `mmqc graph`. Its README already lists
the pinned skills no check reaches, under "Called by no check". This
rule applies only to production checklists. The general manifest
validation stays inventory-based, because an experiment checklist may
pin skills on purpose that today's prose does not reach.

### Namespace

The prompt-based runner uses `checklists/<checklist>/<check>`, and skills
have the same names. Skills get their own namespace,
`skills/<checklist>/<skill>`. Otherwise a `SKILL.md` would become a new
version of an old prompt, and the old runner would read it as a system
prompt.

### One prompt per skill, contracts in its config

- **Prompt text:** the whole `SKILL.md`, front matter included. The harness
  writes it back verbatim, so production's `skill_content_hash` equals
  mmQC's. That one fact shows the published skill is the one that was
  benchmarked.
- **Config:** keyed by file name, following the existing publisher's
  convention (`config[json_path.stem]`):

  | Key | Source | On |
  |---|---|---|
  | `schema` | `<check>/schema.json` | every skill that has one: leaves and entry points |
  | `eval-manifest` | `<check>/eval-manifest.json` | the same |
  | `model-defaults` | `<checklist>/model-defaults.yaml` | the entry point |
  | `skill` | name, mmQC version, content hash | every skill (for display and provenance; nothing reads it to resolve versions) |

- **Tags:** `entry`, `leaf` or `shared`, for browsing.
- `benchmark.json` is not published. It names gold examples, and production
  never scores.

**What a session actually uses.** The **entry point's** `schema` becomes the
session's required output format (`output_format`). A leaf's `schema` is
used only when that leaf is itself the entry point, which is the case when a
single check runs on its own. Inside a whole-checklist session, a leaf's
schema is staged next to its `SKILL.md` but never read, because the session
has only the `Skill` tool. The panel-major schema was derived from the
leaves' schemas and checked against them
(`experiments/exp-10-panel-major-revisited/build_contract.py`), so
publishing the leaves' schemas costs nothing. It also keeps every leaf
runnable on its own, and keeps the derivation checkable from Langfuse
alone.

`eval-manifest` is not needed to run anything. It is published because it
is the only place a field's N/A values are declared (`na_values`, for
example `not_applicable` on `error_bar_on_figure`). Production needs those
to tell "does not apply" from "fails" when it derives `passed`.

### Loading in production

The harness's Langfuse skill source loads `skills/<checklist>/*` at label
`production`, writes each prompt back as `<skill>/SKILL.md` with its
`schema.json`, and from then on runs exactly as it does from the
filesystem: validation, closure, assembly. The skill set and its content
hashes are written into `qc_check_metadata`.

**Partial publish (open).** The publisher uploads skills one at a time. A
run that starts during an upload could load some new skills and some old
ones. A cheap guard: the publisher writes the same release ID (the commit
SHA) into every skill's `skill` config, and the loader refuses a set whose
IDs differ, then retries. Whether the guard is worth having depends on how
often production runs overlap a publish.

### Checking the publication

mmQC runs a benchmark sample with skills loaded from Langfuse, and asserts
that the content hashes equal the filesystem's for the published closure.

## Changes in soda-curation

**For the soda-curation maintainers; not implemented from mmQC.** mmQC's
scope ends at the package (`mmqc-utils[agentic]`) and the Langfuse
publication. This section records what the integration will need on the
application side, as found at tag 3.8.2.

- Install `mmqc-utils[agentic]`. Replace the per-check runner for structured
  checks with the harness, behind a config flag, first for `fig-checklist`.
  `doc-checklist` follows once it has skills. Nothing in the new path is
  specific to figures.
- Build inputs with the shared content builders instead of
  `get_figure_images_and_captions`.
- One session per figure on `do-fig-checklist-pm` replaces 11 calls per
  figure. The panel-major answer (one row per panel, each check's fields
  under its name) maps directly onto `figures.<fig>.panels[].qc_checks[]`.
- Run sessions concurrently. The QC pipeline runs one figure at a time, and
  a session takes 25 to 30 turns.
- Derive `passed` from the verdict fields in the schema, not from whether a
  dict is empty.
- For the new path, load skills from `skills/<checklist>/*` at label
  `production` through the harness's Langfuse skill source, instead of the
  prompt registry and its schema-equivalence check. `qc_check_metadata`
  records each skill's name, mmQC version and content hash instead of a
  prompt permalink.
- Feed the tool audit's token usage into the `cost` block.
- Docker: add the SDK, and confirm that the CLI it bundles runs on the slim
  image (no Node.js is installed today). Provide a writable runtime
  directory and `ANTHROPIC_API_KEY`.
- Run the new path alongside the old one on real manuscripts before
  switching.

**Expected panel labels.** soda-curation tells the model the panel labels it
found and drops any panel outside that list. In the skills,
`classify-panels` finds the panels itself, and every exp-04 to exp-10 result
was measured without the list. Adding it to the message changes the input,
so it needs measuring first, or production leaves it out.

## Could guideline reviews use the harness?

Mechanically, mostly. Two parts are built to require structured output:

- `_run_agent_session` requires a JSON answer and validates it against the
  leaf schema. An optional output contract would let it return prose.
- A guideline review attaches XML and a PDF, which needs the extra input
  kinds above.

Both changes are on the roadmap anyway. Recommendation: do not include
guideline reviews in the first version. Make the output contract optional
and the input kinds open-ended, so they can be added later without a
redesign, and keep the names separate as set out in
[Vocabulary](#vocabulary).

## Order of work

Scheduled, with milestones and gates, in
[`plans/2026-10-23-harness-in-mmqc-utils.md`](plans/2026-10-23-harness-in-mmqc-utils.md).

1. **Refactor the seam inside mmQC.** Assembly takes parts, files and a
   checklist source. Configuration becomes an options object. Content
   builders are separated from gold. The existing tests must keep passing.
   This step does not depend on any open decision.
2. **Move the code into `mmqc_utils.agentic`**, with `soda_mmqc` depending
   on it through an editable source during development. Requires the
   maintainer's agreement.
3. **Image parity sanity check** (above).
4. **Langfuse publishing for skills:** clean `fig-checklist` down to
   production, add the checklist list to `production.json`, add the skills
   publisher with its reachability guard, the Langfuse
   skill source in the harness, then the content-hash check.
5. **Handover to soda-curation** (outside mmQC's scope): the package, the
   Langfuse namespace, and [Changes in soda-curation](#changes-in-soda-curation)
   as the integration brief.

## Decisions needed

1. ~~**Skills entry in `production.json`**~~ — agreed 2026-10-23: a list of
   checklist names, no versions. `fig-checklist` holds the production
   topology. Its manifest picks the production prose.
   Still open: whether the skills publisher is a mode of
   `build_langfuse_checklist.py` or a script of its own.
2. ~~**Skill namespace**~~ — agreed 2026-10-23: a namespace of its own,
   distinct from the prompt-based runner's `checklists/…`. Proposed:
   `skills/<checklist>/<skill>`.
3. **Partial-publish guard:** a release ID in every skill's config, checked
   at load, or nothing?
4. **Expected panel labels:** measure a variant that receives them, or keep
   production's message identical to the benchmark's?
5. **Benchmark originals:** answered 2026-10-23 — the benchmark figures are
   published figures from journal websites, with no submitted files
   (plan, Milestone 4 Step 1). Open: obtain the submitted figures of the
   benchmark manuscripts (EMBO Press titles) to measure the
   published-versus-submitted gap, or measure only the encoding gap?
6. ~~**Staged files**~~ — decided 2026-10-23: not now. File access comes
   with `ref-checklist`, or with the first checklist that needs it.
7. ~~**Packaging**~~ — decided 2026-10-24: a sibling package,
   `mmqc-harness` (import `mmqc_harness`), in `mmqc_harness/` next to
   `mmqc_utils/`, depending on `mmqc-utils`. Not an extra of `mmqc-utils`:
   that package is conversion utilities, maintained separately.
