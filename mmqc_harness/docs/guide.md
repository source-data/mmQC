# mmqc-harness — guide

The [README](../README.md) is the quick start. This guide explains what the harness does and why, so that you can run a checklist with confidence, diagnose a session that went wrong, and change the harness without breaking the property it exists for: **a benchmark score describes what production runs.**

1. [Concepts](#1-concepts)
2. [The life of one session](#2-the-life-of-one-session)
3. [Content: what the model is sent](#3-content-what-the-model-is-sent)
4. [Containment: what a session can do](#4-containment-what-a-session-can-do)
5. [Results: the answer, the trace, the audit](#5-results-the-answer-the-trace-the-audit)
6. [Running many examples](#6-running-many-examples)
7. [Publishing and pulling checklists](#7-publishing-and-pulling-checklists)
8. [Reference](#8-reference)

---

## 1. Concepts

### Skills

A **skill** is a Markdown file, `SKILL.md`, that an agent reads and follows. Its front matter names it and declares its edges:

```markdown
---
name: error-bars-defined
description: Check that error bars, and box or violin plot elements, are explained in the caption.
requires:
  - classify-panels
---

# error-bars-defined
...
Before you do anything else, invoke the `classify-panels` skill with the `Skill` tool ...
```

- `name` is the skill's identity, not its directory, so moving a directory changes nothing.
- `description` is what the agent sees before it opens the skill, so it is how the agent decides to use it.
- `requires` lists the skills this one calls. **The prose must call each of them with the `Skill` tool, and call no other.** Validation reads the prose and refuses a skill whose declared and written calls disagree. The prose is what runs; the front matter is what the harness can check.
- `produces` and `needs` are optional. `needs` may request a capability, but it can only narrow the session's permissions, never widen them (see [section 4](#4-containment-what-a-session-can-do)).

### Checklists

A **checklist** is a directory of skills, each in its own folder and each version in a sub-folder:

```text
fig-checklist/
├── version-manifest.yaml        # one version of every skill
├── model-defaults.yaml          # the model, and session knobs such as max_turns
├── do-fig-checklist-pm/         # the entry point
│   ├── schema.json              #   the answer's contract
│   └── v1/SKILL.md
├── classify-panels/             # a shared skill: no schema
│   └── v1/SKILL.md
├── micrograph-scale-bar/        # a check: it owns a schema
│   ├── schema.json
│   └── v2/SKILL.md
└── …
```

- **Versions.** A skill can have several versions (`v1`, `v2`, …). `version-manifest.yaml` pins exactly one of each, and must pin every skill, so a session is always built from a reviewed set of versions, never from whatever is newest on disk. A skill set's identity is the digest of its pinned versions' contents (`SkillSet.digest`), not their labels.
- **Contracts.** A skill that answers owns `schema.json`: a JSON Schema in the `{"format": {"type": "json_schema", "schema": …}}` envelope. The session's final answer is **constrained** to it by the API, not merely asked to follow it. mmQC adds `eval-manifest.json` and `benchmark.json` for scoring. The harness never reads them, and refuses to stage them into a runtime.
- **The entry point** is the skill a session is dispatched with. For `fig-checklist`, `do-fig-checklist-pm` invokes the eleven checks, each of which invokes `classify-panels`.
- **The call closure** of an entry point is every skill its pinned prose reaches, transitively. A session holds the closure and nothing else.

### Production checklists

A checklist published to production obeys three more rules (`publication.production_entry_point`):

1. **One entry point:** exactly one pinned skill is called by no other, and it owns `schema.json`.
2. **Nothing unreached:** every pinned skill is in the entry point's closure.
3. **One topology:** every version of a skill declares the same `requires`. Prose may vary between versions; the call graph may not.

A different arrangement of the skills is a different checklist.

---

## 2. The life of one session

```text
ExampleContent ──► assemble_runtime ──► session_options ──► run_session ──► answer, trace, audit
 (what to send)     (sealed directory)    (permissions)      (one agent)      (teardown follows)
```

**1. State the content.** An `ExampleContent` says what the example is, and nothing about where it came from:

```python
ExampleContent(
    source_root=Path(...),   # staged as the runtime's input/; may be empty
    parts=(...),             # what the model is sent, in order (section 3)
    files={...},             # supporting files by role, under source_root; listed, not sent
    label="figure-3",        # for logs and the layout
    exclude=("checks",),     # names left out of the staged copy
)
```

**2. Assemble the runtime.** `assemble_runtime(checklist_dir, entry, content, parent=...)`:
- validates the checklist (front matter, prose against `requires`, no cycles, a complete manifest), and refuses an entry point without `schema.json`;
- selects the pinned version of each skill, and keeps the entry point's closure (`assembly="all"` keeps every skill, for reproducing old experiments);
- builds the runtime in a staging directory under `parent`, then renames it into place, so a failed assembly leaves nothing behind. The runtime holds:
  - `.claude/skills/<name>/SKILL.md`, flattened from the version folders, each with its `schema.json` if it has one;
  - `input/`, the content staged from `source_root`, minus `exclude`, plus `inputs.json` naming the supporting files;
  - `CLAUDE.md`, the session's standing instructions. By default the harness's template, written for mmQC's checks: one tool, nothing to open, follow the skill you were dispatched with. `orientation=Path(...)` copies the caller's file instead, verbatim; a missing file, a directory or a symbolic link is refused. Its source and SHA-256 are on the layout, in the audit (`orientation` in `tool_audit.json`) and in the cache key;
  - `agent-home/`, where the SDK keeps its transcript, so it never lands in your home directory;
  - `artifacts/`, where the answer and the sidecars are written;
- **refuses a runtime that leaks:** any `benchmark.json`, `eval-manifest.json`, `checks/` folder or symbolic link, wherever it sits.

`runtime_session(...)` does the same as a context manager, and removes the runtime on exit, including after an error. `keep=True` keeps it for inspection.

**3. Decide the session's options.** `session_options(layout)` is the permission profile (section 4). `effective_session_options(layout, skills, defaults=…)` adds the checklist's defaults, such as `max_turns` from `model-defaults.yaml`. Set `options["model"]` yourself, usually `load_model_defaults(checklist).model_for("claude-sdk")`.

**4. Run it.** `run_session(layout, options=options)` is a coroutine:
1. It records a fingerprint of every image it will send, before sending anything.
2. It sends one message: an instruction naming the entry point ("Apply the `do-fig-checklist-pm` check to the example below, and answer with the structured output you were given a schema for"), then the content parts.
3. It follows the session, recording every `Skill` call in the trace and every tool call, turn, event and token in the audit.
4. It parses the final structured result, writes it to `artifacts/prediction.json`, and validates it against the entry point's schema.

The instruction names only the entry point. Which skills run, and in what order, is the agent's doing, prompted by the skills' prose. That is the property mmQC's experiments measure, which is why the harness never preselects.

**5. Teardown.** Leaving `runtime_session` deletes the runtime. Copy `artifacts/intermediates/` out first if you keep the trace and audit files; the returned objects hold the same information.

---

## 3. Content: what the model is sent

### Parts

Content is a short list of provider-neutral **parts**:

| part | meaning |
|---|---|
| `{"kind": "text", "text": str}` | literal text |
| `{"kind": "image", "path": str}` | an image file, relative to `source_root`; it is staged, then read and encoded when the request is built |
| `{"kind": "image", "media_type": str, "data": bytes}` | an image carried as bytes; it travels in the request and is never written into the runtime |

An image part names a file or carries bytes, exactly one of the two. `render.render_anthropic` and `render.render_openai` turn parts into each provider's content blocks. The vocabulary is closed on purpose: a new kind is a deliberate change to the renderers.

### Figures

Build a figure's parts with **`figure_parts(source, caption)`**: the caption as text (`"Figure caption:\n…"`), then the figure as an image carrying its bytes.

The figure is converted **once**, by `mmqc_utils.convert_to_bounded_jpeg`:
- rasterized at 300 dpi (`FIGURE_RASTERIZATION_DPI`), for vector formats;
- transparency flattened onto white;
- longest side at most 2,048 px (`FIGURE_MAX_DIMENSION`);
- JPEG at quality 80 (`FIGURE_JPEG_QUALITY`).

Those bytes are what the model receives. **Do not decode and re-encode them:** every lossy pass adds artefacts, and fine text (axis labels, scale bars, panel letters) suffers first. mmQC's benchmark builds its figures with the same function. exp-11 showed that scores on figures converted this way are no worse than on the stored files the series used before.

The provider downscales further when an image exceeds its own limits. Sonnet 5.5 is in the high-resolution tier: at most 2,576 px on the long edge and 4,784 visual tokens of 28 × 28 px.

### Documents

A manuscript is a text part: convert it to HTML with `mmqc_utils.document_to_html` and send the HTML as text. The conversion removes images and empty elements, so the model sees the text, not embedded pictures.

### Supporting files

Files a check might want but usually does not need (source-data spreadsheets, for instance) go in `files` and are listed in `input/inputs.json`. Today no session can open them: the only tool is `Skill`. File access will come with the first checklist that needs it.

---

## 4. Containment: what a session can do

A session **observes one example and answers**. It changes nothing, fetches nothing, and leaves nothing behind.

| setting | value | why |
|---|---|---|
| `tools` | `["Skill"]` | what the session *has*; everything else is absent from its context |
| `allowed_tools` | `["Skill"]` | approved without prompting |
| `permission_mode` | `dontAsk` | anything that would prompt is denied: no one is there to answer |
| `disallowed_tools` | Bash, Agent, Task, WebFetch, WebSearch, SendMessage, … | removed by name, for the calls the SDK allows without asking. Each has its reason in `runtime.AGENTIC_FORBIDDEN_TOOLS` |
| `setting_sources` | `["project"]` | the operator's own skills and settings are not read |
| `skills` | the assembled names | only these are invocable; other installed skills are refused |
| `cwd` | the runtime root | skill discovery sees the assembled tree only |
| `env.CLAUDE_CONFIG_DIR` | `<runtime>/agent-home` | the transcript stays inside the runtime |
| `output_format` | the entry point's schema | the answer is constrained, not requested |

The profile is **not configurable**. A checklist's `model-defaults.yaml` may set the model and session knobs such as `max_turns`, but a key that touches permissions is refused with a warning. A skill's `needs` can only narrow the profile. Widening it is a deliberate change to `runtime.py`, reviewed like one.

**Where runtimes go.** Under `parent`, by default the system temp directory. Keep it off synced folders (iCloud, Dropbox, OneDrive and the like), because runtimes hold unpublished figures. Keep it outside any repository that holds skills: the Agent SDK discovers skills from parent directories, and the harness's containment assumes it finds none. The harness does not check either rule itself; mmQC's runner does, with `resolve_agentic_runtime_root`.

---

## 5. Results: the answer, the trace, the audit

`run_session` returns `(answer, trace, audit)`.

- **`answer`**: the parsed structured result, already valid against the entry point's schema. For `fig-checklist` it is panel-major: `{"outputs": [{"panel_label", "panel_classes", "<check>": {…}, …}]}`.
- **`trace`** (`SkillTraceRecorder`): `trace.invoked` is the list of skills the session called, in order. The trace is also written to `artifacts/intermediates/skill_trace.json`. A session that answered without invoking its checks shows up here, and nowhere else.
- **`audit`** (`ToolAuditLog`), also written to `artifacts/intermediates/tool_audit.json`:
  - `inputs`: the fingerprint of every image sent (`part`, `source`, `media_type`, `bytes`, `dimensions`, `sha256`);
  - `usage`: cost in dollars, turns, duration and token counts, from the SDK;
  - `session`: what the SDK reported at start-up, including the tool set it actually granted;
  - `turns`: the model that wrote each message;
  - `events`: other system messages, truncated;
  - `calls`: every tool call attempted, and whether it was allowed.

**The fingerprint** lets you check later what the model saw without keeping the image: re-convert the source with `figure_image_part` and compare the SHA-256. A mismatch means the source or a library underneath (ImageMagick, the JPEG encoder) has changed.

**Failures.** `run_session` raises `ValueError` when:
- the session ends without an answer;
- the answer is not JSON, which is how a model declining to answer within the schema shows up;
- the answer does not satisfy the schema.

Errors from the SDK itself, such as a bad API key, no credit or a lost connection, propagate unchanged. mmQC's runner treats those as reasons to stop a whole batch, since every later session would fail the same way.

---

## 6. Running many examples

- **One session per example.** Sessions share nothing: each has its own runtime, its own SDK process and its own answer.
- **Run them concurrently.** A `fig-checklist` session takes 25–30 turns, about a minute with Sonnet 5.5, and costs about $0.15. mmQC runs 38 at a time in a thread pool, each thread running its session's event loop with `asyncio.run`.
- **Expect some partial dispatch.** In a few percent of sessions the agent answers some checks without invoking them. `trace.invoked` shows it. Decide per application whether to retry such a session.
- **Caching.** `runtime.session_cache_key(layout, model=…, options=…)` keys a session by everything that can change its answer: content, skill set, model, options, schema and the runtime's `CLAUDE.md`. Never by its trace.

---

## 7. Publishing and pulling checklists

### The store

A prompt store (Langfuse) is the boundary between the repository a checklist is developed in and the application that runs it. **Only production is published:** the pinned version of each skill, one prompt per skill, named `skills/<checklist>/<skill>` and labelled `production`.

| part of the prompt | holds |
|---|---|
| text | the whole `SKILL.md`, front matter included |
| config `skill` | `checklist`, `name`, `version`, `role` (`entry`, `leaf` or `shared`), `content_hash`, `release` |
| config `schema`, `eval-manifest` | the skill's contracts, where it owns them |
| config `model-defaults` | on the entry point only |
| tags | the role |

`release` is the digest of the whole published skill set, so all of a release's prompts carry the same value.

### Publishing (mmQC)

`publication.skill_payloads(checklist_dir)` builds the payloads, after checking the production rules. mmQC's publisher, `.github/scripts/publish_langfuse_skills.py`:
- `--dry-run` writes the payloads, with no credentials needed;
- a real run skips a release the store already carries, otherwise publishes every skill, then loads the release back uncached and compares it with the repository.

### Pulling (applications)

`publication.load_published_checklist(client, checklist, entry, dest)`:
- fetches the entry point and follows each skill's `requires` to the next, which reaches exactly the published set, because nothing pinned is unreached;
- writes an ordinary checklist directory, so validation, assembly and sessions run on it unchanged;
- refuses skills from two releases (a publish in progress), and text that does not match its content hash.

On top of it, the `mmqc-skills` command and its functions:

| command | function | does |
|---|---|---|
| `pull` | `pull_checklist` | fetches the published release into a temporary directory, checks it (hashes, one release, the production rules, the entry point), writes `release.json`, then swaps it into place. A refused pull leaves the previous copy, and a current copy that verifies is left alone |
| `verify` | `verify_local_checklist` | offline: each `SKILL.md` against `release.json`, and the production rules |
| `status` | `published_release` | compares the local release with the published one; exit 1 when they differ |

`release.json`:

```json
{
  "checklist": "fig-checklist",
  "entry": "do-fig-checklist-pm",
  "label": "production",
  "release": "a3280625…",
  "fetched_at": "2026-10-24T13:51:02+00:00",
  "skills": {"classify-panels": {"version": "v1", "content_hash": "…"}, "…": "…"}
}
```

`SKILL.md` files come back byte-identical to the repository's. The contract files come back equal in content, rewritten from the prompt's config.

---

## 8. Reference

### Package `mmqc_harness`

| name | signature, and what it does |
|---|---|
| `ExampleContent` | dataclass: `source_root`, `parts`, `files`, `label`, `exclude=()` |
| `RuntimeLayout` | dataclass: the assembled runtime's paths (`root`, `skills_root`, `input_root`, `artifacts_root`, `agent_home`, `orientation_path`, `schema_path`), `entry_point`, `example`, `input_parts`, `orientation_source` (a path, or `"default"`), `orientation_sha256` |
| `figure_parts` | `(source, caption) -> tuple of parts`: the caption, then the figure converted once |
| `figure_image_part` | `(source) -> part`: the figure converted once, as bytes |
| `assemble_runtime` | `(checklist_dir, check, content, *, root=None, parent=None, pins=None, assembly="closure", orientation=None) -> RuntimeLayout`. `orientation` is a file copied verbatim as the runtime's `CLAUDE.md`; `None` uses the harness's template |
| `runtime_session` | the same as a context manager, `keep=False`; removes the runtime on exit |
| `session_options` | `(layout) -> dict`: the permission profile |
| `effective_session_options` | `(layout, skills, *, defaults=None) -> dict`: plus the checklist's session defaults |
| `run_session` | `async (layout, *, client=None, options=None, trace_path=None, versions=None, audit_log=None, approver=None) -> (answer, trace, audit)`. `client` replaces the SDK, for tests; `versions` labels the trace; `approver` asks a human before each tool call (interactive use only) |
| `validate_skills` | `(checklist_dir) -> {name: {version: Skill}}`, or `ValueError` naming every problem |
| `call_closure` | `(entry, selected) -> set of names` |
| `checklist_pins` | `(checklist_dir) -> {name: version}`, or `None` without a manifest |
| `load_model_defaults` | `(checklist_dir) -> ModelDefaults`, with `.model_for(provider)` and `.session` |
| `skill_content_hash` | `(skill) -> str`: SHA-256 of a `SKILL.md` |
| `Skill`, `SkillSet` | a skill version as read; a set of pinned versions, with `.digest` |

### Module `mmqc_harness.publication`

| name | signature |
|---|---|
| `production_entry_point` | `(checklist_dir) -> str`, or `ValueError` naming every broken rule |
| `skill_payloads` | `(checklist_dir) -> list of {name, prompt, config, labels, tags, type}` |
| `load_published_checklist` | `(client, checklist, entry, dest, *, label="production") -> Path` |
| `pull_checklist` | `(client, checklist, entry, dest, *, label="production") -> release record + changed` |
| `verify_local_checklist` | `(path) -> release record`, or `ValueError` |
| `published_release` | `(client, checklist, entry, *, label="production") -> str` |
| `prompt_name` | `(checklist, skill) -> "skills/<checklist>/<skill>"` |

A `client` needs only `get_prompt(name, label=...)`, returning an object with `prompt` and `config`, as Langfuse's does. Publishing also needs `create_prompt(**payload)`.

### Module `mmqc_harness.render`

`render_anthropic(parts, root)`, `render_openai(parts, root)`, `image_bytes(part, root)`, `image_fingerprints(parts, root)`.

### Environment

| variable | used by |
|---|---|
| `ANTHROPIC_API_KEY` | every session (the Agent SDK) |
| `MAGICK_HOME` | figure conversion, when ImageMagick is not on the library path (macOS + Homebrew: `/opt/homebrew/opt/imagemagick`) |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` (or `LANGFUSE_HOST`) | `mmqc-skills pull` and `status`, and publishing |

The harness reads no `.env` file and configures no logging handlers. It logs under `mmqc_harness`.

### Versions

The Agent SDK is pinned exactly. A new SDK can change how a session behaves, so bumping it is a release of the harness, and mmQC re-benchmarks under the new pin before production adopts it.
