---
title: Dismantle the --all-checks cache/deny apparatus
date: 2026-09-20
status: planned, not started
---

# Dismantle the `--all-checks` cache/deny apparatus

`--all-checks` does more than loop. After the first check for an example
produces a shared artifact, it **denies that shared skill to every
subsequent check** and hands them the cached artifact instead.

The consequences, when it was live:

- results depend on check order — the first check alphabetically runs
  `identify-panels`, the other ten are refused it;
- 10 of 11 checks never exercise the DAG discovery the paper is about;
- a check's behaviour depends on whether a *different* check succeeded.

It is inert today only because the session has no write tool (`218fe013`),
so `produced` is always empty and the loop never populates `denied` or
`cache`. One skill that writes anything brings it all back. The seeding path
is also now self-contradictory: it plants files into `artifacts/` that the
session was deliberately denied the ability to create.

**Goal:** `--all-checks` means the harness walks checks and examples. Each
`(check, example)` run is independent, discovers its own DAG, and cannot be
influenced by another check's run.

## What to remove

All line numbers against `218fe013`.

| Where | What |
|---|---|
| `cli.py:2277` | `denied_shared_skills` parameter on `_run_agent_session` |
| `cli.py:2303` | third argument passed to `make_pretooluse_hook` |
| `cli.py:2615` | `denied_shared_skills` parameter on `make_pretooluse_hook` |
| `cli.py:2641-2655` | the hook branch that denies the `Skill` tool by name |
| `cli.py:2773-2774` | `seed_intermediates` / `shared_skill_denials` parameters on `run_check_live` |
| `cli.py:2844-2850` | seeding: writing cached artifacts into `artifacts/` |
| `cli.py:2855-2870` | assembling `denied_shared` and passing it to the session |
| `cli.py:3008-3013` | `cache`, `denied`, `shared_by_check`, `producers` bookkeeping |
| `cli.py:3036-3037` | the two arguments at the `run_check_live` call site |
| `cli.py` | the post-run block that fills `denied` and `cache` from each report |
| `cli.py` | `_required_shared_skills`, if nothing else uses it |
| `tests/test_agentic_cli.py:4741-4742` | the two assertions on seeding and denial |

## What to keep

- The loop itself: `for check in checks: run_check_live(...)`.
- Per-check output directories and the combined report.
- `entry["intermediates"]` **only if** something still reads it; it was the
  cache's input, so check before keeping.
- `validate_intermediates` — decide separately. It is also file-based and
  also inert now, but it is not part of this apparatus.

## Order

1. Remove the denial path first (hook branch, both parameters, the call
   site). It is self-contained, and denying a skill is the part that
   actually changes what the agent may do.
2. Remove the seeding path.
3. Remove the bookkeeping in `run_checklist_live`, leaving a plain loop.
4. Rewrite the test at 4741 to assert the opposite property: that a second
   check is **not** seeded and **not** denied anything — the invariant worth
   protecting, so nobody reintroduces coupling quietly.

## Verification

- `pytest tests/test_agentic_cli.py` green, and the rewritten test fails if
  the apparatus returns.
- **Run `--all-checks` for real, on one example.** It has probably never
  been exercised on this branch: Çağatay added it in `c8dc2834` and its
  caching path cannot have worked since the write tool went. Expect 11
  sessions for one example, each with its own hop chain, each invoking
  `identify-panels` itself.
- Confirm no run is denied a skill: no `"denied in this run"` in any
  `tool_audit.json`.

## Cost, accepted deliberately

`identify-panels` runs once per check rather than once per example — 11
sessions of shared work instead of 1. That is the price of independence and
the right default for an experiment. If reuse is wanted later it should
return as something explicit and declared, not as a side effect of run
order.

## Not in scope

- `produces` / contract edges — a separate design question
  (`tl_dev_agentic` models it as `requires: [panels]` matched against
  `produces: [panels]`, with `kind: leaf|intermediate`).
- `validate_intermediates` and the rest of the file-based intermediate
  plumbing.
- Whether `--all-checks` should exist at all, versus the caller looping.
