# API providers

SODA MMQC supports **OpenAI** and **Anthropic** for multimodal check execution with structured JSON output. Routing is controlled by `API_PROVIDER` in `.env`; implementation lives in `soda_mmqc.lib.api`.

## Environment setup

Create a `.env` file in the project root:

```bash
# API provider
API_PROVIDER=openai  # or 'anthropic'

# OpenAI (required when API_PROVIDER=openai)
OPENAI_API_KEY=your_openai_api_key_here

# Anthropic (required when API_PROVIDER=anthropic)
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional: PyTorch device for semantic scoring embedder
DEVICE=cpu  # 'cpu', 'cuda', or 'mps'
```

On import, `soda_mmqc.config` validates the setup:

- Logs a warning if the selected provider’s API key is missing (does not block import).
- Falls back to OpenAI with a warning if `API_PROVIDER` is unknown.

## Default models

Defaults are set in `soda_mmqc/config.py` and used when `--model` is omitted on the CLI:

| Provider | Default model |
|----------|---------------|
| OpenAI | `gpt-5-mini-2025-08-07` |
| Anthropic | `claude-opus-4-5-20251101` |

Pass any model ID your account supports, e.g. `evaluate fig-checklist --model gpt-5`. The CLI checks the name against models returned by the provider API (`get_compatible_models()`).

## Structured output

Each check’s `schema.json` defines the required JSON shape. Both providers enforce it; only the mechanism differs.

### OpenAI (Responses API)

Calls use `client.responses.create()` with the check schema passed as the `text` parameter (JSON-schema structured output). Optional `model_config.json` fields (`tools`, `reasoning`, etc.) are merged into the same request.

### Anthropic

The schema is converted to a `structured_output` tool. The API call sets `tool_choice` to force that tool; the parsed tool input becomes the response JSON.

`model_config.json` tool and reasoning options apply to **OpenAI only**. For Anthropic, the same file may still affect input preparation (e.g. source data attachments).

## Per-check model config (OpenAI)

Checks may include `model_config.json` beside `schema.json`. Values are passed through to `client.responses.create()` (`tools`, `tool_choice`, `max_tool_calls`, `include`, `reasoning`, `max_output_tokens`). If a check has no file, `soda_mmqc/data/model_config.json` supplies defaults (empty tools).

**Valid tool types** (Responses API): `web_search_preview`, `web_search_preview_2025_03_11`, `file_search`, `code_interpreter`, `function`, `mcp`, `image_generation`, `shell`, `computer_use_preview`, `apply_patch`, `custom`. Do **not** use `web_fetch` (unsupported; returns 400).

Minimal web-search example:

```json
{
  "tools": [{ "type": "web_search_preview" }],
  "tool_choice": "auto"
}
```

Agentic example (reasoning model + web search + code interpreter):

```json
{
  "tools": [
    { "type": "web_search_preview" },
    { "type": "code_interpreter", "container": { "type": "auto", "memory_limit": "4g" } }
  ],
  "tool_choice": "auto",
  "max_tool_calls": 20,
  "reasoning": { "effort": "medium" },
  "max_output_tokens": 16384
}
```

Use a reasoning-capable OpenAI model (e.g. `gpt-5`, `gpt-5-mini`, o-series) when setting `reasoning`. Multi-turn `conversation` / `previous_response_id` is not wired through the evaluate loop.

## Programmatic usage

`generate_response` routes to the configured provider:

```python
from soda_mmqc.lib.api import ModelInput
from soda_mmqc.lib.api import generate_response

model_input = ModelInput(
    example=example,
    prompt=prompt_text,
    schema=schema_dict,
)

response, metadata = generate_response(
    model_input,
    model="gpt-5-mini-2025-08-07",  # optional; uses DEFAULT_MODEL if omitted
    metadata={"doc_id": example.doc_id},
    model_config=model_config_dict,  # optional; from check's model_config.json
)
```

Returns `(parsed_json, metadata)` where `metadata` includes `response_id`, `model`, and token usage when available.
