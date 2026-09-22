# mmQC check run

You are running one quality-control check on one example from a scientific
manuscript.

## What you have

The example's content came with the request: read it there. Nothing needs to
be found or opened before you can start.

- `input/inputs.json` — the *additional* files this example carries, if any,
  and the exact path of each. They are there if you need them; most checks
  do not. What you were already sent is not listed again.
- `input/` — the example's files, under their original names.

Paths outside this directory are not available and not needed. There is no
shell, no file search and no directory listing, so anything not sent to you
and not named in `inputs.json` is not meant to be found.

## How to work

1. Follow the skill you were dispatched with. If it names another skill,
   invoke that skill rather than reimplementing what it does.
2. Answer with the structured output you were given a schema for. Report what
   you observe; do not guess to fill a field.
