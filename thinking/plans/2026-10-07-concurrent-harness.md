---
title: Run sessions concurrently in the harness
date: 2026-10-07
status: done 2026-10-07
---

# Run sessions concurrently in the harness

## Why

A full experiment is hundreds to thousands of sessions, and the harness ran
them one after another: exp-04's 1,140 sessions took about 17 hours, exp-05's
418 about 5. Every session is independent — its own runtime in its own
temporary directory, its own Claude Code process, its own prediction — so
nothing but the loop forced them to wait for each other.

This is a **harness** concern only. It is not the subagent question (whether
the model should dispatch work to parallel agents), which was weighed on
2026-10-07 and set aside: for a fixed checklist the work to run is known before
the session starts, so the harness can parallelise it without a model
coordinating anything. It does not touch the principle of
`2026-09-20-dismantle-cross-check-cache.md` either: sessions still share
nothing, and the harness still never reaches across them.

## What was built

`run_check_live(..., concurrency=N)` and `mmqc run --concurrency N`
(`70d6c7801`, branch `harness-concurrency`).

- **One unit of work per session** — one figure, in one arm and one replicate.
  The per-session body of `run_check_live` was lifted unchanged into a
  function; arms, replicates and figures are all units, so all run in parallel.
- **`concurrency=1`, the default, runs the units one after another**, exactly
  as before 2026-10-07.
- **Above 1, a thread pool of N workers.** Each worker runs its session's event
  loop with `asyncio.run`, as the sequential path does; the work itself is done
  by the Claude Code process the Agent SDK starts per session, so N workers
  means N such processes side by side. Threads rather than one shared event
  loop, because runtime assembly and the writing of predictions and sidecars are
  synchronous and would block a shared loop; rather than processes, because
  there is no CPU-bound Python work to distribute.
- **The report keeps the sequential order**, whatever order sessions finish in.
- **An account error still stops the run** (`RunAborted`): sessions not yet
  started are cancelled, those running finish and keep what they write.
  Rate limits and overloads are not account errors and do not stop it.
- **Interactive tool approval is refused above concurrency 1**: it asks at the
  terminal, one call at a time.
- **Each session records the concurrency it ran at** in the `session` section of
  its `tool_audit.json`, the sidecar committed with runs.
- **Ctrl-C does not interrupt running sessions** in the concurrent path: the
  pool waits for them, up to about a session's length. Kept as is
  (2026-10-07); nothing is lost and a rerun resumes.

Tests (`tests/test_run_aborted.py`): a concurrent run reports exactly what a
sequential one does; each session records its concurrency; an account error
stops a concurrent run; impossible settings are refused. They caught one bug
before any real run: cancelled futures, after an abort, raised when read.

## Measured

Configuration: `fig-checklist-exp04`, CM `A|B ← C_i ← D` (`do-fig-checklist-cm`,
checks at v3), `claude-sonnet-5`, closure assembly. Output kept out of
`experiments/runs/`. References: the same figures in exp-04's run, sessions
one at a time.

| | concurrency 4 | concurrency 38 |
|---|---|---|
| sessions | 4 figures × 2 replicates = 8 | 38 figures × 1 = 38 |
| succeeded | 8/8 | 38/38 |
| valid against the contract | 8/8 | 38/38 |
| rate-limit or overload errors | 0 | 0 |
| wall time | 140 s (449 s summed: **3.2×**) | **105 s** (about 27 min sequentially) |
| duration per session against exp-04 | within its spread (+20 s to −24 s) | median 44 s against 43 s; mean ratio 1.12 |
| cost per session | $0.101 (exp-04: $0.100) | **$0.081** (exp-04: $0.081) |
| peak memory of the session processes | — | **9.8 GB**, about **260 MB per process** |

**Prompt caching.** At concurrency 4 the first wave, started together, wrote
more to the cache and read less (53k written / 83k read, $0.447) than the
second (45k / 107k, $0.361); the sequential reference sits between ($0.401).
At concurrency 38, cache writes and reads were close to the sequential run's
(402k / 953k against 415k / 1,035k) and the cost per session identical. The
first-wave premium does not grow with concurrency, and is within the
session-to-session spread.

**Rate limits.** The organisation's limits, as quoted from the console for
Sonnet 5.5 and Opus 5.5 (per minute): 10 M input tokens excluding cache reads,
2 M output tokens, 20 K requests — **to be confirmed for `claude-sonnet-5`**,
the model the series runs. Measured on exp-04's sessions, one session uses per
minute 14–21 K input tokens excluding cache reads, 6.4–6.9 K output tokens and
12–23 requests. **Output tokens bind first, at about 300 concurrent sessions**;
input allows ~500–700, requests ~900–1,700. Averages: peaks run higher, and the
limits are shared with anyone else in the organisation.

**Memory** binds well before that on a 32 GB machine: about 260 MB per session
process, so ~10 GB at 38 and ~20 GB at 76.

## Recommendation

**Default `concurrency=1`**, so a plain call or `mmqc run` behaves as it
always has. **Experiment runs should pass `concurrency=38`**
(`RECOMMENDED_CONCURRENCY` in `soda_mmqc/agentic/runner.py`, and
`mmqc run --concurrency 38`):

- one wave covers one condition's 38 benchmark figures;
- at about an eighth of the output-token limit and ~10 GB of memory, it leaves
  room on both;
- exp-04's 1,140 sessions would take about 25 minutes instead of 16 hours;
- per-session durations and cost were indistinguishable from sequential runs.

Going to 76 would save little more at twice the memory. Above ~150, the
rate limits start to matter.

**What concurrency changes in a measurement.** Wall time per session and
prompt-cache hits can depend on it, so **time and cost endpoints compare only
between runs at the same concurrency** — exp-01 to exp-05 ran at 1; a run at 38
compared with them on time or cost must say so. Accuracy endpoints are
unaffected: sessions share nothing.
