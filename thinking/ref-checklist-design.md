---
title: Reference checklist (design note)
date: 2026-10-20
tags: [ref-checklist, references, citations, skills, curation, perturbation, harness, tools]
status: draft
sources:
  - https://arxiv.org/html/2601.05103v1
  - https://doi.org/10.1162/qss_a_00146
  - https://docs.scite.ai/
  - https://api.biorxiv.org/
---

# `ref-checklist` — design note

Planning only. No skill, schema or data is written yet. This note sets out
what the reference checklist should check, the harness extension it needs
(tools in the session), how the skills nest, what one document's output
looks like, and how to build a curated set we do not have, by spiking
errors into real articles and preprints.

The decisions this note asks for are collected in
[Decisions needed](#decisions-needed). Taxonomies proposed here (citation
function, cited-work type, identity-match grades) are drafts for a human to
settle, not choices made by this note.

## What the checklist should catch

| # | Check | What goes wrong when it fails |
|---|-------|-------------------------------|
| 1 | Every in-text citation matches an entry in the reference list, and every entry is cited | A claim with no traceable source, or a list padded with uncited works |
| 2 | Each entry is described well enough to be resolved (DOI, URL, or journal + volume + pages) | A reader cannot find the work |
| 3 | The DOI/URL resolves to the work the entry describes (title, authors, year, venue agree) | A typo at best, a **hallucinated reference** at worst |
| 4 | The cited work is not retracted (or the retraction is acknowledged) | The manuscript rests on withdrawn evidence |
| 5 | Each citation's function is classified from its context | Input to editors and to check 7; not a pass/fail on its own |
| 6 | Each cited work's type is identified (research article, review, preprint, book, …) | Input to editors; some combinations are findings (see below) |
| 7 | The cited work belongs in the passage and in the paper where it is cited, whatever its stance | An out-of-context citation: an error (wrong entry), a hallucination, or a citation inserted for other reasons than the science |

Checks 1–4 are **verifications** with a right answer. Checks 5–6 are
**classifications** that describe rather than judge. Check 7 is a
**judgement** that two careful readers can disagree on. The three kinds
need different gold, different metrics and different confidence in the
result, and the plan below treats them differently.

## Harness extension: tools in the session

Checks 3, 4, 6 and 7 depend on the outside world: what a DOI resolves to,
whether a work has been retracted, what Crossref or PubMed calls it, what
its abstract says. Today a session has exactly one tool, `Skill`, and no
network ([agentic/CLAUDE.md](../soda_mmqc/agentic/CLAUDE.md)). The
reference checklist needs that changed.

**Decided (2026-10-21): network access goes only through specific tools we
control. No built-in `WebFetch`.** `WebFetch` is not a plain fetch: it
converts the page and has a separate small model answer a prompt about it,
so what the session sees would depend on a second, unpinned model. It cannot
be recorded and replayed at our layer, and the OpenAI side has no
equivalent. Even fetching an arbitrary URL is our own `fetch-url` tool. The
registry below is built so that `WebFetch` can be granted later as one more
capability name, if it turns out to be needed.

### What the harness does today

- [runtime.py](../soda_mmqc/agentic/runtime.py) builds the session options:
  `tools` is `AGENTIC_BASE_TOOLS`, `allowed_tools` is
  `AGENTIC_ALLOWED_TOOL_NAMES`, `permission_mode` is `dontAsk`, so an
  unlisted tool is absent rather than merely denied.
- [pinning.py](../soda_mmqc/agentic/pinning.py) refuses any
  `model-defaults.yaml` that touches `allowed_tools`, `disallowed_tools`,
  `permission_mode`, `setting_sources`, `skills` or `cwd`. This is
  deliberate: "the containment boundary is a property of the runtime rather
  than of a checklist".
- The OpenAI driver ([openai_driver.py](../soda_mmqc/agentic/openai_driver.py))
  hand-builds a single `Skill` function schema and runs its own loop on
  Chat Completions. It was a stopgap from when the project had only an
  OpenAI key.
- The PostToolUse trace records `Skill` calls only.

### Proposal: a leaf contract requests named capabilities, the runtime grants them

Add a provider-neutral `model-config.yaml` to the check contracts, next to
`schema.json`, `eval-manifest.json` and `benchmark.json` (above the version
directories, so two versions of a check are compared under the same
capabilities):

```yaml
# ref-checklist/reference-identity-match/model-config.yaml
tools:
  - fetch-url
  - doi-resolve
  - bibliographic-search
  - compare-metadata
```

The containment principle is kept by making the contract name
**capabilities** from an mmQC-owned registry, never raw tool rules:

1. **Registry, owned by the runtime.** Each capability name maps to one
   plain Python function, with an input/output schema and a `network:
   yes/no` flag. No shell, no file tools, no generic `run_script`. This
   matches the conversion plan's `needs.mcps`/`needs.scripts` ("named
   semantic operations with typed inputs"). How a function reaches the
   model is the job of a thin adapter per driver (see
   [Implementation](#implementation-one-registry-thin-adapters)). The
   contract never says whether a tool is MCP.
2. **Union over the closure.** A session assembled for `do-ref-checklist`
   holds the union of the capabilities its reachable checks request. A check
   run on its own holds only its own. The union is computed at assembly and
   written into the SkillSet record, so the digest covers it.
3. **The pinning guard stays.** `model-defaults.yaml` still cannot set
   tools. The new file is read by the runtime, which validates every name
   against the registry and refuses unknown ones. The boundary is still in
   the runtime: the checklist chooses from a menu and cannot write to it.
4. **Trace every tool call**, not only `Skill`: name, input, and a digest of
   the response. "What the model saw" is no longer just the request, so it
   has to be recorded.
5. **Cache key** gains the capability set and the replay-store version (see
   below).

`fig-checklist` is unaffected: its checks request no tools, so its sessions
keep exactly today's profile. Making the tool set explicitly empty for those
checks would be a cheap regression test.

### Tools for this checklist (draft)

Split each lookup into deterministic **retrieval** (a tool) and **judgement**
(the skill, scored). Retrieval is ordinary engineering, unit-tested like
code. Judgement is what the benchmark measures.

| Capability | Network | Input → output | Serves |
|---|---|---|---|
| `doi-resolve` | yes | DOIs (batch) → Crossref/DataCite record, HTTP status, landing URL | 2, 3, 6 |
| `bibliographic-search` | yes | title/authors/year → top-k candidates (Crossref, PubMed, OpenAlex) | 3 when no DOI |
| `retraction-status` | yes | DOIs (batch) → retraction / EoC / correction, with date and notice DOI | 4 |
| `compare-metadata` | no | entry as written + record → per-field similarity (normalised title, author-list alignment, year, venue, pages) | 3 |
| `fetch-abstract` | yes | DOIs/PMIDs (batch) → abstract, MeSH where available | 7 |
| `fetch-url` | yes | URL → status, final URL after redirects, title, cleaned text (truncated) | 3 for URL-only entries, data and software links |

Sources these functions would wrap:

- **DOI → metadata:** Crossref REST (`/works/{doi}`), doi.org content
  negotiation for DataCite DOIs (datasets, Zenodo, figshare).
- **No DOI:** Crossref bibliographic query, PubMed citation matcher, OpenAlex
  title search. The `pubmed` and `openalex` MCP servers in this environment
  cover the last two for prototyping.
- **Retractions, corrections, expressions of concern:** the Retraction Watch
  database (open through Crossref since 2023), Crossref `update-to`
  relations, PubMed publication type *Retracted Publication*, OpenAlex
  `is_retracted`. Use them together, because each misses cases the others
  catch.
- **Type:** Crossref `type`, PubMed publication types (which, unlike Crossref,
  mark *Review*), OpenAlex `type`. Preprint ↔ published version from
  Crossref `is-preprint-of` / `has-preprint`.
- **Abstract:** PubMed, Europe PMC, Crossref when deposited.

**Batch inputs matter.** A manuscript has 50–120 references. One tool call
per reference per lookup would take hundreds of turns against today's
ceiling of 40 (`model-defaults.yaml`). Batch operations keep the turn count
roughly constant in the number of references, and the ceiling becomes a
per-checklist setting.

`compare-metadata` is the mechanical comparison: normalised string
similarity, author-list alignment. It gives the skill evidence, not a
verdict. The skill decides whether "Li J" vs "Lee J" is a typo, whether a
missing subtitle matters, whether a consortium author is consistent.

### Implementation: one registry, thin adapters

Whether a tool is "direct Python" or "MCP" is not a choice the contract
makes, and on the main path it is barely a choice at all:

- **`claude-sdk`:** the Agent SDK (0.2.165 installed) provides `@tool` and
  `create_sdk_mcp_server`. Plain Python functions are served as an MCP
  server **in our own process**, with no subprocess and no stdio. The model
  sees `mcp__mmqc__doi_resolve`, and `allowed_tools` lists that name. On
  this path a Python tool *is* an in-process MCP tool.
- **OpenAI driver:** no MCP layer. A capability is one more function schema
  whose handler calls the same Python function.
- **Optional, later:** a stdio MCP server over the same registry, to use
  the tools from Claude Code or another host outside the harness.

```text
model-config.yaml        names: doi-resolve, compare-metadata, fetch-url …
        │
registry (runtime)       name → Python function + input/output schema + network: yes/no
        │                record/replay wraps every network: yes function here
        ├── claude-sdk   create_sdk_mcp_server(subset)   → mcp__mmqc__doi_resolve
        ├── openai       function schemas, dispatched by the driver (deferred)
        └── (optional)   stdio MCP server, same registry, for use outside the harness
```

In-process is preferred over a separate local MCP server. Replay,
compact projections and the tool trace all wrap one function call. There
is no server lifecycle to manage across 38 concurrent sessions. Unit tests
call the function directly.

### Reproducibility: record and replay

Live lookups break the benchmark in two ways. Gold drifts when a paper is
retracted after curation or a DOI starts resolving. Reruns diverge when an
API answers differently. Proposal:

- **Record mode** (production, and curation): tool calls go live, and every
  request/response pair is stored in a replay store keyed by
  `(capability, normalised request)`.
- **Replay mode** (benchmark runs): tool calls are served from the store
  captured at curation. A request missing from the store returns a
  recorded-miss error rather than going live, and the trace counts these.
  Many misses means the skill asks questions the curation did not anticipate.
  That is worth knowing, but it must not be silently answered by today's
  web.
- `fetch-url` replays too. Pages are stored as fetched.
- Only `network: yes` functions are recorded and replayed. A pure function
  like `compare-metadata` is deterministic and is simply called.

Replay also solves rate limits: at concurrency 38, live Crossref traffic
from 38 sessions × ~80 references needs the polite pool and backoff. In
replay mode it needs nothing.

### Other consequences to plan for

- **Drivers: the OpenAI arm is deferred (decided 2026-10-21).** Build and
  run on `claude-sdk` only. Keep the registry provider-neutral, so that
  another provider needs only an adapter. When the OpenAI arm resumes, the
  likely path is to replace the hand-written Chat Completions loop with
  OpenAI's Agents SDK (`openai-agents`, not installed today), rather than
  extend the loop. That SDK should cover function tools from Python
  functions, MCP servers, structured output (which would also close
  [openai-agentic-structured-output.md](openai-agentic-structured-output.md))
  and run hooks for tracing. `Skill` would stay a function tool returning
  the skill's body, as it is in today's driver. This is from memory of the
  SDK, and needs checking against its docs when the work resumes.
- **Untrusted content.** Fetched pages are third-party text inside a scored
  session. They can carry instructions. The skill prose should say that
  fetched content is evidence, never instruction, and the replay store makes
  any incident reproducible.
- **Session length.** Tool results are large: a page, a Crossref record per
  reference. Returning compact projections (the fields the skill needs, not
  the raw JSON) is the tool's job.

## Unit of analysis: one document

The harness runs per document, as it runs per figure. One example is one
manuscript. Its references and citations are lists inside the output schema,
as panels are inside a figure's output, and accuracy on those lists is
scored at layer S (Hungarian row matching on `list_alignment` keys, then
layer 1/2 on matched rows).

### Two lists, and which checks use which

| List | Row | Checks | Natural count |
|---|---|---|---|
| `references[]` | one entry of the reference list | 1 (is it cited), 2, 3, 4, 6 | 50–120 |
| `citations[]` | one in-text citation of one entry | 1 (does it match), 5, 7 | 100–300 |

A citation group `(Smith 2019; Lee 2020)` gives two rows. A reference cited
four times has four citation rows.

**Options for the citation rows:**

- **(a) Flat `citations[]` at the root**, each row carrying the
  `reference_id` it resolves to (or none). Orphan citations, which have no
  entry, fit naturally. That is exactly what check 1 must report.
- **(b) Nested `references[].citations[]`.** The evaluator supports nested
  predictive lists: `plot-axis-units` aligns `axis` rows inside `panel_label`
  rows in [do-fig-checklist-cm's manifest](../soda_mmqc/data/checklist/fig-checklist/do-fig-checklist-cm/eval-manifest.json).
  It reads well for 5 and 7, but has nowhere to put an orphan citation.

Recommendation: (a) for checks 1, 5 and 7, and `references[]` for 2, 3, 4
and 6. Each check owns one list, as each `fig-checklist` check owns its
`outputs[]` of panels.

### Alignment keys

Layer S is only as good as its keys. `fig-checklist` aligns on
`panel_label`, which the figure prints. References and citations have no
printed label in author-year style, so the choice needs care:

**Agreed (2026-10-21): fuzzy text match, not semantic similarity.** The
keys are excerpts copied from the document, so a correct prediction is
nearly the same string as the gold. Edit distance (`string_compare:
fuzzy`, rapidfuzz `fuzz.ratio` after lowercasing and stripping, already in
[leaves.py](../soda_mmqc/core/leaves.py)) detects that. Semantic similarity
would also match a paraphrase, or a different sentence about the same
thing, which is what alignment must not do.

- **References:** keys `first_author` (surname only, as written) and `year`
  (as written, with any `a`/`b` suffix), both fuzzy. `reference_id`, the
  1-based position in the list, is reported and scored as an ordinary field
  but is **not** a key: one skipped entry would shift every later position.
  Two entries with the same surname and year and no suffix tie. That is
  rare, and it is also the linkage error check 1 reports.
- **Citations:** keys `marker` (as written, `Smith et al, 2019`) and
  `sentence` (the sentence it sits in), both fuzzy. The ordinal position
  (n-th marker in reading order) is not used, for the same reason as
  `reference_id`. Hungarian matching resolves repeats of the same marker in
  the same sentence by order.
- **Venue is left out for now.** `publication_venue` would separate
  same-author, same-year entries, and every type has one: the journal for
  an article, the publisher for a book, the server for a preprint, the
  hosting database for a dataset, the domain for a web page. The problem is
  the spelling, not the existence. The same venue is written several ways
  (*J Cell Biol* / *J. Cell Biol.* / *Journal of Cell Biology*; *bioRxiv* /
  *Cold Spring Harbor Laboratory*; *Oxford University Press* / *OUP*), and
  edit distance scores those as different. A key that misses on correct
  predictions harms alignment more than it helps. Add it only if ties turn
  out to matter, and then with normalisation (e.g. ISSN-based journal
  abbreviations) rather than raw strings.
- **To be seen:** `fuzz.ratio` compares whole strings, so a prediction that
  copies a shorter or longer span of the sentence than the gold scores
  lower than its correctness deserves. If that shows up in the first runs,
  a partial-match variant (`fuzz.partial_ratio`) would be a new
  `string_compare` mode. Until then, the schema should say to copy the
  whole sentence, and thresholds should be set from observed scores.

### Scale, coverage and dispatch

One session per manuscript, running seven checks over ~80 references and
~200 citations, is a much bigger job than one figure with eleven checks.
[exp-08](experiments/exp-08-arrangements-sonnet.md) left partial dispatch
open even at figure scale. Here there is a second failure: **partial
coverage**, a check that reports the first 30 references and stops. Layer S
recall on `references[]` and `citations[]` measures this directly, so it
should be a headline number from the first run, not a footnote. Batch tools
(above) keep the turn count down. The `max_turns` ceiling for this checklist
should be set from measured sessions, as exp-07 did for `fig-checklist`.

### On-disk sketch

Per document, as the existing `doc-checklist` examples are:

```text
soda_mmqc/data/examples/<document>/
  content/<document>.docx                           # what the model sees: a real submission, or its spiked copy
  source/fields.json                                # citation→reference links and metadata read from reference-manager fields; never sent to the model
  source/spikes.json                                # verified spike log, for spiked documents
  checks/<check>/expected_output.json
  replay/                                           # recorded tool responses for this document
```

**Decided (2026-10-21): examples are in the format of the application, as
for every `doc-checklist` check.** A manuscript arrives as Word (or PDF).
The `Example` subclass named by `example_class` in `benchmark.json` turns it
into model input. Today that is `word`: `WordExample` takes exactly one
`.docx` from `content/` and converts it with `document_to_html`
([documents.py](../mmqc_utils/src/mmqc_utils/documents.py)), which is
pandoc `docx → HTML`, with a PDF fallback in the same function.

**Not the pandoc AST, either.** The application converts Word through
pandoc's AST too, but storing the AST would skip pandoc's `.docx` reader,
which is the step that deals with real Word mess (field codes,
superscripts, text boxes, tracked changes). A conversion failure there is
part of what the benchmark should be able to show. The stored example is
the `.docx`. AST and HTML are derived from it at run time.

**Decided (2026-10-21): the base is real Word submissions, spiked in
place.** See [Base documents](#base-documents). The JATS route (render
published XML to a submission-like `.docx`) was probed and works for EMBO
articles. It is set aside because rendered documents are clean in ways
real submissions are not, and the gold would be built on that cleanness.
The probe is kept in [Appendix: the JATS route](#appendix-the-jats-route).

## Skill tree (draft)

```text
do-ref-checklist                      entry: the whole checklist on one document
├── citation-reference-linkage        check 1          → citations[], references[].cited
│   ├── list-reference-entries        shared
│   └── list-citation-markers         shared
├── reference-resolvable              check 2          → references[]
│   └── list-reference-entries
├── reference-identity-match          check 3          → references[]     tools: doi-resolve, bibliographic-search, compare-metadata, fetch-url
│   └── list-reference-entries
├── reference-retraction-status       check 4          → references[]     tools: retraction-status
│   └── list-reference-entries
├── cited-work-type                   check 6          → references[]     tools: doi-resolve
│   └── list-reference-entries
├── citation-function                 check 5          → citations[]      tools: none
│   ├── list-citation-markers
│   └── read-citation-context         shared: the passage around a citation, and the part of it the citation attaches to
└── citation-context-fit              check 7          → citations[]      tools: fetch-abstract
    ├── list-citation-markers
    └── read-citation-context
```

Notes:

- **`list-reference-entries` and `list-citation-markers`** play the role
  `classify-panels` plays: the inventory every check starts from. Two
  inventories instead of one, because the lists differ.
- **`read-citation-context`** returns the sentence and paragraph around a
  citation, and the part of the sentence it attaches to, which is rarely
  the whole sentence: in "X binds Y (A 2019) and is degraded by Z (B 2020)",
  each citation attaches to half of it. `citation-function` reads the
  attachment. `citation-context-fit` reads the passage.
- exp-08 found the separate inventory skill invoked in 27 of 185 sessions
  when it was available. Measure whether these shared skills are used before
  relying on them.
- **Self-citation** is not a function of the context. It is a property of
  two author lists, the manuscript's and the cited work's, and `doi-resolve`
  returns the second. Proposal: a field in `reference-identity-match` (or
  `cited-work-type`), with the matching done by `compare-metadata` and the
  skill adjudicating ambiguous initials. Not a check of its own.
- **Linkage** in author-year style (EMBO Press house style) needs care that
  numbered style does not: `et al.`, `Smith & Jones`, `2019a/b` suffixes,
  narrative `Smith et al (2019) showed`, and two `Smith 2019` entries
  without suffixes. Submissions to other journals add numbered,
  superscript and bracketed styles. Reference-manager fields (EndNote,
  Zotero, Mendeley) carry the citation→entry link in most submissions. They
  are read separately as gold and do not reach the model (see
  [Base documents](#base-documents)).

## The checks in more detail

### 1. `citation-reference-linkage`

Per citation: `matched_reference_id` or `none`, with the reason for no match
(`no_entry`, `ambiguous`, `year_mismatch`, `name_mismatch`). Per entry:
`cited: yes/no`. Mostly deterministic for numbered styles and close to it
for author-year. A strong regex/fuzzy baseline in code should be built
first, and the skill measured against it. If the skill does not beat the
baseline, the check should be code, or a tool the skill calls.

### 2. `reference-resolvable`

Whether the entry *as written* carries enough to identify the work:
identifier present (DOI, PMID, arXiv/bioRxiv ID, URL), or a complete
citation (journal, volume, pages or article number, year), or for books
(publisher, year). Output `sufficient / insufficient` with
`missing_elements[]`. This is judged from the entry alone, without tools,
so a correctly formatted fabricated reference passes here and is caught by 3.

### 3. `reference-identity-match`

The core anti-hallucination check. Given the entry and what the tools
return, grade the correspondence:

| Grade (draft) | Meaning | Typical cause |
|---|---|---|
| `match` | Same work; differences are formatting only | — |
| `minor_discrepancy` | Same work; a field is wrong (year, page, author initial, title typo) | Clerical error |
| `points_elsewhere` | Identifier resolves, but to a **different** work | DOI typo, copy-paste from a neighbouring entry, citing the erratum or the preprint, **or fabrication** |
| `not_found` | Identifier does not resolve and no candidate matches | Broken link, or **fabrication** |
| `cannot_assess` | Lookup failed for a technical reason | A tool problem, not an author problem |

Per field: `title_agrees`, `authors_agree`, `year_agrees`, `venue_agrees`,
so that the grade is explained and partly scorable field by field.

`points_elsewhere` and `not_found` cannot tell a mistake from a fabrication
on their own. A hint that separates them: a mistake usually leaves the rest
of the entry consistent with *some* real work that a title search finds. A
fabricated entry has no real counterpart for its title + author combination,
and is often a **chimera** (real authors, plausible title, real journal,
none of which belong together). `bibliographic-search` supplies the
evidence, and the skill reports `likely_fabricated`.

### 4. `reference-retraction-status`

Status comes from the tool: `none / retracted / expression_of_concern /
corrected`. The judgement is whether the manuscript **acknowledges** it.
Citing a retracted paper to discuss the retraction, or flagged as
`(retracted)`, is legitimate. Citing it as support is not. Timing matters
too: a retraction after the manuscript's submission date is a lesser finding
than one before it. Output: `status`, `retraction_date`,
`acknowledged_in_text: yes/no`, `decision`.

### 5. `citation-function`

Per citation row. The non-exclusive categories asked for at reference level
then **emerge as the union** of exclusive per-citation labels: a reference
"supporting" in one place and "mentioning" in another is both. Each row
stays a single-label classification, which is easier to annotate, to score
(`multiclass`) and to agree on, and the scorer needs no multilabel metric.

Two orthogonal axes look right, following SOFT's separation of intent from
content:

**Axis 1: stance** (scite.ai smart citations; Nicholson et al. 2021, *QSS*):

- `supporting` — the citing statement supports the cited work's findings
- `contrasting` — it contradicts them
- `mentioning` — neither: background, attribution, method reference

**Axis 2: intent** (SOFT, Duan & Tan, arXiv:2601.05103, Jan 2026; one label
per citation): `Contextualize`, `SignalGap`, `HighlightLimitation`,
`JustifyDesignChoice`, `Use`, `Modify`, `EvaluateAgainst`.

SOFT also has a third, content-type axis: `PerformedWork`, `Discovery`,
`ProducedResource`. It distinguishes citing a method or reagent from citing
a finding, which matters for biology: "antibody from (Smith 2019)" is
`Use:ProducedResource`, "consistent with (Smith 2019)" is
`EvaluateAgainst:Discovery`.

How the categories asked for map onto these:

| Asked for | Stance | SOFT |
|---|---|---|
| providing credit | `mentioning` | `Use` / `Modify` on `ProducedResource` or `PerformedWork`; `Contextualize` for priority |
| prior supporting evidence | `supporting` | `Contextualize:Discovery`, `JustifyDesignChoice`, or `EvaluateAgainst` when agreeing |
| prior contradicting evidence | `contrasting` | `HighlightLimitation`, or `EvaluateAgainst` when disagreeing |
| self-citation | — | — (an author-list property, see above) |

Caveats to set expectations:

- SOFT was built on computational linguistics papers (ACL-ARC), with a
  264-instance cross-domain test set. It reports human–LLM κ around 0.6–0.7
  on intent, and macro-F1 falling from 0.65 to 0.56 out of domain.
  Biomedical text has not been tested.
- Secondary sources quote scite's own accuracy as high for `mentioning` and
  near 60% for `supporting`/`contrasting`. These are the rare and
  interesting classes.
- "Supporting" has two readings that annotators will confuse: *the citing
  statement agrees with the cited finding* (scite) versus *the citation is
  offered as evidence for a claim* (most citations in an introduction). The
  guideline has to pick one. The table takes scite's reading and lets SOFT's
  intent carry the other.

Which axes to adopt, and whether to collapse SOFT's seven intents for
biology, is a domain decision for a human to make. It is not settled here.

#### scite.ai: a source of gold, never a tool

**Decided (2026-10-21): scite annotates the gold, offline. It is not
available at inference.** `citation-function` is measured on what the skill
and the model can do from the manuscript alone. That is also the only
situation the application meets: scite has never indexed a submission, so at
inference it could offer only counts about the *cited* work, which would
nudge the label without classifying the statement. Keeping scite out makes
the skill's score a property of the skill, and the skill usable wherever
scite is not.

What the API offers (docs.scite.ai, checked 2026-10-20):

| Endpoint | Auth | Returns |
|---|---|---|
| `GET /tallies/{doi}`, `POST /tallies` (≤500 DOIs) | **public, no key** | per cited DOI: total, supporting, contradicting, mentioning, unclassified statement counts; a variant splits counts by citing section |
| `GET /api_partner/citations/citing/{doi}` | **partner token** (via sales) | every classified statement *toward* a DOI: `source` (citing DOI), `target`, `section`, `type`, `typeConfidence`, `expertClassification`; **no snippet text** |
| Papers | public | paper metadata |

**Tallies cannot annotate gold.** They are counts per cited work, not
labels per statement. Gold needs the citation graph, so the **partner token
is a prerequisite**, not an option.

**How the annotation works:**

1. **Only documents with a published version** can be annotated: scite
   indexes publications, not submissions. Several of the 15 `.docx` are
   published (their directory names are DOIs). For each, query the citation
   graph for every cited DOI and keep the statements whose `source` is the
   published article.
2. **Map statements to citation rows.** There is no snippet, so statements
   are matched by `(target, section, order of occurrence)`. The match is
   exact when a work is cited once in a section, and ambiguous otherwise.
   Ambiguous rows are left unlabelled rather than guessed.
3. **Submission ≠ published version.** Text changes between the two
   (revision, copy-editing) can move, add or drop citations. A row is
   labelled only when its cited work and section agree in both versions.
4. **Silver, then checked.** scite's own accuracy is low on the rare
   classes (near 60% for `supporting`/`contrasting`, as quoted second-hand).
   So every `supporting` and `contrasting` label, and a sample of
   `mentioning`, is confirmed by a human. Prefer `expertClassification`
   where scite has one. The confirmed labels are gold, and agreement
   between scite and the reviewer is reported.
5. **Spiked documents inherit it.** A stance-flip spike (see the catalogue)
   takes the flipped gold label of the row it rewrote.

**What scite does not cover:** only the stance axis. SOFT's intent and
content-type axes have no external source and would need human annotation
from scratch. If scite is the gold source, stance is the axis that scales,
which is an argument for making it the v1 axis (decision 5).

Open with scite: coverage of the journals in our set, rate limits on the
citation graph, and whether the terms allow the labels to be stored in the
repo as gold.

### 6. `cited-work-type`

Draft label set: `research_article`, `review`, `preprint`, `book`,
`book_chapter`, `monograph_or_thesis`, `conference_paper`,
`protocol_or_method`, `dataset`, `software`, `editorial_or_commentary`
(news & views, perspective, editorial), `correction_or_retraction_notice`,
`web_page`, `other`.

Mostly answered by `doi-resolve`, and gold is close to free from metadata,
with known gaps: Crossref calls reviews `journal-article`, and commentaries
are inconsistently typed. The skill's value is in those gaps and in
unresolved entries. Combinations worth surfacing as **findings**, not just
labels:

- cites a **preprint** whose published version exists (from `is-preprint-of`)
- cites a **correction notice** or **retraction notice** in place of the
  article (often a DOI copy error, overlapping check 3)
- a mechanistic claim supported only by a **review**, which belongs with
  check 7

### 7. `citation-context-fit`

Per citation row: **does the cited work belong where it is cited?** This
asks about topic, not stance. A citation can support, contrast or merely
mention, and all three fit when the cited work is about what the passage is
about. The check looks for citations that are **out of context**:

- a viewpoint on traditional Chinese medicine cited in a sentence about
  text-mining techniques;
- a mass-spectrometry method cited in a paragraph describing a DNA
  sequencing protocol.

Such citations arise from errors (the neighbouring entry, a reference
manager pulling the wrong record), from hallucinated references that
happen to resolve to a real but unrelated paper, and from citations
inserted for reasons other than the science (coerced citations, citation
rings, paper-mill references).

**Two levels of context**, judged separately:

| Field | Question | Context |
|---|---|---|
| `fits_passage` | Is the cited work about what this sentence and paragraph are about? | the sentence and its paragraph, from `read-citation-context` |
| `fits_paper` | Is the cited work within the scope of this paper at all? | the manuscript's title, abstract and topic |

Values: `yes`, `partly`, `no`, `cannot_assess`. The combination is the
finding:

| `fits_passage` | `fits_paper` | Reading |
|---|---|---|
| yes | yes | fits |
| no | yes | **misplaced**: in scope for the paper, wrong place. Typical of a wrong entry or a shifted citation number |
| no | no | **out of context**: unrelated to the paper. Typical of hallucination or manipulation |
| yes | no | rare: the passage itself digresses. Usually fine, worth an explanation |

Evidence about the cited work: title, abstract, venue, type, and subject
terms (MeSH, OpenAlex topics) from `fetch-abstract` and `doi-resolve`.
Topical fit is usually decidable from the title and abstract, because the
question is "is this about the same thing", not "does this paper show
that". `cannot_assess` is for works with no retrievable title or abstract.

**What this check does not do:** verify that the cited work actually says
what the sentence claims (*claim verification*). A paper on the right gene
and the right process, cited for a result it does not report, fits the
context and fails a claim check. That is a harder, separate check that
would need full text. It is not in v1.

Each row is judged on its own. The check assumes no pattern in how
out-of-context citations are distributed across a document.

## Curated set: building it by spiking

There is no gold set. The proposal is to generate most of it: start from
real submissions, establish their clean gold once, insert known errors with
an agent, verify every insertion mechanically, and let **the verified spike
log be the gold**. Human annotation is needed only where spiking cannot
produce a label (positives for check 5), and to establish the clean gold.

### Base documents

**Real Word submissions are the base.** They are what the application
receives: mixed styles, hand-edited lists, stale fields, superscripts,
pasted text. A benchmark built on a cleaner source would measure a cleaner
problem.

**Reference-manager fields give gold for free.** Probe on the 15 `.docx`
in `data/examples/` (2026-10-21):

| Field type | Documents | Carries |
|---|---|---|
| EndNote (`ADDIN EN.CITE`) | 7 | XML per citation: author, year, title, record number, ref type, DOI (`electronic-resource-num`; 21 of 22 readable blocks in one document) |
| Zotero (`ZOTERO_ITEM CSL_CITATION`) | 2 | CSL-JSON per citation, including DOI when the library has it |
| Mendeley (`MENDELEY CITATION`) | 2 | CSL-JSON per citation |
| none (plain text) | 4 | nothing: gold by hand |

Each field links one in-text citation to one library record, so it gives
the **citation→reference link (check 1)** and the **intended identifier
(check 3)**, the two things JATS `<xref>`/`<pub-id>` would have given.

- **Pandoc reads them only partly.** `pandoc -f docx+citations` found 147
  citations and 63 references in a Zotero document, 22 of 124 fields in an
  EndNote document, and none in a Mendeley one. EndNote stores most
  citations base64-encoded in `w:fldData` (`EN.CITE.DATA`) rather than as
  readable XML. So we need **our own field parser** for the three formats.
  It is small, and it is testable against these 11 documents.
- **The fields do not reach the model.** `document_to_html` shows the
  displayed text, not the field instructions, so the links are gold without
  leaking into the input. (To verify on all 11.)
- **A field can disagree with its displayed text**, when an author edited
  the citation or the list by hand after the manager last updated it. That
  disagreement is itself a real error, for check 1 or 3, and should be
  recorded as found, not smoothed over.

**Clean gold, once per document.** The fields (where present), plus an
agent's extraction of the reference list and citation markers, plus one
human pass to confirm. Real errors found in the base are kept as labelled
positives. They are the most realistic positives the set will have.

**Supply is the constraint.** 15 documents is enough to build the pipeline,
not a benchmark. More come from the editorial office. Those are unpublished,
confidential manuscripts: whether they may be used, sent to model and
lookup APIs, and kept in the repo, has to be settled before collecting
them. The benchmark could not be published as a dataset.

**Other sources, later or as controls.** Preprint ↔ published pairs
(bioRxiv `/pubs`, `/publisher/10.15252` for EMBO Press) give natural errors
corrected at copy-editing, as PDFs. bioRxiv preprints as PDFs give
variable, unedited reference lists. Neither is spikeable, and both need a
`pdf` example class.

### Spiking a real `.docx` with an agent

The spiker is an agent, because realistic errors need judgement: which
entry a tired author would mistype, what a hallucinated reference for this
sentence would look like, which retracted paper fits the topic. Its output
is not trusted. Every spike is verified by code.

1. **Plan.** The agent reads the document (and the clean gold), picks
   operators from the catalogue below and targets for them, and declares
   each spike: `{operator, location, before, after, expected_labels}`.
2. **Apply in place.** Edits go into the Word XML of the original file,
   copying the run formatting of the surrounding text. **Never as tracked
   changes or comments**, which would mark the spike. The file is never
   round-tripped through pandoc, which would normalise it. Tooling: the
   docx skill, or `python-docx` at run level.
3. **Verify mechanically.** Convert both versions with `document_to_html`
   and diff the text. The diff must equal the declared edits exactly, with
   nothing else changed. A spike that fails is rejected, not repaired by
   hand.
4. **Write the gold** from the clean gold and the verified log, in code.
5. **Record the world** for the spiked document: the replay store for every
   lookup the checks may make.

Separation: the spiking agent never sees the checklist's skills, and it runs
on a different model family from the one under test, so the set does not
reward a model for recognising its own style. A human reviews a sample of
spikes for realism.

### Perturbation catalogue

Each operator changes one thing and records `{document, operator, target,
before, after, expected_labels}`. A starting point:

| Check | Operator | Expected label | Difficulty |
|---|---|---|---|
| 1 | Delete an entry that is cited | citation → `none`/`no_entry` | easy |
| 1 | Delete every citation of an entry | entry `cited: no` | easy |
| 1 | Shift the year in one in-text citation (2019 → 2018) | `year_mismatch` | medium |
| 1 | Misspell the author in one in-text citation | `name_mismatch` or tolerated, per guideline | medium |
| 1 | Add a second `Smith 2019` entry, no a/b suffixes | `ambiguous` | hard |
| 2 | Strip DOI, volume and pages | `insufficient` | easy |
| 2 | Strip DOI only, leaving journal/volume/pages | still `sufficient` (control) | — |
| 3 | Transpose two digits in the DOI | `not_found` or `points_elsewhere` (fixed at recording time) | easy |
| 3 | Swap DOIs between two entries of the same list | `points_elsewhere` | medium: same field, plausible |
| 3 | Change year / one author / first page | `minor_discrepancy` | medium |
| 3 | Replace DOI with the DOI of the article's erratum or preprint | `points_elsewhere` (+ type finding) | hard |
| 3 | **Insert an LLM-generated reference** for the citing sentence | `not_found`, fabricated | hard: this is how hallucinated references arise |
| 3 | **Chimera**: real authors + real journal + title from another paper | `points_elsewhere` / fabricated | hard |
| 4 | Replace an entry with a retracted paper on a similar topic, keep the supporting sentence | `retracted`, not acknowledged → FAIL | medium |
| 4 | Same, and add "(retracted)" or a sentence discussing it | `retracted`, acknowledged → PASS (control) | medium |
| 6 | Replace an entry with a review / preprint / editorial on the same topic | the new type | easy from metadata |
| 5 | Rewrite the citing clause to flip stance ("consistent with" → "in contrast to") | flipped stance | **minimal pair**, tests sensitivity |
| 5 | Rewrite "using the method of" ↔ "as reported by" | `Use` ↔ `Contextualize` | minimal pair |
| 7 | **Insert** a new citation + entry for an out-of-context work | per tier, below | tiered by distance |
| 7 | **Swap** an existing citation's target for another work | per tier, below | tiered by distance |

**Context fit can be spiked automatically, with controlled difficulty.**
Choose the inserted or substituted work by its distance from the true one,
using OpenAlex concepts or abstract embeddings:

| Tier | Inserted or substituted work | `fits_passage` | `fits_paper` | Difficulty |
|---|---|---|---|---|
| unrelated | another field entirely (the TCM viewpoint in a text-mining paper) | no | no | easy, and exactly the target |
| adjacent method | same broad field, wrong technique (mass-spec method in a sequencing protocol) | no | partly/yes | medium |
| misplaced | another entry from the same reference list, from a different section | no | yes | hard: same paper, same vocabulary |
| control | another paper on the same topic as the original, any stance | yes | yes | — |

The control tier matters. Without it, the check can pass by flagging every
inserted citation, and the set only measures insertion detection. Distance
for choosing works per tier: OpenAlex topics or abstract embeddings between
the passage and the candidate.

The `unrelated` tier can draw on real cases: retracted paper-mill articles
and known citation-manipulation cases give realistic out-of-context
references, rather than random ones.

**Citation function is the hard one.** Spiking gives minimal pairs (does the
label flip when the stance is rewritten?), not the label of an untouched
citation. That comes from scite, offline, on documents with a published
version, confirmed by a human (see
[scite.ai: a source of gold, never a tool](#sciteai-a-source-of-gold-never-a-tool)).

The operators that need an LLM (fabricated references, chimeras, stance
rewrites) should use a **different model family** from the one under test,
with a human check on a sample, so the set does not reward a model for
recognising its own style.

### Principles

- **Gold is generated, not typed.** `expected_output.json` is written by
  code from the verified spike log and the clean gold. The generator has
  tests. A gold error is a bug to fix, not an annotation to argue about.
- **Every spiked document has its clean twin.** Score detection on the
  spiked rows, and **false alarms on the clean twin and on every untouched
  row**. Paired comparison removes most of the variance between documents.
- **Realistic prevalence.** Real reference lists have few errors. Spike 1–5
  per document, not half the list, and report precision at that prevalence.
  Use a separate high-prevalence set only for recall curves.
- **No telltale artefacts.** An inserted entry imitates its neighbours in
  the same list, including their inconsistencies. The run formatting of the
  surrounding text is copied. There are no tracked changes or comments.
  Otherwise the model finds spikes by formatting, and the set measures
  style detection.
- **Record the world at spiking time.** Each document's replay store is
  recorded when it is spiked. A fabricated DOI is confirmed not to resolve
  *at that moment*. A real DOI chosen to "point elsewhere" is confirmed to
  point where we say. The tools then replay that world in every benchmark
  run.
- **Base errors are found, not assumed away.** When a check flags an
  untouched row, that is either a false positive or a real error in the
  base. Route these to adjudication and fold confirmed ones into the gold.
  On real submissions this is expected and welcome: confirmed base errors
  are the most realistic positives in the set.
- **Difficulty tiers are reported separately.** One average over easy and
  hard operators hides exactly what we want to know.

## Evaluation contracts

Each check owns `schema.json`, `eval-manifest.json`, `benchmark.json` and
now `model-config.yaml`. `do-ref-checklist` owns a contract derived from
the checks' own, as `do-fig-checklist-cm`'s is
([build_contract.py](../experiments/exp-06-full-checklist/build_contract.py)).
`benchmark.json` has `example_class: word`, as every `doc-checklist` check does.

| Field kind | Metric |
|---|---|
| decisions (PASS/FAIL), `cited`, `acknowledged_in_text`, `likely_fabricated` | `binary_polarity` / `multiclass` |
| identity grade, retraction status, work type, stance, intent | `multiclass` |
| `missing_elements[]` | `string[]` extended primitive, `align` |
| `reference_id`, `matched_reference_id` | `graded_string`, exact |
| `first_author`, `year` (alignment keys) | `graded_string`, fuzzy |
| `marker`, `sentence` (alignment keys) | `graded_string`, fuzzy |
| `explanation` | not scored |

A sketch of one check's output, `reference-identity-match`:

```json
{
  "references": [{
    "reference_id": "17",
    "first_author": "Lee",
    "year": "2019",
    "title_agrees": "yes",
    "authors_agree": "no",
    "year_agrees": "yes",
    "venue_agrees": "yes",
    "grade": "minor_discrepancy",
    "likely_fabricated": "no",
    "self_citation": "no",
    "decision": "FAIL",
    "explanation": "Second author differs: entry has 'Lee J', the Crossref record has 'Li J'."
  }]
}
```

## Plan

1. **Decisions** below, with a human, in particular the citation-function
   taxonomy, the schema shape and the capability names.
2. **Harness extension.** Capability registry, `model-config.yaml` loading
   and validation, union over the closure, tool tracing, record/replay, on
   `claude-sdk`. Tests that `fig-checklist` sessions keep today's profile
   and that an unknown capability is refused.
3. **Tool functions.** `doi-resolve`, `bibliographic-search`,
   `retraction-status`, `compare-metadata`, `fetch-abstract`,
   `fetch-url`, as plain Python functions served in-process on `claude-sdk`,
   batch inputs, compact outputs. Unit tests on known DOIs, retracted papers,
   DataCite DOIs and fabricated DOIs.
4. **Base documents.** A field parser for EndNote (readable and
   base64 `fldData`), Zotero and Mendeley, tested on the 11 documents that
   have fields. Clean gold for the 15, with one human pass. Confirm that
   field instructions never reach `document_to_html` output. In parallel,
   settle the use of further editorial-office submissions.
5. **Agent spiker and verifier.** Operators for checks 1–4 and 6 first,
   because their labels are exact, then context-fit insertion with tiers.
   The text-diff verifier first, with tests: a no-op spike reproduces the
   clean gold, and an undeclared change is rejected. Replay stores recorded
   at spiking.
6. **Checks in isolation.** One check at a time on whole documents, against
   code baselines where one exists (1, 2, 4 status, 6). A check that does
   not beat its baseline becomes code, or a tool. Layer S recall
   (coverage) reported from the first run.
7. **Gold for 5** from the scite citation graph on the published
   documents, human-confirmed, and a human sample for 7,
   in parallel with 5–6.
8. **Integrated DAG.** `do-ref-checklist` on whole documents. Preregister
   integrated against isolated runs as an experiment in
   [experiments/](experiments/README.md), with dispatch and coverage as
   endpoints from the start.
9. **Unspiked sets.** Unspiked submissions, then preprint ↔ published
   pairs as PDFs (needs the `pdf` class). Adjudicate what the checklist
   flags and report precision there.

## Decisions needed

1. **Capabilities:** the contract file's name and shape
   (`model-config.yaml` with `tools:`), the initial registry, and whether
   capabilities sit with the contracts (shared by every version, as
   proposed) or per version.
2. **Replay:** replay-only for benchmark runs, with misses reported
   (recommended), or fall through to live on a miss?
3. **Schema shape:** `references[]` for 2/3/4/6 and a flat `citations[]` for
   1/5/7 (recommended), or nested `references[].citations[]`?
4. ~~**Alignment keys**~~ — agreed 2026-10-21: `first_author` + `year` for
   references, `marker` + `sentence` for citations, fuzzy match. Venue left
   out unless ties matter.
5. **Citation function:** scite stance, SOFT intent, SOFT content type, or a
   combination? Collapse SOFT for biology? Which reading of "supporting"?
6. ~~**scite**~~ — decided 2026-10-21: scite annotates gold offline and is
   never a tool at inference. Needs a partner token for the citation graph
   (contact sales@scite.ai), and terms that allow storing the labels.
7. **Self-citation:** a field computed with `compare-metadata` (recommended)
   or a check?
8. **Scope against `doc-checklist`:** `reference-format-alphabetical` checks
   house style. Leave it there (recommended), or move it into
   `ref-checklist`?
9. **Context fit:** topical fit at passage and paper level from title,
   abstract and subject terms (as reframed 2026-10-22). Claim verification
   is out of v1. Is the `partly` value needed, or is yes/no enough?
10. ~~**Base and format**~~ — decided 2026-10-21: real `.docx`
    submissions, spiked in place by an agent, verified by text diff. JATS
    set aside. A `pdf` class only if unspiked PDF sets are added later.
11. **Supply:** may further editorial-office submissions be used, sent to
    model and lookup APIs, and stored in the repo? How many, and from which
    journals?

## Appendix: the JATS route

Considered and set aside on 2026-10-21 in favour of real submissions (see
[Base documents](#base-documents)). Kept because it is the way to scale
beyond the editorial office's documents if that is ever needed, and
because the probe answers how hard it is.

### Probe: JATS → `.docx` (2026-10-21)

Tried on one EMBO J article (PMC11697293, from Europe PMC's
`fullTextXML`) with pandoc 3.7 to see whether step 3 is hard.

- **The references are already formatted.** In PMC's JATS for EMBO Press,
  every `<ref>` is a `<mixed-citation>` holding the printed string (`<named-content
  content-type="citation-string">`) plus the DOI, PMID and PMCID as
  `<ext-link>`s. There are no structured fields (no `<person-group>`,
  `<source>`). 74 refs, 141 in-text `<xref ref-type="bibr">`.
- **In-text links wrap only the year:** `Alberti et al, <xref rid="CR1">2019</xref>`.
  The author part is plain text before the link.
- **Pandoc renders the body and the in-text citations correctly, but drops
  the reference list.** Its JATS reader ignores `<mixed-citation>`. A
  20-line preprocessing step that replaces `<ref-list>` with a section of one
  `<p>` per citation string fixes it.
- **Round trip passes:** the repo's `document_to_html` on the rendered
  `.docx` shows the in-text citations and the reference strings verbatim.
  Figures become placeholders, which does not matter here.

So for **clean** EMBO documents, rendering is easy: the printed strings are
copied as they are, so there is no reference formatting to do. For
**spiked** documents:

- Edits to existing entries and markers (year shift, author misspelling,
  deleting an entry or a citation) are string edits on the XML before
  rendering. Still no formatting needed.
- **Inserted** entries (fabricated, retracted, context-fit insertions) must
  be formatted in the list's style. For a real DOI, doi.org content
  negotiation returns a formatted citation in any CSL style (`Accept:
  text/x-bibliography; style=…`), and CSL has an EMBO style. For a
  fabricated entry, the same CSL style is applied to invented CSL-JSON
  through citeproc (pandoc's, or `citeproc-py`).
- **bioRxiv was not tested.** Direct download of `.source.xml` was blocked
  (Cloudflare error 1015), so bulk access has to go through bioRxiv's
  text-mining channel. bioRxiv references come in every style. An inserted
  entry has to imitate its neighbours, which CSL cannot do for an arbitrary
  style. Options: pick the nearest CSL style, or copy a neighbouring entry
  as a template. This is the part that could become hard, and it only
  affects insertion operators on bioRxiv.

Pandoc's JATS reader puts `<element-citation>` references into the metadata
as CSL, and turns each `<xref ref-type="bibr">` into a `Cite` node. With
`--citeproc --csl <style>` it can re-render citations and bibliography from
edited CSL data, which would be the clean way to spike structured sources.
The catch is that the author part of an author-year citation sits outside
the `<xref>`, so citeproc output would duplicate it unless the XML is
cleaned first.
