# The agentic OpenAI driver does not enforce the schema

**Status:** open defect, deferred. Found 2026-09-20 while preparing a
cross-provider smoke run; the run was not made, because it would have
measured this rather than the skills.

## The finding

Three places in this repository send a check to a model. Two enforce the
output schema mechanically. The one that runs agentic checks on OpenAI does
not pass it at all.

| Path | Call | Schema |
|---|---|---|
| Legacy | `client.responses.create(..., text=schema)` — [`lib/api.py:589`](../soda_mmqc/lib/api.py) | **Enforced.** `text=` is the Responses API's structured-output parameter, and `schema` is the whole `schema.json` envelope |
| Agentic, `claude-sdk` | `output_format={"type": "json_schema", "schema": …}` — [`cli.py:1783`](../soda_mmqc/cli.py) | **Enforced** by the Agent SDK |
| Agentic, `openai` | `chat.completions.create(model=…, messages=…, tools=…)` — [`agentic_openai.py:284`](../soda_mmqc/agentic_openai.py) | **Nothing passed** |

The `openai` package is current (2.20.0) and the capability is not missing.
The agentic driver is simply the one component built on **Chat Completions**
while the rest of the project uses **Responses**, and it never passes the
schema on either surface.

## Why it matters more than it looks

Every `schema.json` in every checklist stores its contract in the Responses
API's shape:

```json
{"format": {"type": "json_schema", "name": "<check>", "schema": { … }}}
```

That envelope exists *because* `lib/api.py` passes it to `text=`. So the
project already has, for every check, exactly the object the agentic driver
would need — and the driver ignores it.

What the `claude-sdk` path says about its own `output_format` is the whole
argument:

> The schema is enforced, not described. Prose asking the model to "conform
> exactly" is a request; this is a constraint, and the M2 spike measured it
> reaching enum level — the model could not write "MAYBE" into a yes/no field
> even when told to.

On the OpenAI agentic path there is only the request. The runner takes the
prediction from the session's final text and raises *"The session returned no
structured result"* when it cannot parse it, so a model that answers in prose
produces a failed run rather than a wrong one — the failure is loud, which is
something, but it is a retry loop standing in for a constraint.

## The consequence for experiments

**A cross-provider comparison is currently uninterpretable.** The two agentic
providers differ in a way that has nothing to do with the skills under study:
one is constrained to the schema and one is asked politely. Any difference in
scores between them is confounded with that, and no experiment design can
separate the two after the fact.

Single-provider work is unaffected. The `claude-sdk` path is the one the
experiment series uses, and it is the enforced one.

## What the fix probably is

Move the agentic driver to `client.responses.create(..., text=schema)`,
matching both the legacy path and the `claude-sdk` path, and reusing the
envelope already stored in every `schema.json` rather than translating it
into the Chat Completions `response_format` shape.

This is not a one-line change. The driver's whole loop is written against
Chat Completions: `response.choices[0].message`, `message.tool_calls`, the
assistant-message round-trip in `_assistant_message`, and the tool schemas in
`_tool_schemas` all follow that surface. Responses uses a different request
and response shape for tools and for the conversation it accumulates.

The alternative — staying on Chat Completions and passing
`response_format={"type": "json_schema", "json_schema": {"name": …, "schema":
…, "strict": true}}` — is a smaller diff, but it means the repository would
carry two spellings of the same contract and a translation between them.
Given that the stored envelope is already Responses-shaped, converging on
Responses looks like the honest end state.

## Related

- A neighbouring defect, fixed 2026-09-20: the same driver was still
  advertising a `Write` tool as *"the only writable location"* after
  `218fe013` removed writing from the `claude-sdk` profile, so the two
  providers were not running the same session in that respect either. The
  tool, its dispatch branch, its implementation and the nudge telling the
  model to write `artifacts/prediction.json` are gone. That nudge could never
  have worked: the runner reads the prediction from the final text, so a
  model obeying it wrote a file nothing reads and the run then failed for
  want of a structured result.
- [`plans/2026-09-20-example-owned-staging-and-agentic-split.md`](plans/2026-09-20-example-owned-staging-and-agentic-split.md)
  — the refactor during which this surfaced. Its Phase 2 moves this driver to
  `soda_mmqc/agentic/openai_driver.py`; fixing the schema gap is deliberately
  **not** part of that move, which is meant to change no behaviour.
