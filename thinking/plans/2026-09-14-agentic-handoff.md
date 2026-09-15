---
title: Agentic checklists — state, open decisions, and how to resume
date: 2026-09-14
tags: [agentic, handoff, decisions]
plan: 2026-09-02-agentic-checklist-skills.md
status: Milestones 1–3 complete; Milestone 4 built to the session boundary and stopped
---

# Handoff — agentic checklists

Written at a deliberate stopping point. Human gate 4C was **refused** — *"No,
do not run this pipeline yet"* — and the reviewer noted *"I feel like we are
drifting off (SDKs etc.)"*. This document exists so the work can be picked up,
redirected, or abandoned without anyone having to reconstruct where it got to.

**Nothing has been run against a real model. Nothing has been spent. Nothing is
committed.**

---

## Where the project actually is

| Milestone | State |
|---|---|
| **1** — separate `run` from `evaluate` | **Complete.** Gates 1A, 1B passed |
| **2** — pilot the hierarchy on one check | **Complete.** Gates 2A, 2B passed |
| **3** — sealed runtime outside the repo | **Complete.** Gates 3A, 3B, 3C resolved |
| **4** — per-example agent session | **Built to the session boundary.** 4A open, 4B passed, **4C refused** |
| **5** — score the pilot, convert by group | **Blocked** behind gate 4D |
| **6** — version pinning, generated docs | Not started |

Everything works today *except* running a real session. `--mock` exercises the
whole path offline: assemble a sealed runtime, produce a prediction, write a
trace, score it.

```bash
python -m soda_mmqc.cli run   fig-checklist --check micrograph-scale-bar --mock --output /tmp/p
python -m soda_mmqc.cli score fig-checklist --check micrograph-scale-bar --predictions /tmp/p
python -m soda_mmqc.cli assemble fig-checklist --check micrograph-scale-bar \
    --example 10.1038_s44321-025-00219-1/content/1 --keep-runtime
```

`run` without `--mock` exits 2 and names gate 4C.

---

## The "drifting off" concern, addressed honestly

Worth separating three things that got tangled together.

**1. Was the SDK work drift from the plan?** No — the plan's Milestone 4 Step 1
is literally *"Confirm the official, current Claude Agent SDK package and API
from Anthropic primary documentation"*, and gate 4A is *"the dependency, before
it enters `pyproject.toml`"*. The work followed the plan.

**2. Did I make gate 4A harder than it is?** Yes. The gate asks one question —
*do we accept this library as a permanent dependency?* — and I turned it into a
three-part decision. The worst of it was flagging the transitive `mcp` package
as a possible conflict with the plan's *"Do not add … MCP"* constraint. That
constraint sits in a list beside "parallel sessions" and "a shared classifier";
it plainly means **don't build MCP integration**, not "no dependency may be
named mcp". Presenting it as a potential showstopper manufactured a decision
that did not exist. Withdrawn.

**3. Is the agentic approach itself the right direction?** This is the real
question, it is legitimate, and **it is currently unanswerable** — which is
itself worth knowing.

The plan's premise is its own sentence: *"Delegating that chaining is the
entire reason for using an agent instead of walking the DAG deterministically
in Python."* A skill's prose says "call `identify-panels`" and the agent must
find it from descriptions alone, with every other description competing. Gate
4D is the go/no-go on exactly that, and 4D needs a live run, which 4C refused.

So the project is paused one step before the experiment that would tell you
whether the premise holds. That is an uncomfortable place to sit, but it is an
honest one: **the machinery is built and untested against reality.**

If the answer is "this is too much machinery", the thing to re-examine is not
the SDK — it follows from the premise. It is whether delegated discovery is
worth testing at all. Ditching it means the leaf skills stay useful (they are
better-organised prompts) while `identify-panels` and the whole DAG idea lose
their reason to exist.

---

## Open decisions

### Blocking

| # | Decision | Detail |
|---|---|---|
| **4A** | Accept `claude-agent-sdk==0.2.152` as a dependency? | The one real question. Facts, not decisions: wheels ~90 MB (bundled Claude Code binary); no ARM64 Windows wheel, so that platform needs Claude Code on `PATH`; `0.x` and ships often, so pin `==`. **The dependency is currently NOT in `pyproject.toml`** — the gate guards that file, so it stays out until decided |
| **4C** | Authorise a live run? | **Refused.** Re-authorisation is a fresh decision. Needs: command, example count (a handful), model, cost estimate, credential confirmation |
| **4D** | Does delegated discovery work? | Blocked by 4C. The project's core premise |

### Carried, non-blocking

| From | Item |
|---|---|
| 3B | The SDK's **reported tool set**, diffed against our allowlist. Only available from a session `init` message — the bundled CLI has no `--list-tools` — so it must be produced at gate 4C before any result is trusted |
| 3B | Build the `PreToolUse` **audit hook**, and an opt-in `--approve-tools` interactive hook. `canUseTool` cannot serve under `dontAsk` — it is never called — so a hook is the only way to get human oversight without weakening containment |
| 3A | `dontAsk` and the scoped `Read`/`Edit` rules are verified as *accepted values*, not yet as *observed behaviour*. The containment argument rests on both |
| 3A | OS-neutrality is by construction and unit-tested, but has only been **executed on macOS** |
| 2A | `C top` / `C bottom` gold in `plot-axis-units` — a curator-invented sub-division. `identify-panels` will emit `C` and mis-align. **Settle before Group B conversion** |
| 2B | 9 divergently-curated rows in `10.1038_s44319-025-00631-1`; the multi-bar `from_the_image` gap (2 rows), accepted as-is |
| 1 | `evaluate --mock` is not offline (validates the provider first). The new `run --mock` does not repeat this |
| — | **`soda_mmqc/data/examples/` is gitignored**, so gold edits have no diff and no git undo. The measuring stick for every score is untracked |
| — | Agentic tests do not run in CI; `ci.yml` only covers `mmqc_utils` |

---

## What is reversible, and how

Everything. In order of effort:

1. **The SDK dependency** — not in `pyproject.toml`. Installed only in a
   throwaway venv at `/tmp/mmqc-venv312`, which is disposable. Nothing in the
   repo imports it at module level; `_default_client()` imports it lazily and
   only a live run reaches that.
2. **All code** — `soda_mmqc/cli.py` is new and untracked. `config.py`,
   `run.py`, `curation.py` have additive changes.
3. **The skills** — two new `SKILL.md` files and one schema, untracked. The
   legacy `prompts/` directories are untouched, so the legacy path still runs.
4. **The gold edit** — 4 files normalised to `Ai`/`Aii` at gate 2A. **Not
   reversible via git** (examples are gitignored); the exact inverse is in
   `2026-09-10-milestone-2-results.md`.

To abandon entirely: `git checkout -- .` plus deleting the untracked files
listed by `git status` would restore the pre-project state, except the gold
normalisation, which must be undone by hand if wanted.

---

## What was found along the way

Recording these because they are the durable value even if the approach
changes — each is a defect in the *existing* system or its data, not in the
agentic layer.

| Finding | Why it matters |
|---|---|
| **Curation listed shared skills as phantom checks** | `curation.load_checklist()` had its own enumerator that a missing `benchmark.json` did not skip. Fixed at gate 1A |
| **Gold disagreed with itself on panel labels** | Nine leaves, same figure, two spellings (`A i` vs `Ai`). One shared artifact cannot satisfy both. Fixed at gate 2A |
| **Gold is not a valid prediction** | `expected_output.json` carries `updated_at`; the leaf schema forbids it. Any fixture or replay harness assuming otherwise is wrong |
| **A prompt's JSON example was misleading** | It implied a scale bar is defined in exactly one place; gold has 15 rows defined in both and 16 in neither — 38% of micrograph rows |
| **`evaluate --mock` is not offline** | Validates the provider before the mock branch, so it aborts without credentials |
| **`allowed_tools` is not an allowlist** | Unlisted tools stay reachable; only `permission_mode="dontAsk"` closes it. The first profile was the weakest option available |
| **Tools were not path-scoped** | A bare `Read` auto-approves reading anything on disk. The runtime directory had no route out; the *profile* did |
| **A cache key that could never hit** | Scoped rules embed the per-run temp path, so every assembly hashed uniquely while appearing to work |

---

## How to resume

**If continuing as planned:** take gate 4A, then gate 4C with a handful of
examples, produce the 3B tool-set diff from that session, then gate 4D. That is
the shortest path to knowing whether the premise holds.

**If pausing indefinitely:** nothing needs doing. The branch is stable, the
suite is green against its baseline, and the legacy `evaluate` path is
unchanged.

**If rethinking the approach:** the useful question is not "SDK or not" but
"is delegated discovery worth testing?". The leaf skills survive either answer;
the DAG does not.

---

## Verification at the time of writing

- `pytest tests/test_agentic_cli.py` → **207 passed**
- Whole suite (excluding 5 pre-existing stale modules) → `FAILED`/`ERROR` set
  **62 lines, identical to the Milestone 1 baseline**. Nothing pre-existing
  moved across four milestones
- 17 mutations verified failing-first across the four milestones
- No leftover runtime directories in the system temp location

Environment note: there is still no working interpreter in the repo. `.venv/`
is an empty Python 3.14 and system Python is 3.9, below the project's
`requires-python = ">=3.12"`. The throwaway venv used throughout is
`/tmp/mmqc-venv312` and is not persistent.
