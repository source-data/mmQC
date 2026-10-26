# mmqc-harness

Run a structured quality-control checklist on one example — a figure and its caption, a manuscript — in a sealed Claude agent session, exactly as [mmQC](https://github.com/source-data/mmQC) benchmarks it.

![mmQC publishes a production checklist to Langfuse; an application pulls a verified local copy with mmqc-skills; per figure, the figure is converted once, a throwaway runtime holds the closure of skills and a sealed agent session with only the Skill tool, and run_session returns the validated answer, the skill trace and an audit with cost and image fingerprints; the runtime is then deleted](docs/harness-overview.svg)

**Documentation:** this README is the quick start. The [guide](docs/guide.md) explains concepts, the life of a session, containment, results, publishing, and the API. [Integrating into soda-curation](docs/soda-curation-integration.md) is the brief for the production application. [`examples/run_figure_checklist.py`](examples/run_figure_checklist.py) runs the whole path on one figure, with `--mock` for a run without a model.

A checklist is a set of **skills**: Markdown instructions that call each other by name. One of them, the **entry point**, owns a JSON schema, and the session's answer is constrained to it. mmQC writes the skills, benchmarks them against curated gold, and publishes the production version to Langfuse. An application installs this package, pulls the published checklist, and runs it on its own examples. Because both sides use the same harness, the same figure conversion and the same skill files, a benchmark score describes what production does.

## Installation

```bash
pip install mmqc-harness
```

This brings [`mmqc-utils`](../mmqc_utils) (the figure and document conversions) and the Claude Agent SDK, pinned exactly: a silently updated agent runtime would make results incomparable. The SDK bundles the Claude Code CLI that each session runs.

You also need:

- **`ANTHROPIC_API_KEY`** in the environment, for the sessions;
- **ImageMagick**, for converting figures. On macOS with Homebrew set `MAGICK_HOME=/opt/homebrew/opt/imagemagick`; on Debian or Ubuntu install `libmagickwand-dev`;
- **the `langfuse` package and credentials,** to pull checklists from Langfuse: `pip install "mmqc-harness[langfuse]"`, plus `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_BASE_URL`.

## Getting a checklist: `mmqc-skills`

mmQC publishes each production checklist to Langfuse, one prompt per skill (`skills/<checklist>/<skill>`, label `production`). Keep a local copy and run from it:

```bash
mmqc-skills pull   fig-checklist --entry do-fig-checklist-pm --dest skills/
mmqc-skills verify skills/fig-checklist
mmqc-skills status skills/fig-checklist
```

- **`pull`** brings `skills/fig-checklist` to the published release, or does nothing if it is already there. It fetches into a temporary directory and checks it first:
  - each `SKILL.md` against its content hash;
  - a single release;
  - the production rules: one entry point, every skill reached, one call graph.

  Only then does it swap the copy into place, so a refused update leaves the previous copy untouched. It writes `release.json` beside the skills, recording the release, the label, when it was fetched, and each skill's version and hash.
- **`verify`** checks a local copy offline against `release.json`. Use it at start-up or in a health check.
- **`status`** compares the local release with the published one.

| exit code | meaning |
|---|---|
| `0` | fine (for `status`: up to date) |
| `1` | a check failed (for `status`: an update is available) |
| `2` | a usage or configuration error |

`SKILL.md` files are written back byte-identical. The contract files (`schema.json`, `eval-manifest.json`, `model-defaults.yaml`) are equal in content, rewritten from the prompt's config. The same operations are available in Python: `mmqc_harness.publication.pull_checklist`, `verify_local_checklist` and `published_release`.

## Running a checklist on a figure

```python
import asyncio
from pathlib import Path

from mmqc_harness import (
    ExampleContent,
    effective_session_options,
    figure_parts,
    load_model_defaults,
    run_session,
    runtime_session,
    validate_skills,
)

checklist = Path("skills/fig-checklist")
skills = validate_skills(checklist)
defaults = load_model_defaults(checklist)

content = ExampleContent(
    source_root=Path("figure-3"),      # a directory, staged into the runtime; may be empty
    parts=figure_parts("figure-3/figure.tif", caption),
    files={},                          # supporting files by role, under source_root (none needed)
    label="figure-3",
)

with runtime_session(checklist, "do-fig-checklist-pm", content, parent=Path("/var/tmp/mmqc")) as layout:
    options = effective_session_options(layout, skills, defaults=defaults.session)
    options["model"] = defaults.model_for("claude-sdk")
    answer, trace, audit = asyncio.run(run_session(layout, options=options))
```

**The content.**
- `figure_parts(source, caption)` gives the caption, then the figure as the model receives it. The figure is converted **once** with `mmqc_utils.convert_to_bounded_jpeg`: rasterized at 300 dpi, longest side 2,048 px, JPEG quality 80. Those bytes are sent unchanged.
- Build figures with it, so the model sees what mmQC benchmarked. Do not decode and re-encode its output: every lossy pass adds artefacts, and fine text such as axis labels, scale bars and panel letters goes first.
- An image part either names a file under `source_root`, `{"kind": "image", "path": ...}`, or carries its bytes, `{"kind": "image", "media_type": ..., "data": ...}`.

**The runtime.**
- `runtime_session` assembles a sealed runtime, yields it, and removes it afterwards, even on failure. The runtime holds the entry point, every skill its pinned prose reaches (one version each), and the example's content.
- It is created under `parent`, the system temp directory by default. Keep that off synced folders, and outside any repository that holds skills: the agent SDK discovers skills from parent directories.

**The answer.** `run_session` returns:
- `answer`, already validated against the entry point's schema;
- `trace.invoked`, the skills the session called, in order;
- `audit`, which records the session's tool calls, its cost and token usage (`audit.usage`), and a **fingerprint of every image sent** (`audit.inputs`: media type, size, dimensions, SHA-256).

`run_session` raises `ValueError` when the session ends without an answer, or with one that is not JSON or does not satisfy the schema. The audit is also written to `tool_audit.json` in the runtime; copy it out before the runtime is removed if you keep it.

**One session per figure.** Each takes 25–30 turns, about a minute with Sonnet 5.5. Run figures concurrently: sessions share nothing.

## What a session can do

One thing: invoke a skill. It has the `Skill` tool and nothing else:
- no shell, file, network or subagent tools;
- `permission_mode` `dontAsk`;
- only the project's settings;
- its transcript is kept inside the runtime.

The content arrives in the request, and the answer is the structured output. `session_options(layout)` returns the exact profile, and the permission profile is not configurable.

**Its standing instructions** are the runtime's `CLAUDE.md`. By default it is the harness's template, written for mmQC's checks. An application whose sessions do something else passes its own file: `runtime_session(..., orientation=Path("review.md"))`, or the same argument to `assemble_runtime`.
- The file is copied verbatim. A missing file, a directory or a symbolic link is refused.
- Its source (a path, or `"default"`) and SHA-256 are on the layout (`layout.orientation_source`, `layout.orientation_sha256`), in `tool_audit.json` under `orientation`, and in `session_cache_key`.
- It changes what the session is told, not what it may do: the permission profile is the same. Checklist defaults (`model-defaults.yaml`) may set the model and session knobs such as `max_turns`, nothing else.

## The production rules

A checklist published to production obeys three rules, which `mmqc_harness.publication.production_entry_point` checks:
- **one entry point**, a skill no other calls, owning `schema.json`;
- **every pinned skill reached** from it;
- **one topology:** versions of a skill may differ in prose, never in which skills they call.

`mmqc-skills pull` refuses a checklist that breaks them.

## Publishing (mmQC's side)

`mmqc_harness.publication.skill_payloads(checklist_dir)` builds one Langfuse prompt per pinned skill. The text is the whole `SKILL.md`. The config holds:
- the contracts;
- the model defaults, on the entry point;
- `skill`: checklist, name, version, role, content hash, and `release`, the digest of the whole set.

mmQC's publisher (`.github/scripts/publish_langfuse_skills.py`) skips a release Langfuse already carries, and verifies each publish by loading it back.

## Logging

The harness logs under `mmqc_harness` and configures no handlers; attach your own.

## Development

```bash
cd mmqc_harness
MAGICK_HOME=/opt/homebrew/opt/imagemagick uv run --group test pytest
```

The tests build their own small checklist and never call a model: sessions run against a client that replays messages. `tests/test_boundary.py` holds the package to two rules:
- it imports nothing from mmQC;
- importing it writes no file, reads no `.env`, and loads neither mmQC nor the SDK.
