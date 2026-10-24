# mmqc-utils

Reusable conversion utilities for MMQC projects.

## Included utilities

- Convert and downscale common image formats (TIFF, JPEG, PNG, GIF, WebP, PDF) to bounded JPEG previews, with optional byte-size budget enforcement
- Convert DOCX, RTF, ODT, TeX, and PDF documents to HTML
- Normalize HTML to plain text
- Align a quote against a source text and return character-level spans, score, and match status
- Align multiple quotes against a shared source with automatic resolution of duplicate-occurrence ambiguity
- Render HTML fragments visualizing a single alignment or multi-quote coverage of a shared source

## System requirements

- **ImageMagick** — required for image conversion (`convert_to_bounded_jpeg`). Install via your system package manager:
  ```bash
  # macOS
  brew install imagemagick

  # Debian / Ubuntu
  apt-get install imagemagick
  ```
- **Pandoc** — bundled automatically via `pypandoc-binary`; no separate installation needed.

## Installation

```bash
pip install mmqc-utils
# or
uv add mmqc-utils
```

## Usage

All functions accept a file path (`str` or `Path`), raw `bytes`/`bytearray`, or a `BinaryIO` object.

### Document conversion

```python
from mmqc_utils import document_to_html

# From a file path
html = document_to_html("paper.docx")

# From bytes — input_format is required when there is no file extension to infer from
html = document_to_html(raw_bytes, input_format="rtf")
```

Supported formats: `docx`, `rtf`, `odt`, `tex`, `pdf`.

For PDFs, pandoc is tried first; if it cannot convert the file, text is extracted page-by-page via `pypdf` and wrapped in `<div class='page'>` elements.

### Image conversion

```python
from mmqc_utils import convert_to_bounded_jpeg, compress_to_bounded_jpeg

# Downscale to pixel dimensions
jpeg_bytes = convert_to_bounded_jpeg(
    "figure.tiff",
    rasterization_dpi=150,   # DPI for vector/PDF rasterization
    max_dimension=2000,       # downscale if width or height exceeds this
    compression_quality=80,   # JPEG quality 1–100
    background="white",       # background when removing transparency
)

# Compress until the result fits within a byte-size budget
jpeg_bytes = compress_to_bounded_jpeg(
    "figure.tiff",
    max_bytes=5 * 1024 * 1024,  # 5 MB
    max_dimension=2000,
    compression_quality=80,
)
```

Both functions accept `Path`, `str`, `bytes`, `bytearray`, or `BinaryIO` as input and only render the first page/layer of multi-page TIFFs.

`compress_to_bounded_jpeg` steps down JPEG quality first (`80 → 70 → … → 30`), then halves `max_dimension` and repeats, until the result fits within `max_bytes`. If the budget cannot be met even at minimum quality and dimension, it returns the smallest result achieved.

### Text normalization

```python
from mmqc_utils import html_to_text, compute_plain_text

text = html_to_text("<p>Hello <b>world</b></p>")
# → "Hello world"
```

`compute_plain_text` is an alias for `html_to_text`. Block-level tags (`<p>`, `<div>`, `<br>`, headings, list items, …) are replaced by a space; inline tags are stripped; whitespace is collapsed.

### Quote matching

`align_quote` performs no normalization. Returned half-open character intervals index into exactly the `text` string passed by the caller. It tries four strategies in order, using the first that succeeds:

| Status | When | `char_intervals` | `score` |
|---|---|---|---|
| `MATCH_EXACT` | verbatim contiguous substring | set | `1.0` |
| `MATCH_GREATER` | all quote chars found across ordered source spans; source has extra text between them (`source_gaps`) | set | `1.0` |
| `MATCH_LESSER` | greedy match skipped some quote chars (`quote_gaps`) | set | matched chars / len(quote) |
| `MATCH_FUZZY` | RapidFuzz partial-ratio fallback | `None` | partial ratio / 100 |

For `MATCH_FUZZY` results above the confidence threshold, `approximate_char_intervals` (not `char_intervals`) is set.

**MATCH_EXACT** — verbatim substring:

```python
from mmqc_utils import align_quote, AlignmentStatus, CharInterval

text = "A Shows protein structure. B Shows binding site."
quote = "Shows protein structure."

alignment = align_quote(quote, text)
assert alignment.alignment_status is AlignmentStatus.MATCH_EXACT
assert alignment.score == 1.0
assert alignment.char_intervals == [CharInterval(2, 26)]
assert text[2:26] == quote
```

**MATCH_GREATER** — quote assembled from multiple non-contiguous source spans:

```python
text = (
    "(a-c) Line plots showing runtime across cell counts. "
    "Evaluations were performed on single-cell transcriptomic data (a), "
    "joint profiling of transcriptomic and chromatin accessibility data (b), "
    "and surface protein data (c)."
)
quote = (
    "Line plots showing runtime across cell counts. "
    "Evaluations were performed on joint profiling of transcriptomic and chromatin accessibility data"
)

alignment = align_quote(quote, text)
assert alignment.alignment_status is AlignmentStatus.MATCH_GREATER
assert alignment.score == 1.0
assert len(alignment.char_intervals) == 2          # two disjoint spans in source
assert alignment.source_gaps[0].text == "single-cell transcriptomic data (a), "
assert alignment.quote_gaps is None
```

`source_gaps` lists text present in `text` between matched spans but absent from the quote.

**MATCH_LESSER** — quote contains chars not present in source:

```python
text = "A Shows protein structure. B Shows binding site."
quote = "Shows protein structure.!"   # trailing "!" absent from source

alignment = align_quote(quote, text)
assert alignment.alignment_status is AlignmentStatus.MATCH_LESSER
assert alignment.char_intervals == [CharInterval(2, 26)]
assert 0.9 < alignment.score < 1.0
assert alignment.quote_gaps[0].text == "!"
assert alignment.source_gaps is None
```

`quote_gaps` lists text present in `quote` that was skipped to produce the literal match.

**MATCH_FUZZY** — approximate match (e.g. typo):

```python
text = "Prefix Alpha beta gamma delta epsilon suffix"
quote = "Alpha beta gamma delta epsylon"   # typo: "epsylon"

alignment = align_quote(quote, text)
assert alignment.alignment_status is AlignmentStatus.MATCH_FUZZY
assert alignment.char_intervals is None
assert alignment.approximate_char_intervals == [CharInterval(7, 37)]
assert text[7:37] == "Alpha beta gamma delta epsilon"
assert alignment.score > 0.9
```

`approximate_char_intervals` covers the best-matching region; exact boundaries may not be precise.

### Aligning multiple quotes against a shared source

When several quotes all target the same source text — for example, panel captions extracted from a figure caption — the same phrase can appear more than once in the source, causing `align_quote` to always return the first occurrence regardless of which one is correct for each panel.

`align_quotes` processes quotes in order and maintains a set of claimed spans. When a quote's alignment overlaps a span already claimed by an earlier quote, it retries the alignment starting from the end of the conflicting region. The retry result is used only if its score is at least as good as the original; otherwise the original is kept unchanged.

**Typical use case:** an LLM-extracted panel caption contains "Two-way ANOVA with multiple comparisons was performed", but the phrase appears twice in the figure caption — once in the panel A section and once in the panel E section. Panel A is quoted with a wider string that also contains the phrase, so after processing panel A first, `align_quotes` correctly directs panel E's alignment to the second occurrence.

```python
from mmqc_utils import align_quotes, AlignmentStatus

figure_caption = (
    "a) Tumor growth curves are shown. ... "
    "Two-way ANOVA with multiple comparisons was performed. "   # panel A region
    "... "
    "e) Two-way ANOVA with multiple comparisons was performed"  # panel E region
)

panel_a_quote = "Tumor growth curves are shown. ... Two-way ANOVA with multiple comparisons was performed."
panel_e_quote = "Two-way ANOVA with multiple comparisons was performed"

results = align_quotes([panel_a_quote, panel_e_quote], figure_caption)
a, e = results

# panel A claims a wide span that contains the first occurrence of the phrase
assert a.alignment_status is AlignmentStatus.MATCH_EXACT

# panel E is resolved to the second occurrence, not the first
assert e.char_intervals[0].start_pos > a.char_intervals[0].end_pos
```

The function also handles `MATCH_GREATER` results (multi-interval quotes): if any of a quote's intervals overlaps a claimed span, the retry uses `search_start` to skip past the claimed region and re-run the full greedy search from there.

Quotes should be passed in the natural reading order of the source so that earlier panels take priority on the first occurrence.

### Quote alignment visualization

Both functions return self-contained HTML fragments. The caller is responsible for providing the CSS classes they reference (listed below each function). Inputs must be plain text — use `compute_plain_text` to convert HTML before calling `align_quote` or either rendering function.

#### `render_alignment_view`

Shows a single `QuoteAlignment` as a two-row Quote / Source block. The quote row highlights unmatched quote chars; the source row highlights matched spans and source gaps with surrounding context.

```python
from mmqc_utils import align_quote, render_alignment_view, compute_plain_text

text  = compute_plain_text("<p>A Shows protein structure. B Shows binding site.</p>")
quote = compute_plain_text("<em>Shows protein structure.</em>")

alignment = align_quote(quote, text)
fragment  = render_alignment_view(quote, text, alignment)
# Returns a <div class="alignment-view"> with two rows:
#   Quote:  Shows protein structure.
#   Source: A [Shows protein structure.] B Shows binding site.
```

For `MATCH_LESSER` and `MATCH_FUZZY` the quote row marks unmatched chars and the source row marks the corresponding gaps, making the divergence immediately visible.

`context_chars` (default `200`) controls how many characters of plain context appear before and after matched spans in the source row. Increase it when the source is long and surrounding text matters.

Required CSS classes:

| Class | Used for |
|---|---|
| `mark.match` | matched spans in source and quote (fuzzy) |
| `mark.gap-q` | quote chars that could not be matched |
| `mark.gap-s` | source text between matched spans (not in quote) |
| `.alignment-view` | wrapper `<div>` |
| `.av-row` | each label + text row |
| `.av-label` | "Quote" / "Source" label |
| `.av-text` | the `<pre>` element |

#### `render_coverage_view`

Shows a shared source text with multiple alignments highlighted simultaneously — each alignment in a distinct color. Intended for cases where several quotes all target the same source, such as panel captions within a figure caption or figure captions within a manuscript's caption section.

```python
from mmqc_utils import align_quote, render_coverage_view

source = "(a) Shows protein structure. (b) Shows binding site. (c) Shows expression."
labeled = [
    ("panel-a", align_quote("Shows protein structure.", source)),
    ("panel-b", align_quote("Shows binding site.", source)),
    ("panel-c", align_quote("Shows expression.", source)),
]
fragment = render_coverage_view(source, labeled)
# Returns a <div class="coverage-view"> with a color legend above
# the source text; each panel's matched span is highlighted in its color.
```

Exact spans (`char_intervals`) are filled with the alignment's color. Approximate spans (`approximate_char_intervals`) are shown as a colored underline only, signalling lower positional confidence. All marks carry a `title` attribute — single-coverage marks show the alignment label; overlapping regions list all contributing labels.

A custom `palette` (list of CSS color strings) can be passed to override the built-in 8-color default.

```python
fragment = render_coverage_view(source, labeled, palette=["#c7d2fe", "#bbf7d0", "#fde68a"])
```

Required CSS classes:

| Class | Used for |
|---|---|
| `.coverage-view` | wrapper `<div>` |
| `.cov-legend` | legend row above the source |
| `.cov-chip` | each colored label chip in the legend |

## Development

### Releasing a New Version

To release a new version of `mmqc-utils` to PyPI:

1. **Update the version number** in `pyproject.toml`.
2. **Update the uv.lock file**:
   ```bash
   uv lock
   ```
3. **Update the changelog** in `CHANGELOG.md`.
4. **Build the distribution**:
   ```bash
   just build
   ```
5. **Check the distribution**:
   ```bash
   uv run --group publish twine check dist/*
   ```
6. **Upload to TestPyPI** (optional but recommended):
   ```bash
   uv run --group publish twine upload --repository testpypi dist/*
   ```
7. **Upload to PyPI**:
   ```bash
   uv run --group publish twine upload dist/*
   ```
