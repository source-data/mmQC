# mmQC check run

You are running one quality-control check on one example from a scientific
manuscript.

## What you have

The example's content came with the request: read it there. Nothing needs to
be found or opened before you can start.

- `input/inputs.json` — supporting files, if this example has any, and the
  exact path of each. They are available if you need them; most checks do
  not.
- `input/` — those files, under their original names.

Paths outside this directory are not available and not needed. There is no
shell, no file search and no directory listing: if a file matters,
`inputs.json` names it.

## How to work

1. Follow the skill you were dispatched with. If it names another skill,
   invoke that skill rather than reimplementing what it does.
2. Answer with the structured output you were given a schema for. Report what
   you observe; do not guess to fill a field.
