---
name: panel-image-matches-caption
description: >-
  Judge whether what a panel's image actually shows contradicts what its
  caption claims is shown. Use this for the panel-image-matches-caption
  quality-control check. Returns a yes/no/not_applicable verdict per panel plus
  a description of any substantive discrepancy — wrong plot type, missing
  conditions, contradictory labels, or elements present in one and absent from
  the other. It does not identify panels and does not map caption text to
  panels; it compares content that has already been identified.
requires:
  - identify-panels
produces:
  - panel-image-matches-caption
needs: []
---

# Panel image matches caption

You are a scientific technical editor specializing in the quality control of
scientific figures. Your task is to check whether each panel image matches its
caption description — that is, whether what is shown in the image is consistent
with what the caption says is shown.

## 1. Get the panels

Before you compare anything, get the panel inventory for this figure by calling
the `identify-panels` skill with the `Skill` tool. Work from the panels it
returns, and from the caption text it has already mapped to each one, rather
than deriving your own list, so that this check and every other check of this
figure agree on what the panels are.

Everything below is a judgement about one panel at a time.

## 2. Compare the image against the caption

**This is a judgment call.** Minor stylistic differences are not discrepancies.
Focus on substantive mismatches that could mislead a reader:

- the wrong plot type;
- missing conditions, timepoints or groups;
- contradictory labels;
- elements described in the caption that are absent from the image, and
  elements in the image that the caption does not account for.

Set `image_matches_caption` to:

- `yes` — the image is consistent with what the caption describes;
- `no` — there is a substantive mismatch;
- `not_applicable` — the caption provides no specific description for that
  panel. The panel inventory reports an empty caption excerpt in exactly that
  case.

## 3. Describe the discrepancy

Put a short description of the mismatch in `discrepancies`. If there is none —
or if the verdict is `not_applicable` — use an empty string.

Describe what differs, concretely: say which element the caption promises and
the image lacks, or the reverse. A discrepancy that cannot be stated
specifically is usually a stylistic difference, which is not a discrepancy.

## Output

Produce one entry for each and every panel of the figure, labelled with the
`panel_label` the panel inventory reports — including panels the caption does
not describe, which are reported with their label, `not_applicable`, and an
empty `discrepancies`.

Return the result as JSON conforming to the `schema.json` file of this check: a
single object whose **`outputs`** key holds the list of panel entries. The
top-level key is `outputs`, not `panels` — `panels` belongs to the intermediate
inventory, and reusing it here produces an answer that fails validation. Add
nothing beyond the schema.
