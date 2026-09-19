---
title: Runtime contract — design update
date: 2026-09-19
status: proposed, awaiting review
---

# Runtime contract — design update

Three structural changes to how the harness hands a run to the agent. All
three were surfaced on 2026-09-19 while fixing a defect that had made every
agentic run read no figure at all (`37dff7c7`), and none is a regression from
that fix: they were always there, hidden behind it.

**Nothing here changes what the agent is allowed to do.** No new tools, no
`Bash`, no `Glob`, no subagents. Each change moves work *out* of the agent
and into the harness.

---

## 1. Enforce the output schema mechanically

### Now

`ORIENTATION.md` names the schema in prose — *"The answer must conform to it
exactly"* — the session writes `artifacts/prediction.json` with the `Write`
tool, and the runner validates it afterwards with `validate_against_schema`.
A malformed answer is a failed run, discovered late.

### Proposed

Pass the leaf schema to the SDK as structured output:

```python
output_format={"type": "json_schema", "schema": <leaf schema>}
```

The Milestone 2 spike already established this works and recommended it
(`agentic-m2-spike-findings.md` § C2): tested against the real
`micrograph-scale-bar` schema — nested arrays, `yes`/`no`/`""` enums — with
enforcement reaching enum level. The model could not write `"MAYBE"` into
`micrograph` even when instructed to. The verdict was *"use `output_format`;
do not build `submit_check_result` for v1"*. This branch never implemented
it.

### The decision this forces

With `output_format`, the answer arrives as the session's result rather than
as a file the agent remembered to write. Two options:

- **(a) Result is the source of truth.** The runner writes
  `prediction.json` itself from the returned JSON. Removes two failure
  modes outright — "the session never wrote the file" and "the file is not
  valid JSON" — and puts serialization where the harness belongs.
- **(b) Keep the file as the contract**, adding `output_format` as a second
  belt.

**Recommendation: (a).** It is the same principle as naming the inputs: the
harness owns the mechanics, the agent owns the judgement.

`Write` stays allowed regardless — `identify-panels` writes
`artifacts/panels.json` for fan-in, which is a different artifact.

### Caveat, from the spike

When the model cannot satisfy the schema it stops and explains itself in
prose, so the result is *not* guaranteed to be JSON. `json.loads` failing is
the signal. `validate_against_schema` stays as the backstop.

---

## 2. Replace `ORIENTATION.md` with a standard `CLAUDE.md` and a manifest

### Now

A per-run `ORIENTATION.md` is generated, carrying both static layout rules
and per-run facts as prose. The session prompt says *"Read ORIENTATION.md and
follow it"*, and **call 1 of every trace is that read** — a turn spent on
something the convention supplies for free.

### Proposed

Split it by what changes:

- **Static `CLAUDE.md`**, copied verbatim into the runtime root: the layout,
  the rules, where to write, that paths outside the runtime do not exist.
  Identical for every run, editable as prose, reviewable once.
- **Per-run `input/inputs.json`**, machine-readable, naming exactly what was
  staged: the figure, the caption, the source-data files.

The SDK loads `CLAUDE.md` automatically when `setting_sources` includes
`"project"` — its own documentation says *"Must include `project` to load
CLAUDE.md files"* — and we already pass exactly that. The `init` message
reports `memoryFiles` ("CLAUDE.md and memory files loaded, with path, type,
and token counts"), so loading is **verifiable rather than assumed**.

This is what `tl_dev_agentic` does, and its `CLAUDE.example.md` says of the
manifest: *"Read it first; it saves you guessing."* The prose fix made in
`37dff7c7` was the right content in the wrong form.

### What must not move into `CLAUDE.md`

The entry point. It is per-run, and the session prompt already names it. The
DAG stays undescribed anywhere: discovering the chain from skill descriptions
is the thing being measured, and stating it would make the trace a
measurement of our own control flow. That discipline is from Step 4 of the
2026-09-02 plan and survives this change intact.

### Cost

`CLAUDE.md` sits in context for every turn rather than being read once. The
file is small; the saved turn is worth more.

---

## 3. Confine the session's ambient state

### Now

`CLAUDE_CONFIG_DIR` is not set, so each session writes its transcript to
`~/.claude/projects/<slugified-cwd>/` — outside the runtime, surviving
teardown. **22 such directories exist on this machine right now.**
`tl_dev_agentic` records ~418 from a single 11-check run.

This is a hole in a design whose premise is a sealed runtime: the transcript
holds the gold-derived reasoning the containment exists to keep in.

### Proposed

```python
env={"CLAUDE_CONFIG_DIR": str(layout.root / "agent-home")}
```

The transcript and the auto-memory directory land inside the runtime, die
with it, and — with `--keep-runtime` — are kept *with* the run they belong
to, which makes them inspectable for the first time.

Existing strays: delete, once.

---

## What stays the same

- The permission profile. No tool is added.
- Contracts held fixed: `schema.json`, `benchmark.json`, `eval-manifest.json`.
- The runtime is a copy, not a processed copy: no renaming, no conversion.
- The DAG is never described to the agent.

---

## Open questions for review

1. **Source of truth for the answer** — recommendation (a) above, the
   structured result, with the runner writing the file. Agree?
2. **Where the static `CLAUDE.md` template lives.** `tl_dev_agentic` keeps it
   at `soda_mmqc/agents/CLAUDE.example.md`; this branch has no `agents/`
   package. Suggest `soda_mmqc/data/agentic/CLAUDE.md`, copied verbatim.
3. **Gate re-review.** Human gate 3B reviewed the runtime's shape by walking
   a real assembled tree. All three changes alter that shape, so the
   walkthrough should be redone rather than assumed to carry over.

---

## Consequence worth stating before, not after

Structured output changes how the model answers, and the spike measured that
it changes behaviour — enum enforcement is real. **Runs made before and after
this change are not comparable.** Every agentic number produced so far is
already invalid for a different reason (no session read a figure), so the
cost is zero today and rises with every run made in the meantime. This is the
moment to do it: before the experiment series starts, not during it.

## Verification

- `memoryFiles` in the `init` message lists the runtime `CLAUDE.md`.
- A trace's first call is no longer a read of an orientation file.
- A session given an unsatisfiable schema fails on `json.loads`, not silently.
- The runtime contains `agent-home/`; `~/.claude/projects/` gains nothing.
- The three-example baseline still completes 3/3 and still reads the figure.

## Sequence

Each step independently revertible, verified before the next:

1. `CLAUDE_CONFIG_DIR` — smallest, no behavioural change to the model.
2. `CLAUDE.md` + `inputs.json`, removing `ORIENTATION.md`.
3. `output_format`, and the answer's source of truth.
4. Re-walk gate 3B on a real assembled runtime; re-baseline the three
   examples.
