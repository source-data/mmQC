---
title: Milestone 2 results — pilot the hierarchy on one check
date: 2026-09-10
tags: [agentic, milestone, skills, results]
plan: 2026-09-02-agentic-checklist-skills.md
status: COMPLETE — automatic gate passed; human gates 2A and 2B passed and recorded
---

# Milestone 2 Results

Outcome record for **Milestone 2: Pilot the Hierarchy on One Check** of
[`2026-09-02-agentic-checklist-skills.md`](2026-09-02-agentic-checklist-skills.md).

**Deliverable:** `micrograph-scale-bar` is an entry-point leaf whose prose
reaches one shared skill, `identify-panels` — hand-authored, with its evaluation
contracts untouched and shared across versions.

> ## Gate status — all passed
>
> | Gate | Status |
> |---|---|
> | Automatic | **passed** — 121 tests, suite failure set unchanged at 62 lines |
> | **2A** — the shared skill's wording | **PASSED 2026-09-11**, Çağatay Gürsoy, with a gold correction executed |
> | **2B** — the leaf conversion | **PASSED 2026-09-11**, Çağatay Gürsoy, no changes required |
>
> **Milestone 2 is complete and Milestone 3 is unblocked.**
>
> Both artifacts were produced under autopilot with the reviewer absent, so the
> agent could not halt and wait; it produced them in full rather than delivering
> 15% of the milestone, and started nothing downstream. Preparing them turned up
> **two real defects** — one from an independent code review, one from checking
> the skills' claims against the gold — both fixed and pinned by mutation-tested
> assertions. A third issue, a gold inconsistency the skills could not fix, was
> escalated rather than worked around and was resolved at gate 2A.

- **Branch:** `agentic`, uncommitted in the working tree
- **Baseline commit:** `60f73b22`, plus the uncommitted Milestone 1 work
- **Measured:** 2026-09-10, Python 3.12.14, pytest 9.1.1

---

## What shipped

| File | Status | What |
|---|---|---|
| `soda_mmqc/data/checklist/fig-checklist/identify-panels/v1/SKILL.md` | **new** | The shared skill, merged from three prompts |
| `soda_mmqc/data/checklist/fig-checklist/identify-panels/schema.json` | **new** | Runtime contract for the `panels` artifact. No eval assets |
| `soda_mmqc/data/checklist/fig-checklist/micrograph-scale-bar/v1/SKILL.md` | **new** | The pilot leaf, converted from `prompt.2.txt` |
| `soda_mmqc/cli.py` | modified | Skill loading, graph building, cycle detection, prose/frontmatter consistency |
| `tests/test_agentic_cli.py` | modified | Skill-loading, graph, consistency and contract-placement tests |

No prompt file was deleted. No evaluation contract was moved, copied, or edited.

---

## Human gate 2A — the shared skill's wording

**Decision:** does the merged `identify-panels` prose preserve everything the
three source sections said, and is its `description` specific enough to win the
intended hop and narrow enough not to attract unrelated ones?

**Status: PASSED — 2026-09-11, Çağatay Gürsoy.**

> **Verdict: pass.** The spelling fork was decided in favour of **`Ai`/`Aii`** —
> *"makes more sense. Force everything into this."* The shared skill needed no
> change; the gold did, and was corrected. See
> [the gold correction](#the-gold-correction-executed-at-this-gate).
>
> Getting here took two passes. The first produced the artifact below. The
> second checked all four of the merge's additions against the dataset's 5,767
> gold panel rows and **found one of them wrong** — see
> [the finding](#finding-found-while-preparing-this-gate-the-composite-panel-rule-contradicted-the-pilots-gold)
> — which was corrected before the decision was taken.

### The proposed `description`, on its own line

> Identify every labeled panel of a scientific figure and map each panel to the caption text that describes it. Use this first, whenever a task needs the list of panels, their labels, where each panel sits in the figure image, what each panel shows, or which caption sentence applies to which panel. Produces the shared panels artifact. Makes no quality-control judgement about what a panel contains.

Three deliberate properties, each aimed at one half of the gate's question:

1. **It claims the hop.** The verbs and nouns a caller's prose will use — "panels",
   "panel labels", "which caption text describes which panel" — are all present,
   so a leaf asking for the panel inventory matches on wording it actually used.
2. **It disclaims the neighbours.** The last sentence exists to *lose*
   competitions. Every other skill in `fig-checklist` is a quality-control check
   ("are error bars defined", "is there a scale bar"). An agent looking for a
   verdict must not land here, and the explicit refusal to judge is the cheapest
   way to say so.
3. **"Use this first"** encodes its position in the DAG without naming a caller,
   so the string stays correct when the other ten leaves point at it.

**Open risk for the reviewer:** `panel-image-matches-caption` also concerns
panels *and* the caption. Its future `description` must claim *comparison* and
*consistency*, not *identification*, or the two will compete. That is a
Milestone 5 authoring constraint created by this wording, and it is recorded
here so it is not discovered by a mis-fired hop.

### The three source sections, quoted

**Source A — `micrograph-scale-bar/prompts/prompt.2.txt`, §1** (the pilot's own
source; conversion map pins `prompt.2.txt`):

> ## 1. Identify all figure panels
> The first task is to understand the figure image and see where there are labeled figure sub-panels. Each labeled panel depicts an experiment either with a plot, a micrograph, some other kinds of images, a scheme. Sometimes a panel can include several images. For example, a panel can include both an microscopy image and a plot that tyipcally displays a quantification of some features shown on the image.

**Source B — `error-bars-defined/prompts/prompt.3.txt`, §1** (the fullest of the
three; the conversion map's designated source for that leaf is `prompt.4.txt`,
which folds the same material into a "Helpful tips" paragraph — quoted after):

> ## 1. Identify all figure panels
> Understand the figure image and see where there are figure sub-part or "panels". Each panel depicts an experiment either with a plot, a micrograph, some other kinds of images, a scheme. Panels are typically labeled with consecutive letters (for example: A, B, C, ... or (a), (b), (c)). The first panel is usually on the top left. The last panel tends to be on the bottom right. Sometimes the layout is however a bit messy. Sometimes a panel can include several images. For example, a panel can include both an microscopy image and a plot. For each panel, locate the corresponding description in the figure caption. Please note that sometimes the same caption text is valid for several panels. This is usually indicated with the respective panel labels in brakest before or after the caption text. For example: "(D and F) Reporter accumulation shown by FLAG immunoblot in RKO iCas9 KO cell lysates upon 48h dox treatment to induce AAVS1 (non-targeting control), ANKZF1, ASCC3, UFM1, NEMF or LTN1 knockout."

`error-bars-defined/prompts/prompt.4.txt`, the newest revision, says the same
thing in one paragraph and adds nothing beyond it:

> Work through the figure systematically, panel by panel. Panels are typically labeled with consecutive letters (A, B, C... or (a), (b), (c)...), and a single caption sentence sometimes covers multiple panels — watch for label brackets like "(D and F) ...".

**Source C — `image-annotation-defined/prompts/prompt.1.txt`, §1** (its newest
revision, `prompt.2.txt`, has no standalone §1; the equivalent line survives in
its "A few things to keep in mind" — quoted after):

> ## 1. Identify all figure panels
> Understand the figure image and see where there are figure sub-part or "panels". Each panel depicts an experiment either with a plot, a micrograph, some other kinds of images, a scheme. Panels are typically labeled with consecutive letters (for example: A, B, C, ... or (a), (b), (c)). The first panel is usually on the top left. The last panel tends to be on the bottom right. Sometimes the layout is however a bit messy. Sometimes a panel can include several images. For example, a panel can include both a microscopy image and a plot. For each panel, locate the corresponding description in the figure caption.

> - If the same caption sentence covers multiple panels, apply it to each relevant panel

Source C is Source B minus the shared-caption sentence — which `prompt.2.txt`
then restores in the bullet above. So the union of the three is Source B plus
Source A's "labeled" emphasis and its composite-panel example.

### Line-level account: every source instruction, and where it went

| # | Instruction | From | Where it is now |
|---|---|---|---|
| 1 | Understand the figure image; find labeled figure sub-parts / "panels" | A, B, C | §1 ¶1 |
| 2 | Each panel depicts an experiment: a plot, a micrograph, another kind of image, or a scheme | A, B, C | §1 ¶1, verbatim in substance |
| 3 | Labels are typically consecutive letters `A, B, C` or `(a), (b), (c)` | B, C | §1 bullet 1 |
| 4 | First panel usually top left, last usually bottom right | B, C | §1 bullet 2 |
| 5 | The layout is sometimes messy | B, C | §1 bullet 2, with the tie-break made explicit: follow the labels, not the reading order |
| 6 | A panel can include several images, e.g. a microscopy image plus a plot | A, B, C | §2 ¶1 |
| 7 | …a plot that typically quantifies features shown in the image | A only | §2 ¶1, kept |
| 8 | For each panel, locate the corresponding description in the caption | B, C | §3 ¶1 |
| 9 | The same caption text is sometimes valid for several panels, indicated by labels in brackets before or after the text | B, C (`prompt.2`) | §3 ¶1 |
| 10 | The "(D and F) Reporter accumulation…" example | B | §3, quoted verbatim as a blockquote |
| 11 | "Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes" | A, B, C (Summary) | Preamble, ¶2 |
| 12 | "You are a scientific technical editor specialized in the quality control of scientific figures and data presentation" | A, B, C (Summary) | Preamble, ¶1 |

**Nothing from the three sections was dropped.** Two source sentences are
*generalized* rather than copied, and a reviewer should confirm both:

- #2 keeps the enumeration ("plot, micrograph, other image, scheme") as a
  description of what panels are. It is not a classification instruction — none
  of the three sources used it as one, and turning it into one here would put a
  content judgement in a skill whose `description` promises not to make any.
- #11/#12 are shared preamble text, present in all three sources, so merging
  them loses nothing.

### Additions beyond the three sources — flagged, not smuggled

The merge is not purely subtractive. Four things are new, each because the
prompt could rely on a surrounding context that a standalone skill has not got:

| Addition | Where | Why it exists |
|---|---|---|
| Report the bare label — `(a)` → `a`; do not invent, reorder, or renumber | §1 bullets 3 | The sources let each leaf normalize labels in its own output. A *shared* artifact consumed by eleven leaves must normalize once, or the leaves disagree about what "panel A" is. **Checked against gold:** safe for `fig-checklist` — the only bracketed gold labels in the whole dataset (`(A)`…`(F)`, 6 rows) are in `Retired-checklist/panel-label-detection`. Lowercase labels (`a`–`g`, 13 files) are preserved correctly by "report the labels the figure actually carries" |
| Unlabeled figure → one panel with an empty label | §1 bullet 4 | The schema requires a `panel_label` string. Without this rule the agent must improvise on a figure with no labels. **Checked against gold:** the dataset contains exactly one such row (`replicates-defined`, `10.1038_emboj.2009.312/content/1`), and it uses `""` — so the fallback matches the only real precedent. Not a `fig-checklist` check, so nothing in the pilot depends on it |
| **Labelled sub-parts get one entry each; unlabelled composites stay one entry** | §2 | **This addition was wrong in its first draft and has been corrected — see the finding below.** It originally said a composite panel is one panel and must never be split |
| Report every panel, including irrelevant-looking ones | "Report every panel" | Lifted in spirit from the pilot's closing line, *"Include all panels visible in the figure, even if they don't contain micrographs or microscopy images"* — which is check-specific in the prompt and had to be restated check-neutrally here. The leaf keeps its own version for its own output rows |

### Finding, found while preparing this gate: the composite-panel rule contradicted the pilot's gold

The four additions above are the substance of gate 2A — they are the merge's
judgement calls rather than the prompts'. Three of them were checkable against
the 5,767 gold panel rows in the dataset, and are annotated above. The fourth
was checkable too, and it failed.

The first draft said:

> A composite panel like that is still one panel with one label — do not split
> it into several — but name each of its distinct elements separately in
> `panel_content`.

`micrograph-scale-bar`'s **own benchmark** contains
`10.1038_s44321-025-00219-1/content/1`, whose caption opens:

> **(Ai–ii)** Phase contrast images of a time lapse of E. coli MG1655 cells
> mock-treated **(i)** and treated with 1.4% saccharin **(ii)**.

and whose gold has four rows, not three:

```
A i, A ii, B, C
```

Under the original rule the agent emits `A`, `B`, `C`. Because `panel_label` is
the `list_alignment` key at `exact` / threshold 1.0, that is one unmatched gold
row plus one label mismatch — roughly half the figure — on 1 of the pilot's 38
examples.

**Corrected**: §2 now distinguishes the two cases. Sub-parts that the figure or
caption labels get one entry each, written the way the figure writes them;
an unlabelled composition — the image-plus-plot case all three source prompts
describe — stays one entry with its elements named in `panel_content`. The
correction also explicitly forbids inventing a separator, which keeps the skill
from generating the `C top` / `C bottom` style that appears once in
`plot-axis-units` gold and nowhere else.

**Covered** by `TestSharedSkillAgainstRealGold`, including a mutation that
restores the original wording and is caught.

### The unresolved half of that finding — a curation decision, not a skill decision

Correcting the rule does not settle what the label should *say*, and this is
the part that needs a person.

The same figure is benchmarked by **eleven** `fig-checklist` leaves. Nine have
gold for it. They do not agree on how to spell the sub-panels:

| Gold spelling | Leaves |
|---|---|
| `A i`, `A ii` (spaced) | **`micrograph-scale-bar`** — the pilot, and the only one |
| `Ai`, `Aii` (unspaced) | `error-bars-defined`, `individual-data-points`, `panel-image-matches-caption`, `plot-axis-units`, `plot-gap-labeling`, `single-channel-for-overlay`, `stat-significance-level`, `stat-test` |

One shared `identify-panels` artifact feeds all of them, so **whichever spelling
it emits, one side mis-aligns.** No wording of the skill can satisfy both.

This cuts two ways, and both are worth stating:

- It is the **strongest evidence so far that the shared skill is the right
  design.** Eleven leaves each re-derived the panel list from a duplicated
  prompt section, and the gold drifted apart on the very first figure with a
  non-trivial label. That drift is what `identify-panels` exists to end.
- It is also a problem `identify-panels` **cannot fix**, because the
  disagreement is in the gold, not in the skill. Fixing it means editing
  curated expected outputs — changing the measuring stick — which is a human
  decision and was not taken here.

The skill currently follows its own stated principle, "report the labels the
figure actually carries". The caption writes `(Ai–ii)`, so that principle
yields `Ai`/`Aii` — matching the caption **and** eight of the nine leaves, and
leaving the pilot's own gold as the outlier.

**Open question for the reviewer, and the one with real consequences:** accept
that the pilot mis-scores on this single example and correct
`micrograph-scale-bar`'s gold by curation; or force the shared skill to emit
`A i` and accept that eight Group A/B leaves mis-score in Milestone 5. Deciding
it the second way for the pilot's convenience would be optimizing the shared
asset for one consumer against eight, which is the opposite of the point.

### The gold correction executed at this gate

**Decided 2026-09-11: `Ai`/`Aii`** — *"makes more sense. Force everything into
this."* The rationale is the one the artifact pointed at: it is what the caption
writes, what the shared skill already emitted under "report the labels the
figure actually carries", and what twelve of the sixteen gold files already had.
**The shared skill was not changed.** The gold was.

Four gold files for `10.1038_s44321-025-00219-1/content/1` were corrected:

| Check | Was | Now | Why |
|---|---|---|---|
| `micrograph-scale-bar` | `A i`, `A ii` | `Ai`, `Aii` | spaced form |
| `panel-label-detection` | `A i`, `A ii` | `Ai`, `Aii` | spaced form |
| `panelisation-and-classification` | `A i`, `A ii` | `Ai`, `Aii` | spaced form |
| `replicates-defined` | `Aii`, **`Aii`** | `Ai`, `Aii` | **a separate bug** — the label appeared twice with byte-identical row content and no `Ai` at all, so the first row was the missing first sub-panel |

All sixteen gold files for the figure now read `['Ai', 'Aii', 'B', 'C']`, and
dataset-wide no spaced sub-panel label remains.

Edits were targeted text replacements on the `"panel_label"` lines rather than a
JSON round-trip, so indentation, key order, unicode escaping (`\u03bc`) and the
`updated_at` timestamps are untouched. The timestamps were left alone
deliberately: they record *curation* events, and this was a mechanical
normalization.

> ⚠️ **`soda_mmqc/data/examples/` is gitignored**, so this change has no diff
> and cannot be undone with git. The exact inverse is: in the three spaced files
> replace `"panel_label": "Ai"` → `"panel_label": "A i"` and
> `"panel_label": "Aii"` → `"panel_label": "A ii"`; in `replicates-defined`
> replace the *first* `"panel_label": "Ai"` with `"panel_label": "Aii"`.
>
> That the gold — the measuring stick for every score this project produces —
> is untracked is itself worth fixing, and is logged as debt.

`test_every_check_spells_this_figures_sub_panels_the_same_way` replaces the
tripwire that flagged the conflict: it now asserts every gold file for the
figure agrees, and fails if any consumer drifts again.

### Two instances of the same class, deliberately left alone

The decision was about `Ai`/`Aii`. Two other gold entries sub-divide a panel the
figure does **not** sub-label — the curator invented the distinction rather than
transcribing one — which is a different judgement, so they were not touched:

| Gold | Check | In scope later? |
|---|---|---|
| `C top`, `C bottom` | `plot-axis-units` | **Yes — a Group B leaf, so it lands in Milestone 5** |
| `B (H1.1)`, `B (RCC1)`, `B (H1t)` | `n_larger-two` | No — not a `fig-checklist` check |

The shared skill is explicitly forbidden from inventing a separator, so it will
emit `C` and `B` here and both will mis-align until decided. `plot-axis-units`
is the one to settle before Group B conversion.

### The draft `panels` schema

`identify-panels/schema.json` — a **runtime contract only**. No
`eval-manifest.json`, no `benchmark.json`, so the directory does not own the
evaluation contracts and therefore is not a check. That is the whole of the
Milestone 1 enumeration fix working as intended.

It reuses the envelope the check schemas use (`format.type = json_schema`,
`format.strict = true`), so Milestone 4's intermediate-artifact validation can
read leaf and intermediate schemas through one code path.

| Field | Type | Carries |
|---|---|---|
| `panel_label` | string | The label, bare. Empty only for an unlabeled figure |
| `location_in_figure` | string | The plan's "region notes" — where to find the panel |
| `panel_content` | string | What the panel shows, composite elements named separately |
| `caption_excerpt` | string | The plan's "caption excerpt" — verbatim, empty if the caption is silent |
| `caption_covers_panels` | array of string | Which labels that excerpt covers. This is what makes the `(D and F)` case machine-readable rather than a note in prose |

`additionalProperties: false` and all five required, matching the house style of
every check schema in the checklist.

**Open question for the reviewer:** the plan says "caption excerpt/**span**".
This schema carries the excerpt text and the covered labels, but no character
offsets into the caption. Offsets would let a consumer highlight the caption in
a UI; they are also a thing an agent gets wrong silently. Text-only is the
proposal.

---

## Human gate 2B — the leaf conversion

**Decision:** did the conversion lose anything check-specific, leave anything
shared duplicated, or turn the sub-skill call into a template?

**Status: PASSED — 2026-09-11, Çağatay Gürsoy. No changes required.**

> **Verdict: pass, unchanged.** All three parts of the gate's question are
> answered *no defect*, and none rests on a reading alone — see
> [the answers](#what-gate-2b-actually-asks-and-the-answers). The `from_the_image`
> "number and unit" rule was **accepted as-is**: two gold rows exceed it by
> carrying several bars per panel, but writing a rule the prompt never made is
> the drift this gate exists to catch. It is a one-line addition whenever it is
> wanted.
>
> Preparation went well past reading: the hand-built account below is backed by
> a vocabulary sweep of all 115 content words of the prompt, and the leaf's
> three additions were checked against the 298 gold panel rows of its own 38
> benchmark examples. Nothing was lost, all three additions are supported, and
> the dropped JSON example turned out to be **misleading** on a point the added
> prose corrects.

### `prompt.2.txt` line by line, and where every rule went

Source: `micrograph-scale-bar/prompts/prompt.2.txt`, 71 lines. Target:
`micrograph-scale-bar/v1/SKILL.md`.

| Prompt lines | Rule | Disposition |
|---|---|---|
| 3–4 | Role: technical editor specialized in QC of figures; task is to check micrographs for a scale bar, defined either in the image or in the caption | **Kept in the leaf** — preamble ¶1 |
| 6 | "Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes" | **Kept in the leaf** — preamble ¶2. Also present in the shared skill, because both are read independently; this is shared *preamble*, not a shared *rule* |
| 8–9 | §1 "Identify all figure panels" in full | **Moved to `identify-panels`** — see the gate 2A table, rows 1, 2, 6, 7. The leaf now has §1 "Get the panels", which asks for them instead of restating how to find them |
| 11–13 | Micrograph applicability: micrograph, picture of a microscopic sample, microscopy image or kymograph counts; schematics, crystal structures, cryo-EM maps and 3D molecular renderings do not | **Kept in the leaf**, verbatim in substance — §2. This is the leaf's own gate and is deliberately *not* shared: the conversion map notes each Group A leaf's visual type gate differs (`image-annotation-defined` excludes kymographs, this leaf includes them) |
| 14 | Only if it is a micrograph, check for a scale bar; definition of a scale bar as a line or bar of defined length | **Kept in the leaf** — §3 |
| 16–19 | §3: the length may be written on the image (e.g. "10 μm", "500 nm") or only in the caption; check both, independently | **Kept in the leaf** — §4, with the independence made explicit (both can be yes, both can be no) |
| 21–22 | §4: extract the number and unit from the image, e.g. "500 nm" | **Kept in the leaf** — §5 |
| 23 | Extract the exact caption text defining the scale bar | **Kept in the leaf** — §5 |
| 24 | *IMPORTANT:* extract only the text describing the scale bar; not general descriptions of the figure or panel | **Kept in the leaf** — §5, still marked as the strict rule it is |
| 26 | "Provide your analysis in the following JSON format for EACH and EVERY panel" | **Kept as a requirement, rewritten as a pointer.** The leaf now points at the check's existing `schema.json` — plan Step 3 requires exactly this |
| 28–69 | The four-panel JSON example | **Deliberately dropped**, per plan Step 3. Its *semantics* were not dropped: the example's only non-obvious content is panel C, which shows that a non-micrograph panel keeps its `panel_label` and empties only the five scale-bar answer fields. That is now stated in prose in "Output", where the schema's `""` enum members cannot state it on their own. See the review finding below — the first draft of that sentence got it wrong |
| 71 | "Be thorough and precise… Include all panels visible in the figure, even if they don't contain micrographs" | **Kept in the leaf** — "Output", as a rule about the leaf's own rows. Its check-neutral half also appears in the shared skill's "Report every panel". Not duplication: one governs the inventory, the other governs the output rows, and the leaf's is the one the evaluator sees |

**Nothing was dropped except the JSON example, and that was required.** No rule
was moved to the shared skill except §1, which is the rule the milestone exists
to share.

### Additions in the leaf — flagged, not smuggled

Three sentences in the leaf are not in `prompt.2.txt`. Each resolves something
the prompt left implicit and that the split makes explicit; a reviewer should
accept or reject them individually. **All three were checked against the 298
gold panel rows of the pilot's own 38 benchmark examples**, and the evidence is
in the last column.

| Addition | Where | Why — and what the gold says |
|---|---|---|
| "A panel that holds several images counts as a micrograph panel if any of its images is one" | §2 | The prompt says composite panels exist (§1) and asks whether "the panel image" is a micrograph, but never says what a composite panel is. The output has one row per panel, so the question has to be answered somewhere. **Gold is consistent with it**: 0 of 217 non-micrograph rows claim a scale bar, so nothing in gold treats a composite as partially-micrograph |
| "Use the caption text the panel inventory already mapped to this panel, remembering that one caption sentence can cover several panels" | §4 | The prompt could assume the agent had just read the caption in its own §1. Now that the mapping is produced by another skill, the leaf has to say to use it, or the shared artifact is computed and ignored. **Gold is consistent**: 0 flag/text mismatches on the caption fields across all 298 rows |
| "The two are independent: a scale bar can be defined in both places, or in neither" | §4 | The prompt's JSON example shows each panel defined in exactly one place, which reads as mutually exclusive. **This addition is not merely defensible — the gold proves the example was misleading** (see below) |

**The independence rule, in gold.** All four combinations occur among the 81
micrograph rows:

| `defined_in_image` | `defined_in_caption` | rows |
|---|---|---|
| no | yes | 26 |
| yes | no | 24 |
| **no** | **no** | **16** |
| **yes** | **yes** | **15** |

The dropped JSON example showed only the two off-diagonal cases. **31 of 81
micrograph rows — 38% — are shapes the example never demonstrated**, and 15 of
them are the both-`yes` case it implicitly denied. So on this point the prose
replacement is not a lossy substitute for the example; it is strictly better
than what it replaced.

### Nothing lost: a mechanical check, not just the table

The table above is hand-built, so it was verified mechanically. Every content
word of `prompt.2.txt` (excluding the deliberately dropped JSON block and a
stopword list) was checked for presence in the leaf plus the shared skill: 115
distinct words, **13 absent**, and every one of the 13 is an artifact rather
than a lost instruction:

| Absent word | Why it is not a loss |
|---|---|
| `three`, `dimensional` | The leaf writes `three-dimensional` as one hyphenated token |
| `itsself`, `tyipcally`, `systematical` | Typos in the prompt; the skills use `itself`, `typically`, `systematic` |
| `bars`, `kinds`, `rendering` | Morphological variants of words that are present |
| `sub-panels` | The shared skill says `sub-parts`, four times |
| `contain`, `don't`, `visible` | Rephrased: "holds", "are not micrographs", "each and every panel" |
| `summary` | The `## Summary` heading, not content |

### A pre-existing gap the conversion faithfully preserved

Gate 2B asks whether the conversion lost anything, and it did not. But checking
§5 against gold surfaced a limitation **in the prompt itself**, which the
conversion inherited verbatim.

The prompt (line 22) and therefore the leaf say `from_the_image` "encompasses
the number and the unit, for example '500 nm'". 12 of 298 gold rows (4.0%) do
not have that shape — and they are **two unrelated things**, which matters,
because only one of them is a prompt problem:

**(a) Genuine multi-bar panels — 2 rows.** One panel carrying several scale
bars of different lengths:

```
5 µm; 2 µm                        10.1038_s44318-026-00715-1, panel B
2 μm; 0.5 μm; 0.5 μm; 0.1 μm      10.15252_emmm.201404392,    panel B
```

This is real, and the prompt genuinely never covers it. It is the composite-panel
question from gate 2A arriving from the other direction.

**(b) One document curated to a different convention — 9 rows, all from
`10.1038_s44319-025-00631-1`.** Every anomalous row in that document describes
where the bar *is* instead of extracting what it *says*:

```
Scale bar (black bar visible lower right)
scale bar visible on H&E panel (black line)
50 μm (scale bar visible in image)
```

plus three rows with `scale_bar_defined_in_image: yes` and an empty
`from_the_image`, which the field's own semantics say cannot happen. That is a
**gold-quality outlier from a single curation session**, not a pattern the skill
should be taught to reproduce.

`from_the_image` is scored `graded_string` / `semantic` / 0.8, so an agent
answering `5 µm` for a two-bar panel loses partial credit rather than failing
structurally.

**Nothing was changed here.** For (a), inventing a rule the prompt never made is
exactly the drift gate 2B exists to catch, and it is two rows; it is a one-line
addition if wanted. For (b), the fix is curation, not prose.

### Is the sub-skill call prose, or a template?

The call is one sentence in the leaf's own §1:

> Before you check anything, get the panel inventory for this figure by calling the `identify-panels` skill with the `Skill` tool. Work from the panels it returns rather than deriving your own list, so that this check and every other check of this figure agree on what the panels are.

It names the skill, names the tool, and gives a reason. There is no placeholder,
no schema fragment, no argument list, and nothing that a code generator filled
in. `requires: [identify-panels]` in the frontmatter says the same thing for the
runner's benefit; the frontmatter is never executed.

### Is the dependency legible from the text alone?

The gate asks that a reader see the edge without looking at the filesystem.
They can: the leaf names `identify-panels` in prose, in `requires`, and in the
sentence quoted above. Nothing in either file refers to a path, a parent
directory, or a location. The two directories are flat siblings, and a test
(`TestGraphIsPathIndependent`) proves the resolved graph is unchanged when the
shared skill's directory is renamed *and* moved under the leaf.

### What gate 2B actually asks, and the answers

The gate's own question has three parts. All three are answered, and none is a
judgement call:

| Question | Answer | Basis |
|---|---|---|
| Did the conversion lose anything check-specific? | **No** | The 71-line account above, corroborated mechanically by a 115-word vocabulary sweep whose 13 gaps are all typos, morphology or synonyms |
| Did it leave anything shared duplicated? | **No** | The leaf's §1 asks for the panel inventory and does not restate how to find panels. Pinned by `TestNoLeafRestatesTheSharedSkill`, which fails if any leaf echoes the shared skill's distinctive wording — the guard that matters once ten more leaves land |
| Did it turn the sub-skill call into a template? | **No** | One sentence naming the skill, the tool and a reason; no placeholder, no schema fragment, no argument list |

**So there was no blocking issue at 2B, and it passed unchanged.** Three notes
remain, none a defect the conversion introduced, all accepted at the gate and
carried forward:

1. **Multi-bar panels in §5 — 2 gold rows.** The prompt's `from_the_image` rule
   says "the number and the unit"; two panels carry several bars
   (`5 µm; 2 µm`). A genuine gap in the *prompt*, preserved faithfully.
   **Accepted as-is at the gate** — inventing rules the prompt never made is the
   drift this gate guards against. A one-line addition whenever it is wanted.
2. **One document's gold uses a different convention — 9 rows, all
   `10.1038_s44319-025-00631-1`.** Descriptions of where the bar sits rather
   than what it reads, plus three rows flagged `yes` with an empty value. A
   curation matter, not a prose matter; **carried into Milestone 5**.
3. **Preamble repetition.** The "step-by-step, systematic" line is in both
   skills. Intentional — each file is read on its own — but it becomes noise
   across eleven leaves. **Carried into Milestone 5.**

### Two questions this gate raised and then closed

**Kymographs — resolved, no action.** The leaf counts a kymograph as a
micrograph, following prompt line 13, while `image-annotation-defined` excludes
kymographs from imaging panels. That looked like a contradiction worth a
decision. It is not one for this gate: the pilot benchmark contains exactly one
figure whose caption mentions a kymograph
(`10.1038_s44318-026-00715-1/content/3`, panel H), and its
`micrograph-scale-bar` gold marks that panel `micrograph: yes`. **The leaf's
rule is what its own gold does.** `image-annotation-defined` has no gold for
that figure, so the two leaves cannot be shown to disagree on any real example
— the disagreement exists only between two prompt texts, and belongs to
whichever gate converts that leaf in Milestone 5.

**The gate 2A gold correction — verified end to end, not just by label
inspection.** Scoring the corrected figure through the real `score_check` path
with gold as its own prediction:

| Labels scored | instances | mean score | layer1 |
|---|---|---|---|
| corrected `Ai`/`Aii` | 28 | **1.000** | 24 `correct_applicable`, 4 `correct_NA` |
| pre-fix `A i`/`A ii` | 28 | **0.500** | **12 `withheld_applicable`**, 12 `correct_applicable`, 4 `correct_NA` |

The two sub-panel rows are six fields each, so the mismatch withheld exactly 12
of 28 instances — the rows did not align at all, scoring `0.0` with a `null`
prediction rather than degrading gracefully. **The fix is worth +0.500 mean
score on that example**, roughly +1.3% on the pilot's 38-example mean, and it
confirms the alignment-key failure mode predicted at gate 2A rather than merely
asserting it.

---

## Independent code review, and what it found

The change set was reviewed by a separate read-only reviewer against the plan's
five invariants. It cleared `_FRONTMATTER` (CRLF, `---` inside the body,
frontmatter-only documents, YAML document separators), `find_cycle` (termination
and genuine cycle paths on self-loops, 2-cycles, tails-into-cycles and diamonds),
and `_name_list`'s duplicate detection. It raised two findings, both real, both
fixed, both now covered by a test that was verified failing-first.

### Finding 1 (high) — the prose told the agent to blank the alignment key

The first draft of the leaf's "Output" section said a non-micrograph panel is
reported "with `micrograph` set to `no` and **every remaining field** left as an
empty string". `panel_label` is a remaining field under that reading, and it was
the one schema field the prose never named anywhere else.

That is not a cosmetic slip. `eval-manifest.json` uses `panel_label` as the
list-alignment key:

```json
"list_alignment": { "outputs": ["panel_label"] }
```

Blanking it collapses every non-micrograph panel onto the same empty key, so
pairing against gold fails — and it fails **silently**, because `panel_label` is
an unconstrained `string` in `schema.json`, so the output validates perfectly
while the figure's panel-level scores collapse. Had this reached Milestone 4,
the symptom would have been a bad agentic score at gate 5A, read as evidence
that delegation does not work.

It was introduced precisely by the edit the plan asks for — dropping the JSON
example. In `prompt.2.txt` the example carries the rule implicitly: panel C, the
non-micrograph case, keeps `"panel_label": "C"` and empties only the five answer
fields. Generalizing that into prose is where the label got swept in.

**Fixed**: the sentence now names `panel_label` and scopes the blanking to "the
remaining scale-bar fields". **Covered** by `TestTheLeafProseMatchesItsContracts`
— the prose must name every field of the check's `schema.json`, must name every
`list_alignment` key of its `eval-manifest.json`, and the block that empties
fields may not use a universal quantifier and must say the label is kept. All
three fail on the original wording.

**This is the general risk the "point at `schema.json`" instruction creates**,
and it will recur in all ten remaining leaves: the schema can no longer catch a
prose rule that contradicts it, because a wrong value is still a valid value.
The new test class is check-agnostic and should be pointed at each leaf as it
lands in Milestone 5.

### Finding 2 (medium) — one `Skill`-tool mention vouched for every requirement

`validate_skills` checked prose-vs-`requires` per requirement, but asked "is this
an actual instruction to the agent?" once per file: `if declared and not
_mentions(skill.body, SKILL_TOOL)`. With the pilot's single requirement the two
are equivalent, which is why it passed.

With two, they are not. Every Group B leaf declares `identify-panels` **and**
`classify-quantitative-plot`. A leaf that properly calls the first and merely
*mentions* the second would validate clean, and the missing hop would only
appear at runtime as an absent `Skill` invocation — the exact failure mode the
plan says to catch in the prose, not in the trace.

**Fixed**: the check is now per requirement and asks for co-occurrence within a
*prose block* — a paragraph, with each markdown list item its own block, and
line wrapping ignored. So a leaf with two requirements has to instruct the agent
twice, in a bullet each or a paragraph each, while a call that wraps across two
source lines still counts. **Covered** by three tests: the two-requirement
free-ride case fails; a bullet per hop passes; a wrapped call passes.

---

## Automatic gate

**Command:** `pytest tests/test_agentic_cli.py tests/test_micrograph_scale_bar_manifest.py -v`

```
121 passed in 3.83s
```

58 before this milestone (55 in `test_agentic_cli.py` after parametrization,
plus 3 manifest tests), **121 after** — 63 new tests. Two existing tests were
updated when gate 2A's decision changed the gold they pinned; nothing else was
changed or removed.

### The whole suite is unaffected

The milestone constraint is that *every* milestone runs the existing suite. Run
with the five stale pre-existing collection failures excluded (`test_evaluate`,
`test_compare_lists`, `test_compare_objects`, `test_compare_strings`,
`test_fuzzy_matching` — they import a `JSONEvaluator` that no longer exists, and
their collection error aborts a plain `pytest tests/` run; documented in the
Milestone 1 handoff and untouched here):

| | before | after |
|---|---|---|
| `FAILED`/`ERROR` lines | 62 | **62** |
| diff of the sorted line sets | — | **empty** |

"Before" is the same working tree with `identify-panels/` and
`micrograph-scale-bar/v1/` moved aside, `tests/test_agentic_cli.py` excluded on
both sides. The 62 pre-existing failures are the same set Milestone 1 recorded
against `60f73b22`; **not one of them moved.** Full run including the new tests:
`38 failed, 414 passed, 12 skipped, 23 errors`.

### Mutation testing — the new tests were verified failing-first

Each mutation was applied to the working tree, the gate re-run, and the tree
restored.

| Mutation | Tests that caught it |
|---|---|
| `load_skill` takes the name from the directory instead of the frontmatter | 5, incl. `test_renaming_a_skill_directory_leaves_the_graph_unchanged` |
| The leaf's prose stops naming `identify-panels` and the `Skill` tool | 5, incl. `test_the_real_checklist_validates` and both path-independence tests |
| `identify-panels/schema.json` deleted | 2 |
| `benchmark.json` copied into `micrograph-scale-bar/v1/` | `test_no_version_directory_holds_a_copy_of_a_contract` |
| The leaf's "Output" reverted to "every remaining field left as an empty string" (review finding 1) | 3, all of `TestTheLeafProseMatchesItsContracts` |
| The `Skill`-tool check reverted to whole-file (review finding 2) | `test_a_second_requirement_cannot_ride_on_the_first_ones_call` |
| The shared skill's absolute "do not split composite panels" restored (gate 2A finding) | `test_the_shared_skill_tells_the_agent_to_split_labelled_sub_panels` |
| The leaf's independence sentence deleted (gate 2B evidence) | `test_the_leaf_says_the_two_definition_sites_are_independent` |
| The leaf re-absorbs the shared skill's panel-finding rules (gate 2B, "nothing duplicated") | `test_no_leaf_restates_how_to_find_panels` |

The first is the load-bearing one: it is the only mutation that makes the
resolved graph depend on the filesystem, and the rename test is what notices.
Note that *moving* the skill (rather than renaming it) does **not** catch that
mutation — `path.parent.parent.name` is unchanged by a move — which is why the
plan asks for both.

The last four are the review and gate findings replayed as mutations, so the
fixes are pinned rather than merely applied. The independence mutation
initially **survived**, because the first version of its test matched the
substring `independent` — which the unrelated phrase "check both,
independently" already satisfied. The test now requires a prose block asserting
the both/neither outcome, and the mutation is caught.

### Test coverage added (63)

| Class | n | Covers |
|---|---|---|
| `TestLoadSkill` | 13 | Frontmatter parses; name comes from frontmatter, not the directory; folded (`>-`) descriptions; missing/invalid frontmatter, missing `name`/`description`, non-list `requires`, repeated requirement, empty body, non-`vN` version directory, missing file. Every message names the file |
| `TestLoadSkillsOnTheRealChecklist` | 7 | Both pilot skills load; the leaf declares *and* invokes the shared skill; the shared skill requires nothing and produces `panels`; the two `description`s claim disjoint jobs; duplicate name+version rejected; two versions of one skill coexist |
| `TestSkillGraph` | 6 | The real graph is exactly one edge; acyclic; 2-cycle and 3-cycle detected and reported as a loop; a diamond is not a cycle; edges union across versions |
| `TestProseAndFrontmatterAgree` | 14 | The real checklist validates; declared-but-not-in-prose fails; invoked-in-prose-but-undeclared fails; a requirement with no `Skill`-tool instruction fails; **a second requirement cannot ride on the first one's call**; a bullet per hop passes; a call wrapped across two lines passes; unknown requirement; self-requirement; cycle; all problems reported at once; a skill naming *itself* is not an invocation; a name inside a longer word (`root-cause`) is not an invocation |
| `TestGraphIsPathIndependent` | 3 | Rename the shared skill's directory; move it *under* its caller; bury it three levels deep — the resolved graph is identical each time |
| `TestEvaluationContractsStayAtSkillLevel` | 6 | No version directory anywhere under `CHECKLIST_DIR` holds a contract copy; the leaf still owns its three; the shared skill owns a runtime `schema.json` and neither eval asset; it is not enumerated as a check; it cannot be scored; the `panels` schema has the five expected fields, all required, closed |
| `TestTheLeafProseMatchesItsContracts` | 3 | The leaf's prose names every field of its `schema.json` and every `list_alignment` key of its `eval-manifest.json`; the rule that empties fields does not sweep up the label. Check-agnostic — point it at each leaf as Milestone 5 converts it |
| `TestSharedSkillAgainstRealGold` | 4 | The pilot benchmark really does contain a split composite panel; the shared skill no longer forbids splitting outright and does tell the agent to split labelled sub-parts; **a tripwire on the nine-leaf gold spelling conflict** that fails if the state changes at all, including if curation fixes it |
| `TestLeafProseAgainstPilotGold` | 5 | Gold really does define scale bars in both places at once and in neither; the leaf states the both/neither claim; no non-micrograph gold row claims a scale bar; non-micrograph rows empty the answer fields (bounding the one known outlier); every non-micrograph gold row keeps its `panel_label` |
| `TestNoLeafRestatesTheSharedSkill` | 3 | The guarded phrases really are the shared skill's own (no vacuous pass); no leaf restates how to find panels; every leaf that needs panels both declares and calls `identify-panels`. **The guard that matters in Milestone 5**, when ten more leaves could each quietly keep their own copy |

### What `cli.py` gained

Public: `Skill`, `load_skill`, `load_skills`, `build_graph`, `find_cycle`,
`invoked_skills`, `validate_skills`, plus `SKILL_FILENAME` and `SKILL_TOOL`.
`score` and everything it uses is untouched.

Four decisions worth knowing about:

- **Prose invocation is detected by name match**, with hyphen-aware boundaries
  (`(?<![\w-])name(?![\w-])`), so `root` does not match inside `root-cause` and
  `identify-panels` does not match inside `identify-panels-v2`. A skill naming
  itself is not an invocation.
- **A requirement must be named together with the `Skill` tool, per
  requirement**, inside one *prose block* — a paragraph, with each markdown
  list item its own block and line wrapping ignored. This is what stops
  `requires` from drifting into a bare mention that would never fire, and it
  scales to the two-requirement Group B leaves. See review finding 2.
- **`build_graph` unions edges across versions.** Version pinning is Milestone
  6; until then, a cycle that exists in *any* version is a cycle worth refusing.
  Self-edges are filtered before cycle detection, because a self-requirement
  already gets its own, clearer message and reporting it twice buries it.
- **Every error message names the offending file**, which is what gate 6C will
  ask for; starting now is cheaper than retrofitting eleven leaves later.

---

## Where this leaves Milestone 3

**Milestone 2 is complete — both human gates passed and recorded — so Milestone
3 is unblocked.** Its first stop is human gate 3A (the runtime root), which sits
*before* any assembly code is written.

Milestone 3 assembles the sealed runtime directory. From this milestone it
inherits:

- Two skills to copy, discovered by `load_skills()` walking `SKILL.md` files —
  not by directory name, so assembly must copy by resolved name and version.
- The rule that the runtime must contain **every** skill of the checklist, so
  all descriptions compete. With only two skills the competition is trivial; it
  becomes a real test at Milestone 5.
- `identify-panels/schema.json` must reach the runtime (the shared skill's prose
  points at it), while `benchmark.json` and `eval-manifest.json` must not.

## Carried into Milestone 5

Decided at the gates, deliberately not acted on now:

| Item | From | What has to happen |
|---|---|---|
| `C top` / `C bottom` in `plot-axis-units` gold | 2A | A curator invented a sub-division the figure does not label. `identify-panels` is forbidden from inventing separators, so it will emit `C` and mis-align. **Settle before Group B conversion** |
| `B (H1.1)` / `B (RCC1)` / `B (H1t)` in `n_larger-two` | 2A | Same class, but not a `fig-checklist` check, so lower priority |
| 9 divergently-curated rows in `10.1038_s44319-025-00631-1` | 2B | `from_the_image` describes where the bar sits instead of what it reads. Curation, not prose |
| The multi-bar `from_the_image` rule | 2B | Accepted as-is. One line if the 2 affected rows ever justify it |
| Preamble repetition across skills | 2B | Harmless at two skills; revisit at eleven |
| `panel-image-matches-caption`'s future `description` | 2A | Must claim *comparison*, not *identification*, or it competes with `identify-panels` |
| Point `TestTheLeafProseMatchesItsContracts` at each new leaf | review | It is check-agnostic by design |
| **`soda_mmqc/data/examples/` is gitignored** | 2A | Gold edits have no diff and no git undo. The measuring stick for every score should be tracked **before Milestone 5 moves scores in bulk** |
