# mmQC check run

You are running one quality-control check on one figure from a scientific
manuscript. Everything you need is in this directory.

## Where things are

- `input/inputs.json` — what was staged for this run and the exact path of
  each file. **Read it first.** The harness resolved these paths; they are
  not to be guessed at or searched for.
- `input/` — the figure image, the caption, and any source data, under their
  original filenames.
- `artifacts/` — the only writable location.

Paths outside this directory are not available and not needed. There is no
shell, no file search and no directory listing: if a file matters,
`inputs.json` names it.

## How to work

1. Read `input/inputs.json`, then the files it names. Open the figure image —
   a check about what a figure shows cannot be answered from its caption.
2. Follow the skill you were dispatched with. If it names another skill,
   invoke that skill rather than reimplementing what it does.
3. Write intermediate artifacts other skills need into `artifacts/`.
4. Answer with the structured output you were given a schema for. Report what
   you observe; do not guess to fill a field.
