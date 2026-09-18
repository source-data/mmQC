# Thinking wiki

Long-lived notes, design reflections, and context for **people and coding agents** working on this repository. Everything here is **versioned with the main repo** (unlike GitHub’s separate Wiki repo). The wiki is **Markdown only** under `thinking/` (no parallel HTML/CSS to maintain).

## How to use it

- **Skim the catalog first:** [`index.md`](index.md) — links, one-line blurbs, light metadata. Then open linked pages.
- **Read in GitHub or the IDE:** open `.md` files; GitHub renders them in the repo browser.
- **Agents:** treat this folder as authoritative project memory when it overlaps with the task; prefer linking to specific pages rather than duplicating long explanations in chat.
- **Timeline:** [`log.md`](log.md) — append-only activity log (ingests, queries, lint passes).

## How to maintain it

1. **New topic:** add a `.md` file under `thinking/`, use repo-relative links (see Conventions).
2. **Update the catalog:** edit [`index.md`](index.md) on every ingest (new page, rename, or substantive merge of notes).
3. **Log significant events:** append to [`log.md`](log.md) with the dated heading format below.
4. **Keep the catalog honest:** [`index.md`](index.md) should only list pages that exist.

## Special wiki files

In this repo these live under **`thinking/`** (not a separate `wiki/` directory).

- **[`index.md`](index.md)** — Content catalog: links, one-line blurbs, optional metadata (date, source count). **Update on every ingest.** When answering questions, skim the index first, then open linked pages.
- **[`log.md`](log.md)** — Append-only timeline. Prefix each entry with a parseable heading, for example:
  - `## [YYYY-MM-DD] ingest | …`
  - `## [YYYY-MM-DD] query | …`
  - `## [YYYY-MM-DD] lint | …`

  New entries go at the **bottom** of `log.md` so `grep '^## \[' thinking/log.md | tail -5` shows the latest activity.

## Subfolders

A subfolder under `thinking/` carries its own `README.md` catalog and gets
**one row** in [`index.md`](index.md) pointing at it, rather than a row per
page. This keeps the top-level catalog skimmable as a series grows, and lets
a sub-catalog use columns that suit it (an experiment wants status and
result; a design note wants a blurb).

- [`experiments/`](experiments/README.md) — skill-design experiment series.
- [`plans/`](plans/) — dated milestone plans and results.

**Markdown-only still holds here.** Jupyter notebooks belong in
`notebooks/experiments/`, not under `thinking/`: `.ipynb` is JSON carrying
execution counts and outputs, which diffs badly and buries prose a reviewer
needs to read. An experiment's note and its notebook are paired by sharing
the stem `exp-NN-<slug>`.

## Conventions

- **Markdown:** Prefer `[label](relative-path.md)` for links between wiki pages and into the codebase (e.g. `[evaluation.py](../soda_mmqc/core/evaluation.py)`). Paths are relative to the file containing the link.
- **Wikilinks:** If you introduce Obsidian-style `[[Page Name]]` links, use them **consistently** across `thinking/` and ensure the team’s tooling resolves them; otherwise stick to standard Markdown links so GitHub and generic agents behave predictably.
- **Frontmatter (optional):** YAML at the top of a wiki page can carry metadata for later tooling (e.g. Dataview-style queries, search, or agent filters):

  ```yaml
  ---
  title: Short title
  date: 2026-04-30
  tags: [evaluation, json, oss]
  sources:
    - https://inspect.ai-safety-institute.org.uk/
  ---
  ```

  Keep keys stable once you rely on them in scripts or prompts.

- **Tone:** Factual and durable; avoid one-off chat transcript dumps unless summarized into a reusable note.

## Pages (Markdown sources)

Canonical list with blurbs: **[`index.md`](index.md)**. Quick links:

| Topic | Markdown |
|--------|----------|
| Wiki usage and maintenance | [`README.md`](README.md) |
| JSON evaluation vs OSS frameworks | [`evaluation-json-vs-open-source.md`](evaluation-json-vs-open-source.md) |
| Flat leaf scoring (normative) | [`evaluation-scoring.md`](evaluation-scoring.md) |
| Evaluation toy examples (shared schema/manifest) | [`evaluation-toy-examples.md`](evaluation-toy-examples.md) |
| Leaf primitives (`score`, strings, numbers, booleans) | [`evaluation-leaf-primitives.md`](evaluation-leaf-primitives.md) |
| Hierarchical scoring (DEPRECATED) | [`evaluation-hierarchical-scoring-DEPRECATED.md`](evaluation-hierarchical-scoring-DEPRECATED.md) |
| Agentic checklist skills (design brief) | [`agentic-checklist-skills.md`](agentic-checklist-skills.md) |
