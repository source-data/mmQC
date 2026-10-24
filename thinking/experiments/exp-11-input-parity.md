---
title: exp-11 — the figure as production sends it, against the stored file
date: 2026-10-24
status: done           # draft | planned | running | done | abandoned
kind: experiment
tags: [experiment, input, images, production, sonnet, non-inferiority]
---

# exp-11 — the figure as production sends it, against the stored file

*A non-inferiority test, committed before the run.*

## Question

On the production checklist (`fig-checklist`, panel-major, Sonnet 5.5), are
the scores obtained when each figure is **converted as production converts
it** not worse than the scores obtained from the **stored file**, which is
what every run of the series has sent?

## Why

The harness is moving into `mmqc_utils` so that production runs what mmQC
benchmarks ([`plans/2026-10-23-harness-in-mmqc-utils.md`](../plans/2026-10-23-harness-in-mmqc-utils.md),
Milestone 4). The model's input is part of that, and it differs today:

- **The benchmark** sends each figure's stored file as it is: 15 PNG,
  14 WebP, 8 JPEG, published figures downloaded from journal websites.
  30 of 37 exceed 2,048 px on their longest side.
- **Production** converts each figure with `convert_to_bounded_jpeg`:
  rasterized at 300 dpi, longest side 2,048 px, JPEG quality 80. At
  soda-curation 3.8.2 it then re-encodes the JPEG a second time; that is a
  bug, reported separately.

`mmqc_utils.agentic.figure_parts` now holds production's conversion, done
once, for both. Decided with the author (2026-10-24), the benchmark will
process its figures **as if they were submissions** through that builder.
Some authors do submit JPEGs.

This experiment measures what that switch costs. If the converted figures
score no worse, the series' results carry over to the input production sends,
and the builder becomes the benchmark's only image path. If they score worse,
the conversion is what has to change, because production cannot send the
stored file.

**Scope.** This measures the *encoding* gap only: the same published figure,
stored versus converted. The larger gap, between a published figure and the
file its author submitted (layout, labelling, resolution, text rendering), is
not measured. It needs the submitted files of the benchmark manuscripts.

**What the provider does anyway.** Sonnet 5.5 is in the high-resolution
tier: an image is downscaled to at most 2,576 px on its long edge and 4,784
visual tokens of 28×28 px (vision docs, 2026-10-23). By that rule the model
sees a median of 3.7 megapixels of a stored figure, and 0.63–1.00 times as
many pixels of the converted one (median 0.93; within 2% for 13 of 37). The
largest losses are on wide figures. The converted arm also turns every PNG
and WebP into a lossy JPEG.

## Design

| | |
|---|---|
| Checklist | **`fig-checklist-exp11`**: a copy of `fig-checklist` as of this commit, the production topology and pins (`do-fig-checklist-pm` v1, `classify-panels` v1, the eleven checks v2), contracts byte-identical |
| Arms | **stored**: the figure's file as stored (`FigureExample`, unchanged). **converted**: the same file through `figure_image_part` (300 dpi, 2,048 px, JPEG 80), sent as bytes |
| What differs | the image bytes alone. Caption, its position, skills, contracts and gold are identical |
| Model, provider | `claude-sonnet-5-5`, `claude-sdk` 0.2.165 |
| Gold | `gold-v7` (exp-10's), the panel-major merged gold |
| Figures | exp-07's 37 |
| Replicates | **3 per arm** (decided with the author, 2026-10-24; the replicate-variability exploration found 3 enough except for one property), **both arms run the same day** (as exp-10) |
| Concurrency | 38 |
| Sessions | 2 × 37 × 3 = **222** |
| Budget | exp-10's panel-major arm cost $28.59 for 185 sessions ($0.155 a session). Expected about **$34**, a little less on the converted arm (fewer image tokens). **Ceiling $50**: stop and report if it is passed |

**Verification of the arms.** Every session now records a fingerprint of each
image it sends (`tool_audit.json`, `inputs`). Before any analysis, the
notebook checks:

- every stored-arm session sent its file's own bytes, by SHA-256;
- every converted-arm session sent `figure_image_part`'s bytes for that
  file;
- the converted bytes are identical across the arm's 3 replicates.

A run that fails any of these is not analysed.

## What is measured

As exp-10, per arm:

- **dispatch**: all eleven checks, partial, none;
- failures, fallback;
- layer S, layer 1, layer 2 per property;
- each check's decision;
- spurious, missing and partly missing panels per figure;
- **input tokens**, output tokens, cost, turns and time;
- the image as sent, per arm and figure: media type, bytes, dimensions.

## The hypothesis

**Converted is non-inferior to stored.** For E1 (layer S, both errors,
pooled over the checks) and E2 (layer 1, pooled), the paired difference over
figures, **converted minus stored**, has a 95% bootstrap interval whose lower
bound is above **−0.02** (exp-10's margin).

- **Non-inferior:** both bounds hold.
- **Inconclusive:** either lower bound at or below −0.02, with its interval
  including 0.
- **Inferior:** either interval wholly below 0 and past −0.02.

**Secondary**, reported, not in the verdict:

- E3, the eleven decisions, classified the same way;
- layer 1 per check, and the checks that read fine text
  (`micrograph-scale-bar`, `plot-axis-units`, `stat-significance-level`)
  separately;
- whether the per-figure difference grows with the pixels lost (converted
  over stored, as above);
- input tokens and cost.

**What each outcome decides** (gate 4B):

- **Non-inferior:** the builder becomes the benchmark's only image path.
  Earlier results stand, read as describing production's input.
- **Inconclusive:** the builder still becomes the only path, because
  production cannot send the stored file. Results before the switch are
  marked as measured on stored files, and later comparisons are not made
  across the switch.
- **Inferior:** the conversion is revisited before anything is switched:
  quality, size or format, with exploration first, then a new experiment.

## Threats to validity

- **Published figures stand in for submissions.** A published figure has
  already been typeset and compressed by its publisher. The test is what
  production's conversion does to *a* figure, not to what authors send.
- **The provider resizes both arms.** A difference can only come from what
  survives its downscaling, which narrows the resolution part of the
  comparison and leaves the compression part.
- **One model, 37 figures, many intervals,** as in exp-10.
- **The skills were tuned on stored figures,** since exp-01.

## Preparation

| # | step | done |
|---|---|---|
| P1 | `fig-checklist-exp11`: a copy of `fig-checklist`, `dag.yaml` and README regenerated. Only the manifest and the generated views differ; the skill-set digest equals production's (`a3280625…`) | 2026-10-24 |
| P2 | The converted arm: an example class, `figure-converted`, whose image part comes from `figure_image_part`. `run_check_live` takes an `example_class` override for the run, so the same checklist and contracts run either input. **Temporary**: both are removed after exp-11, at gate 4B (decided with the author) | 2026-10-24 |
| P3 | `experiments/exp-11-input-parity/run.py`: both arms, 3 replicates, concurrency 38; `--smoke` for 3 figures, one replicate. Refuses to start if ImageMagick cannot be loaded (`MAGICK_HOME`) | 2026-10-24 |
| P4 | Dry run of both arms. `--mock` assembles no runtime, so it would test nothing here. Instead, the real runner ran both arms on 2 figures with the SDK replaced by a client returning an empty answer: no failure, the stored arm sent its WebP files, the converted arm sent JPEG bytes (2048×1552, 1606×2048), and every recorded fingerprint matched the arm's expected bytes | 2026-10-24 |
| P5 | Smoke test: both arms on 3 figures, one replicate; the fingerprints checked | 2026-10-24, below |
| P6 | Notebook `notebooks/experiments/exp-11-input-parity.ipynb`: exp-10's, two arms, the fingerprint verification first (it stops the notebook on any mismatch), and the secondary pixel-ratio analysis. Executed on the smoke output, end to end | 2026-10-24 |

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| 2026-10-24 | smoke, both arms | `MAGICK_HOME=… run.py --smoke` | $1.16 | `experiments/runs/exp-11-input-parity/smoke/` (not committed) |
| 2026-10-24 | both arms, 3 replicates | `MAGICK_HOME=… caffeinate -i python experiments/exp-11-input-parity/run.py` | $34.16 ($16.93 stored + $17.24 converted) | `experiments/runs/exp-11-input-parity/`; 222 of 222 answered |

**Smoke test, 2026-10-24.**

- `s44318-026-00715-1` content/1–3, one replicate per arm: 6 sessions,
  none failed, all eleven checks in 6 of 6.
- Every image as its arm requires: stored sent the WebP files (up to
  2,693 px), converted sent JPEG bytes (2,048 px on the long edge).
- Cost $0.162–0.250 a session; 26–28 turns.

## Findings

From `notebooks/experiments/exp-11-input-parity.ipynb`, run on 2026-10-24.

### The arms sent what they claim

All 222 sessions passed the fingerprint check: each sent exactly the image its
arm requires, and every figure was converted to the same bytes in all three
replicates.

| arm | media type sent (sessions) | median size | median long edge |
|---|---|---|---|
| stored | PNG (45), WebP (42), JPEG (24) | 0.46–1.99 MB | 1,716–2,746 px |
| converted | JPEG (111) | 0.37 MB | 2,048 px |

No session fell back to another model; 222 of 222 answered.

### The verdict: **non-inferior**

| endpoint | stored | converted | converted − stored | 95% interval | verdict |
|---|---|---|---|---|---|
| E1 layer S | 0.9768 | 0.9969 | +0.0200 | [−0.0062, +0.0575] | non-inferior |
| E2 layer 1 | 0.9774 | 0.9840 | +0.0066 | [−0.0043, +0.0218] | non-inferior |

Both lower bounds are above −0.02.

### Reading

**The difference in the converted arm's favour is dispatch, not images.**

| | stored | converted |
|---|---|---|
| sessions with all eleven checks | 101 | 106 |
| partial | 8 | 5 |
| no check | 2 | 0 |
| E1, sessions with all eleven checks | 1.0000 | 0.9969 |
| E2, sessions with all eleven checks | 0.9863 | 0.9841 |

On complete sessions the two arms are level. Skipped checks are the
series' known stochastic failure (exp-07); nothing here says the encoding
caused them, and this experiment cannot tell.

**Secondary, E3.**

- Nine of the eleven decisions are non-inferior.
- Two are inconclusive:
  - `panel-image-matches-caption`: −0.0123 [−0.0273, +0.0004];
  - `stat-significance-level`: −0.0021 [−0.0290, +0.0202].
- The first is the check that compares the image with the caption, which
  makes it the one to watch if the conversion is ever tightened. Neither
  is in the verdict.
- `micrograph-scale-bar` and `plot-axis-units`, the other fine-text checks,
  are equivalent.

**Pixels lost do not predict the difference.**

- Model-seen pixels, converted over stored: median 0.93, range 0.63–1.00.
- Spearman correlation with the per-figure E2 difference: −0.02.
- The largest per-figure difference (+0.19, `s44321-025-00219-1` Fig. 1)
  is a figure with partial sessions in both arms.

**Cost is unchanged.**

| | stored | converted |
|---|---|---|
| cost per session | $0.153 | $0.155 |
| input tokens | 63.7k | 64.9k |
| output tokens | 9.5k | 9.6k |
| time per session | 51.5 s | 51.5 s |

**For gate 4B.** As preregistered, a non-inferior verdict decides that the
builder becomes the benchmark's only image path, and that earlier results
stand, read as describing production's input. The temporary
`figure-converted` class and the `example_class` override are then removed
(plan, Milestone 4).

**Not measured, as stated in Scope:** published against submitted figures.

**Gate 4B, 2026-10-24: accepted** (Thomas Lemberger).

- `FigureExample` now sends the converted figure, and the temporary switch
  is removed.
- From then on, `run.py` refuses to rerun; check out `24e99b665` to repeat
  either arm.
- The notebook still verifies these runs against the stored files.
