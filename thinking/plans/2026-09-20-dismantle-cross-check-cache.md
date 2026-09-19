---
title: Remove --all-checks and its cache/deny apparatus
date: 2026-09-20
status: planned, not started
---

# Remove `--all-checks` and its cache/deny apparatus

## The principle

**One session per (example, check).** The harness walks examples and checks
mechanically; everything about which skills get called, and in what order,
belongs to the agent.

A skill that is parent to eleven leaves therefore runs eleven times for one
example. That is not waste to be optimised away — **it is the measurement.**
Whether a shared skill is reached, and how it is used, may differ depending
on which leaf is the entry point, and that difference is what the experiment
series exists to detect. A harness that runs the parent once and reuses the
result erases the very signal being looked for.

If a shared parent *should* be invoked once for a whole checklist, the way
to express that is a **DAG whose entry point is a master skill that calls
each check-specific skill**. Then the agent invokes `identify-panels` once
and carries its inventory in context through every check that follows —
sharing, in one session, done by the agent. That is a hypothesis worth
testing, and it needs no harness support: a master entry point is just
another skill.

What is not acceptable is the harness reaching across sessions to suppress a
skill call and substitute a stored answer.

## What `--all-checks` does today

After the first check for an example produces a shared artifact, it **denies
that shared skill to every subsequent check** and seeds the cached artifact
into their runtimes. So:

- results depend on check order — the first check alphabetically runs
  `identify-panels`, the other ten are refused it;
- ten of eleven checks never exercise the DAG discovery under study;
- a check's behaviour depends on whether a *different* check succeeded.

Inert since `218fe013` removed the write tool — nothing is produced, so
nothing is cached or denied — but still wired, and one skill that writes
anything brings it back. The seeding path is self-contradictory now as well:
it plants files into `artifacts/` that the session is denied the ability to
create.

## Decision

Remove `--all-checks` entirely, along with its apparatus. Running every
check over every example is a loop the caller can write, and doing it in the
harness invited the coupling.

`run_check_live` — one check, one session per example — stays as the single
execution path.

## What to remove

Line numbers against `218fe013`.

| Where | What |
|---|---|
| `cli.py` | the `--all-checks` flag and its branch in `main` |
| `cli.py:3021+` | `run_checklist_live` in full |
| `cli.py:3008-3013` | `cache`, `denied`, `shared_by_check`, `producers` |
| `cli.py:2773-2774` | `seed_intermediates` / `shared_skill_denials` parameters |
| `cli.py:2844-2850` | seeding cached artifacts into `artifacts/` |
| `cli.py:2855-2870` | assembling `denied_shared`, passing it to the session |
| `cli.py:2277`, `2303` | `denied_shared_skills` through `_run_agent_session` |
| `cli.py:2615`, `2641-2655` | the hook branch that denies the `Skill` tool |
| `cli.py` | `_required_shared_skills`, if nothing else uses it |
| `tests` | the `--all-checks` tests, incl. assertions at 4741-4742 |

## What to keep

- `run_check_live`, unchanged in behaviour.
- `--check`, `--example`, `--limit`: the harness's mechanical selectors.
- `entry["intermediates"]` **only if** something still reads it — it existed
  to feed the cache.

## Order

1. Remove the denial path first (hook branch, both parameters, call site).
   It is self-contained, and it is the part that changes what the agent may
   do.
2. Remove the seeding path.
3. Remove `run_checklist_live` and the `--all-checks` flag.
4. Replace the `--all-checks` tests with one asserting the invariant that
   matters: **no run is ever denied a skill, and no runtime is ever seeded
   with an artifact the session did not produce.** Deleting the tests would
   leave that unguarded.

## Verification

- `pytest tests/test_agentic_cli.py` green; the new test fails if the
  apparatus returns.
- No `"denied in this run"` in any `tool_audit.json`.
- A `--check` run still completes with its hop chain intact.

## The experiment this opens

Two ways to run eleven checks over one figure:

- **Eleven sessions, one per check.** Each discovers its own chain; the
  shared parent runs eleven times. Independent, and each check is scored on
  its own merits.
- **One session, entry point a master skill that calls all eleven.** The
  shared parent runs once and its result is in context for everything after.

That comparison is a real experiment — cost, accuracy, and whether the agent
actually fans out from a master entry point — and it needs no harness
feature, only a checklist shaped that way. Two obstacles to note before
designing it: `output_format` yields **one** structured answer per session,
so eleven predictions from one session need a different delivery mechanism;
and checks sharing a context can influence one another, which is a
confound for per-check scoring and possibly the finding itself.

## Not in scope

- `produces` / contract edges (`tl_dev_agentic` models `requires: [panels]`
  against `produces: [panels]`, with `kind: leaf|intermediate`).
- `validate_intermediates` and the rest of the file-based plumbing.
