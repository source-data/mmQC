# Thinking catalog

Skim this file first when answering from the wiki; then open linked pages. **Update on every ingest** (new page, major edit, or merge of external notes) so links and blurbs stay current.

Optional columns: **date** (last meaningful update), **sources** (rough count or “—”).

| Page | Blurb | date | sources |
|------|--------|------|---------|
| [README.md](README.md) | Markdown-only wiki: usage, maintenance, conventions. | 2026-04-30 | — |
| [evaluation-json-vs-open-source.md](evaluation-json-vs-open-source.md) | Custom `JSONEvaluator` vs Inspect.ai / OSS; Hungarian lists; no full framework replacement. | 2026-04-30 | ext |
| [evaluation-scoring.md](evaluation-scoring.md) | Normative flat leaf scoring: schema-driven predictive vs collection lists, `list_alignment` validation, extended-primitive compare modes (`align` / `positional` / `join_string`), layer S, layers 1–2. | 2026-07-13 | — |
| [evaluation-implementation-plan.md](evaluation-implementation-plan.md) | Progressive build plan: phases 1–5.3 complete; Phase 6 integration deferred. | 2026-07-13 | — |
| [evaluation-toy-examples.md](evaluation-toy-examples.md) | Worked gold/pred toys: leaf instances, `by_property`, `by_list` (layer S on `panels`); extended-primitive mode illustrations (B.4–B.5). | 2026-07-13 | — |
| [evaluation-hierarchical-scoring-DEPRECATED.md](evaluation-hierarchical-scoring-DEPRECATED.md) | **DEPRECATED:** recursive roll-up/drill-down; use [evaluation-scoring.md](evaluation-scoring.md). | 2026-05-21 | — |
| [evaluation-leaf-primitives.md](evaluation-leaf-primitives.md) | Primitives, extended primitives (`string[]`, three compare modes), and **`score`**; layer S is out of scope here. | 2026-07-13 | — |
| [visualization-plan.md](visualization-plan.md) | Flat eval reporting: notebook-first `soda_mmqc/reporting/` API, Layer S/1/2 plots, interactive drill-down tables (itables); CLI deferred. | 2026-06-12 | — |
| [curation-document-viewer.md](curation-document-viewer.md) | Document curation plan **locked**: Phase 0 `WordExample`→`document_to_html`, HTML viewer, single-docx rule, manual QA. | 2026-08-11 | ext |
| [agentic-checklist-skills.md](agentic-checklist-skills.md) | Design brief: nested skills per checklist (DAG), leaf=check+schema, skills SoT + generated dag, Python example loop, eval CLI split, Anthropic agents first. | 2026-07-22 | — |
| [agentic-checklist-conversion-plan.md](agentic-checklist-conversion-plan.md) | mmQC agentic DAG pipeline plan: code under `soda_mmqc/agentic`, checklist-owned DAGs under `<checklist>/agentic`, orchestrated skill-scoped sub-agents, typed artifacts, restricted MCP/scripts, tests, and human gates. | 2026-08-06 | — |
| [experiments/README.md](experiments/README.md) | **Catalog:** skill-design experiment series (`exp-NN`) behind the paper's results section — how skills are written, organized and chained. Per-experiment notes live in that folder. | 2026-09-18 | — |
| [plans/](plans/) | Dated milestone plans and results for the agentic conversion (milestones 1-6, handoffs). Not individually catalogued. | 2026-09-15 | — |
