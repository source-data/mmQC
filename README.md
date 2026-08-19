# mmQC


An open library of multimodal editorial AI skills for manuscript quality control.

## Installation

Requires **Python 3.12+**. Dependencies are managed in `pyproject.toml`. Use **uv** (recommended) or pip.

### With uv (recommended)

```bash
# Clone the repository
git clone https://github.com/source-data/mmQC.git
cd mmQC

# Install uv if needed: https://docs.astral.sh/uv/
# Then create venv and install dependencies (generates uv.lock)
uv sync

# Activate the environment for shell commands
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### With pip

```bash
# Clone the repository
git clone https://github.com/source-data/mmQC.git
cd mmQC

python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
```

For TIFF, PDF, and other non-JPEG/PNG figure inputs, install [ImageMagick](https://imagemagick.org/download/) on your system (see [mmqc-utils](mmqc_utils/README.md)).

## Configuration

### API Provider Setup

mmQC supports both OpenAI and Anthropic APIs with structured output capabilities. You need to configure your API provider before using the system.

Create a `.env` file in the project root:

```bash
# API Provider Configuration
API_PROVIDER=openai  # Choose: 'openai' or 'anthropic'

# OpenAI Configuration (required if API_PROVIDER=openai)
OPENAI_API_KEY=your_openai_api_key_here

# Anthropic Configuration (required if API_PROVIDER=anthropic)  
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional: Device configuration for ML operations
DEVICE=cpu  # Options: 'cpu', 'cuda', 'mps' (Apple Silicon). Use cpu if PyTorch crashes on import.
```

### Model configuration

Set `API_PROVIDER` and the matching API key as above, then pass a model name with `--model` on the CLI (or use the provider default). See [API Provider Documentation](soda_mmqc/docs/api_providers.md) for details.

### Langfuse Integration (Optional)

[Langfuse](https://langfuse.com) can be used for two purposes:

1. **Remote prompt management** — fetch prompts from Langfuse instead of local `.txt` files. Prompts are looked up using the key `checklists/{checklist_name}/{check_name}`.
2. **Tracing** — model calls are logged as Langfuse spans for observability.

If `LANGFUSE_PUBLIC_KEY` is not set, the system silently falls back to local prompt files and tracing is disabled.

Add the following to your `.env` file (or export as environment variables):

```bash
# Langfuse configuration (optional)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com  # omit to use the default Langfuse Cloud endpoint
```

Self-hosted Langfuse users should set `LANGFUSE_BASE_URL` to their own instance URL.

## Testing

```bash
source .venv/bin/activate
pytest
```

Tests live under `tests/`. Integration tests that call live APIs are skipped unless the matching API key is set (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`).

## Usage

After installation, you can use the following commands to benchmark checks or curate benchmarking examples:

```bash
# Run all checks in a checklist
evaluate CHECKLIST_NAME [--model MODEL_NAME] [--mock] [--no-cache]

# Run a specific check in a checklist
evaluate CHECKLIST_NAME --check CHECK_NAME [--model MODEL_NAME] [--mock] [--no-cache]

# Run multiple specific checks in a checklist
evaluate CHECKLIST_NAME --checks CHECK_NAME_1 CHECK_NAME_2 [--model MODEL_NAME]

# Initialize expected output files for a checklist
init CHECKLIST_NAME [--no-cache]

# Curate and manage checklists
curate CHECKLIST_NAME

# Interactive Layer 2 mean-score reporting (Streamlit)
report
```

Command line options:
- `--model`: Model name to use for API calls (provider must match `API_PROVIDER`)
- `--mock`: Use expected outputs as model outputs (no API calls)
- `--no-cache`: Disable caching of model outputs
- `--check`: Specify a particular check to run within a checklist
- `--checks`: Specify multiple checks to run within a checklist (space-separated)
- `--initialize`: Initialize expected output files (alternative to `init` command)
- `--sentence-transformer-model`: SentenceTransformer model to use for semantic similarity scoring
- `--prompt-version`: Prompt version to run; accepts a version id/index or one of `production`, `latest`
- `--config-from-version`: When `--prompt-version` is set, use that version's config instead of the production config
- `--config-source-check`: Use the prompt config from this check (and the selected `--prompt-version`) for all selected checks

**Note**: If no model is specified, the system automatically uses the default model for your configured API provider (see [Configuration](#configuration)).

## Checklists and checks

mmQC is an open library of multimodal editorial AI skills for manuscript quality control that are benchmarked against curated examples.

A **check** is a directory under `soda_mmqc/data/checklist/{checklist}/{check}/` that contains the following files:

- `prompts/` — prompt templates (compare versions with `--prompt-version`)
- `schema.json` — model structured output contract
- `eval-manifest.json` — scoring policy (see [Benchmarking and evaluation](soda_mmqc/docs/benchmarking.md))
- `model_config.json` *(optional)* — tools, reasoning, and related OpenAI options
- `benchmark.json` — which examples under `data/examples/` to include in the evaluation of the AI check

A **checklist** is a directory of related checks run together (`evaluate fig-checklist`). 

```text
soda_mmqc/data/checklist/
├── fig-checklist/
│   └── error-bars-defined/
│       ├── prompts/
│       │   └── prompt.1.txt
│       │   └── prompt.2.txt
│       │   └── ...                            # other prompt versions
│       ├── schema.json
│       ├── eval-manifest.json
│       ├── model_config.json   # optional
│       └── benchmark.json
│   └── micrograph-scale-bar/...
│   └── ...                                    # other checks in this checklist
└── ...                                        # other checklists
```

### Output schema

`schema.json` defines the structured format for model responses. SODA MMQC enforces it for both OpenAI (structured output) and Anthropic (tool calling).

```json
{
    "format": {
        "type": "json_schema",
        "name": "error-bars-defined",
        "schema": {
            "type": "object",
            "properties": {
                "outputs": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "panel_label": {
                                "type": "string",
                                "description": "Label of the panel (e.g., A, B, C)"
                            },
                            "error_bar_on_figure": {
                                "type": "string",
                                "enum": ["yes", "no"],
                                "description": "Whether error bars are present"
                            },
                            "error_bar_defined_in_caption": {
                                "type": "string",
                                "enum": ["yes", "no", "not needed"],
                                "description": "Whether error bars are defined in caption"
                            },
                            "from_the_caption": {
                                "type": "string",
                                "description": "Text from caption describing error bars, when error bars are present"
                            }
                        },
                        "required": [
                            "panel_label",
                            "error_bar_on_figure",
                            "error_bar_defined_in_caption",
                            "from_the_caption"
                        ],
                        "additionalProperties": false
                    }
                }
            },
            "required": ["outputs"],
            "additionalProperties": false
        },
        "strict": true
    }
}
```

### Model config (OpenAI, optional)

Per-check `model_config.json` enables tools (e.g. `web_search_preview`), reasoning (`reasoning: { "effort": "medium" }` for gpt-5/o-series), and the code interpreter for that check:

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

Use a reasoning-capable model (e.g. `gpt-5`, `gpt-5-mini`) when setting `reasoning`. Full options: [API Provider Documentation](soda_mmqc/docs/api_providers.md#per-check-model-config-openai).

## Benchmarking system

The benchmarking system:

- Evaluates how well models execute checks against curated gold labels
- Supports prompt comparison and policy refinement
- Documents expected outcomes on concrete examples

See **[Benchmarking and evaluation](soda_mmqc/docs/benchmarking.md)** for the scoring model, manifest reference, and reporting layers.

### End-to-end flow

```text
data/examples/…/document/content/figure/     curated gold + inputs (caption, image)
        │
        ▼
   model call (one per benchmark example; metadata.source identifies the path)
        │
        ▼
   predicted JSON  +  expected_output.json
        │
        ▼
   FlatEvaluator + eval-manifest.json  →  analysis.json (per prompt/model)
```

Each **benchmark example** is one document slice (for example a figure or a section of a document) under `data/examples/`. The runner loads the content of each slice (for example, figure image and caption), calls the model once, and stores the prediction. Evaluation compares prediction to gold and writes scored results under `data/evaluation/{checklist}/{check}/{model}/`.

### Example layout

```text
data/examples/{doc_id}/
├── content/
│   └── {figure_id}/
│       ├── content/
│           └── image.png
│           └── caption.txt
│       └── checks/
│           └── {check-name}/
│               └── expected_output.json  # curated gold labels for the check
└── checks/                               # document-level checks
    └── {check-name}/
        └── expected_output.json
```

Gold labels are curated per check in `expected_output.json`. Each check's `benchmark.json` selects which paths under `data/examples/` to run:

```json
{
  "name": "error-bars-defined",
  "example_class": "figure",
  "examples": [
    "10.1038_s44318-026-00715-1/content/1",
    "10.1038_s44319-025-00631-1/content/7"
  ]
}
```

### Scoring overview

Evaluation uses a **flat leaf model**: scoring happens at **leaf properties** only — primitive values (`string`, `number`, `boolean`, …) and **arrays of primitives**. Nested objects are containers; paths look like `outputs[].panel_label`.

`FlatEvaluator` compares each prediction to gold using `schema.json` (model contract) and `eval-manifest.json` (scoring rules). Results use three reporting layers:

| Layer | Question |
|-------|----------|
| **S** | Were rows in object lists (e.g. `outputs[]`) correctly paired within this example? |
| **1** | Were the non-applicable fields (out of scope) correctly omitted? |
| **2** | Did the applicable fields match gold? |

Comparison methods, manifest fields, match thresholds, and output structure are documented in **[Benchmarking and evaluation](soda_mmqc/docs/benchmarking.md)**. After editing `eval-manifest.json`, re-run `evaluate` (cached model outputs can be reused).

### Results and reporting

Scored runs are written to `data/evaluation/{checklist}/{check}/{model}/analysis.json`. Use `metadata.source` (not `doc_id` alone) to identify a specific figure when a paper has multiple benchmark examples.

The `soda_mmqc.reporting` package loads `analysis.json` and supports dashboards and drill-down across layers, models, and prompts. See `notebooks/comparative-reporting.ipynb` for comparative plots and instance inspection in Jupyter.

#### Interactive reporting (`report`)

After running `evaluate`, launch a local Streamlit app to explore **Layer 2 mean scores** and drill into individual instances:

```bash
source .venv/bin/activate
report
```

The app opens at [http://localhost:8502](http://localhost:8502). You can also run it directly:

```bash
streamlit run soda_mmqc/reporting/streamlit_app.py
```

**Prerequisites:** at least one `analysis.json` under `data/evaluation/{checklist}/{check}/{model}/`, and an `eval-manifest.json` for that check (checks without a manifest appear in the sidebar but cannot be loaded).

**What you can do:**

- **Select a check** from evaluation results discovered under `data/evaluation/`.
- **Contrast runs** by a single model/prompt pair, by prompt (fixed model), or by model (fixed prompt).
- **Inspect mean scores** per leaf field (applicable instances only): black bars show the mean; red dots are individual instances.
- **Click a red dot** to open instance drill-down: figure image (zoom/pan), caption, gold vs prediction at the scored path, and the prompt text.

#### Static fig-checklist snapshot (`export-fig-report`)

To freeze the current evaluation state as shareable HTML (mean-score charts per model, Layer overlays, winner lines, and score tables):

```bash
export-fig-report
export-fig-report --models gpt-5-mini-2025-08-07,gpt-5.4
export-fig-report --checks stat-significance-level,plot-gap-labeling --out reports/fig-checklist/demo
```

Open `reports/fig-checklist/<date>/index.html` in a browser. The report also includes `mean-scores.html` (check × model prompt-comparison boxplots) and `key-fields.html` (three curated role plots — binary / semantic / extraction — with box + scatter of instance scores by check). Interactive drill-down remains in the Streamlit app.

Programmatic use of the same plots and tables remains available via `soda_mmqc.reporting` and the comparative-reporting notebook.

