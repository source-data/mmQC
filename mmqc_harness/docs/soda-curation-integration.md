# Integrating mmqc-harness into soda-curation

*For soda-curation's developers. State of soda-curation as of tag `3.8.2`; line numbers refer to it.*

## What changes, in one paragraph

Today soda-curation runs figure QC as eleven independent model calls per figure, one per check. Each call uses a prompt and schema fetched from Langfuse (`checklists/fig-checklist/<check>`, label `production`), and the calls run one after another. With the harness, each figure gets **one agent session** that runs the whole checklist. The checklist, eleven checks plus a shared panel-classification skill, comes from Langfuse under a new namespace (`skills/fig-checklist/…`), and is the exact version mmQC benchmarked. The session returns one validated answer with a row per panel, which maps directly onto your `figures.<fig>.panels[].qc_checks[]`. Document-level QC stays on the current runner for now.

| | today (3.8.2) | with the harness |
|---|---|---|
| model calls per figure | 11, sequential | 1 session (25–30 turns) |
| instructions | 11 prompts, `checklists/fig-checklist/*` | 13 skills, `skills/fig-checklist/*`, one release |
| figure sent | JPEG encoded twice (bug, below) | JPEG encoded once, as benchmarked |
| answer | 11 lists of panels | one list of panels, each check's fields under its name |
| what was benchmarked | not this path | this path, byte for byte |

## 1. Install

```bash
pip install "mmqc-harness[langfuse]"      # brings mmqc-utils and the pinned Claude Agent SDK
```

- **Dependency versions.** `mmqc-harness` needs `mmqc-utils>=0.3.5`; soda-curation locks 0.3.3, so update the lock.
- **Docker** (`Dockerfile.cpu`, `python:3.12-slim-bookworm`):
  - **The Agent SDK bundles the Claude Code CLI.** Confirm that it runs on the slim image as your container user: `python -c "import claude_agent_sdk"`, then the example in section 4 with a real key.
  - **ImageMagick** is already installed, with the EPS/PDF policy relaxed. On Debian, Wand finds it without `MAGICK_HOME`.
  - **A writable runtime directory, off any bind mount:** the system temp directory is fine. Each session creates and deletes one there.
- **Environment:**
  - `ANTHROPIC_API_KEY` for the sessions;
  - the existing `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_BASE_URL` (or `LANGFUSE_HOST`), for pulling skills from the mmQC project.

## 2. Get the checklist, and keep it current

```bash
mmqc-skills pull   fig-checklist --entry do-fig-checklist-pm --dest /app/data/skills
mmqc-skills verify /app/data/skills/fig-checklist
mmqc-skills status /app/data/skills/fig-checklist
```

- **`pull`** is atomic. It verifies before swapping a new release in, leaves the previous copy if anything fails, and does nothing when the copy is already current. It records the release in `release.json`.
- **`verify`** works offline: content hashes, and the checklist's structural rules.
- **`status`** exits 1 when mmQC has published a newer release.

How automatic to make it is your choice. Two reasonable set-ups:

- **Pinned per deploy:** `pull` in the image build or deploy step, `verify` at start-up, and refuse to start QC on failure. A new release reaches production with the next deploy.
- **Followed:** `status` in a scheduled job, `pull` when it exits 1. Releases reach production without a deploy, and still only after they verify.

The old prompts under `checklists/…` are untouched; the harness never reads them.

## 3. Build the input

Use the **source figure file**, the one from the manuscript package, not the base64 JPEG in `figure_data.json`:

```python
from mmqc_harness import ExampleContent, figure_parts

content = ExampleContent(
    source_root=empty_dir,                            # nothing needs staging
    parts=figure_parts(figure_path, figure.figure_caption),
    files={},
    label=f"{manuscript_id}/{figure.figure_label}",
)
```

`figure_parts` converts the figure exactly as mmQC's benchmark does: `mmqc_utils.convert_to_bounded_jpeg` at 300 dpi, longest side 2,048 px, JPEG quality 80, **encoded once**.

The current path encodes twice:
1. `convert_to_pil_image` (`object_detection.py:63`) decodes the bounded JPEG into PIL;
2. `get_figure_images_and_captions` (`match_caption_panel_base.py:225`) saves it again at quality 80.

The same happens to panel crops (around line 341). There is an issue drafted for this, worth fixing on the current path too.

**Expected panel labels.** The current QC prepends a "CRITICAL PANEL LABEL CONSTRAINT" with the labels from `zip_structure`, and drops any panel outside them. Do **not** add that to the harness's input. The checklist finds and classifies the panels itself (`classify-panels`), and every benchmark result was measured without the list. Adding it would run an input mmQC has not measured. If you want the constraint, ask mmQC to benchmark it first. Comparing the answer's labels with `zip_structure` afterwards, as a report, is fine.

## 4. Run it

The runnable example, `examples/run_figure_checklist.py`, is the whole path. In short:

```python
import asyncio
from mmqc_harness import effective_session_options, load_model_defaults, run_session, runtime_session, validate_skills

checklist = Path("/app/data/skills/fig-checklist")
skills, defaults = validate_skills(checklist), load_model_defaults(checklist)

with runtime_session(checklist, "do-fig-checklist-pm", content, parent=runtime_dir) as layout:
    options = effective_session_options(layout, skills, defaults=defaults.session)
    options["model"] = defaults.model_for("claude-sdk")            # claude-sonnet-5-5
    answer, trace, audit = asyncio.run(run_session(layout, options=options))
```

- **Concurrency.** Run figures concurrently, since a session takes about a minute. A thread pool where each thread calls `asyncio.run(...)` is what mmQC uses. The QC pipeline is sequential today (`qc_pipeline.py:178-183`), so this is new.
- **Failures:**
  - `run_session` raises `ValueError` when a session ends without a valid answer. Record that figure's QC as failed; do not invent rows.
  - SDK errors (API key, credit, network) propagate. Stop the batch on an authentication or credit error, since every other figure would fail the same way.
- **Partial dispatch.** In a few percent of sessions the agent answers some checks without invoking them. `trace.invoked` lists the checks actually run. Decide whether to retry such a figure once, or record which checks ran.
- **Cost:** about $0.15 per figure with Sonnet 5.5, from `audit.usage["total_cost_usd"]`.

## 5. Map the answer to `qc_results`

The answer, valid against the entry point's schema:

```json
{"outputs": [
  {"panel_label": "A",
   "panel_classes": ["micrograph"],
   "micrograph-scale-bar": {"micrograph": "yes", "scale_bar_on_image": "yes", "…": "…"},
   "error-bars-defined":   {"is_a_plot": "no", "decision": "not_applicable", "…": "…"},
   "…": "nine more checks"}
]}
```

Into the current structure (`qc_pipeline.py:246-337`):

```text
figures.<figure>.panels[i] = {
  "panel_label": row["panel_label"],
  "qc_checks": [ {"check_name": <check, as below>, "passed": <section 6>, "model_output": row[<check>]}
                 for each of the eleven checks ]
}
```

- **`check_name`:** soda-curation's names are the checks' names with hyphens turned to underscores (`error-bars-defined` → `error_bars_defined`). The eleven are identical.
- **`model_output`:** the check's object for that panel, with the same fields as each check's own schema, minus `panel_label`.
- **`panel_classes`:** the panel's content types (micrograph, plot, blot, …). It isn't a check; keep it on the panel if it is useful.
- **`qc_check_metadata`:** replace each prompt's permalink and version with the release:
  - `release.json`'s `release` and the skill versions and content hashes;
  - the image fingerprint from `audit.inputs` (SHA-256, dimensions);
  - `trace.invoked`;
  - `audit.usage`, which feeds your `cost` block.

## 6. `passed` — a proposal to review

Today `passed` means "the model returned a non-empty dict for this panel" (`base_analyzers.py:298-301`), not that the check passed. The harness's answer carries each check's actual verdict:

| check | verdict field | passes when | does not apply when |
|---|---|---|---|
| `micrograph-scale-bar` | `scale_bar_defined_in_caption` | `yes` | `not_applicable` |
| `image-annotation-defined` | `annotation_defined_in_caption` (one value per annotation) | every value `yes` | `image_data` or `any_annotation_present_on_image` is `no` |
| `single-channel-for-overlay` | `all_channels_shown_separately` | `yes` | `not_applicable` |
| `individual-data-points` | `decision` | `PASS` | `not_applicable` |
| `error-bars-defined` | `decision` | `PASS` | `not_applicable` |
| `plot-axis-units` | `decision` | `PASS` | `not_applicable` |
| `plot-gap-labeling` | `decision` | `PASS` | `not_applicable` |
| `stat-significance-level` | `decision` | `PASS` | `not_applicable` |
| `stat-test` | `decision` | `PASS` | `not_applicable` |
| `replication-reporting` | `decision` | `PASS` | `not_applicable` |
| `panel-image-matches-caption` | `image_matches_caption` | `yes` | `not_applicable` |

**A check that does not apply** to a panel (a plot check on a micrograph) is neither passed nor failed. Record `passed: null`, or omit that check for that panel, rather than `true`. The values meaning "does not apply" are declared per field in each prompt's `eval-manifest` config (`na_values`), so the mapping can be read from the published checklist rather than hard-coded.

*This table encodes editorial judgement, in particular which field is the verdict and what counts as passing. It is a proposal from mmQC, to confirm with the editors before it drives anything users see.*

## 7. Roll-out

1. **Install, pull, verify.** Run the example on a few figures from real packages, as your container user.
2. **Side by side.** Add the harness behind a config flag and run both paths on the same manuscripts. Compare per check and per panel; the panel-major answer makes the comparison mechanical.
3. **Switch** panel QC to the harness. Keep document-level QC on the current runner until mmQC publishes a `doc-checklist` of skills, then switch it the same way.

Guideline reviews, such as the acceptance-guidelines step with its prose report, are a different kind of check and are not part of this.

## Appendix: found while reading soda-curation 3.8.2

Not caused by the harness. Noted here because they touch the same code:

- **`passed` is not a verdict.** Panel checks set it from "non-empty dict" (`base_analyzers.py:298-301`), figure and manuscript checks from `bool(result)` (`:419-422`, `:612-615`).
- **A latent `TypeError`.** `FigureQCAnalyzer.analyze_figure` takes 3 arguments, but `qc_pipeline.py:195-197` passes 4. It is caught as status `error`, and is latent only because no figure-level test is configured.
- **Document tests can be skipped.** They run inside the figure loop, on the first figure (`qc_pipeline.py:217`), so a manuscript with no figures runs none.
- **The analyzer factory never finds a module.** `AnalyzerFactory` imports `soda_curation.qc_tests.<name>`, which does not exist, so every test falls back to the generic analyzer (`analyzer_factory.py:27-43`).
- **Images are encoded twice** (section 3).
