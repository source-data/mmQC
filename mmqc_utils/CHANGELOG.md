# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

### Added
- `mmqc_utils.agentic` (optional extra `agentic`): the agentic harness developed in mmQC, so that applications run a checklist exactly as mmQC benchmarks it. Skills and their call graph, version pinning and model defaults, sealed runtime assembly from an `ExampleContent`, the session's permission profile, running a session (`run_session`) with its skill trace and tool audit, and rendering content for a provider. The extra pins `claude-agent-sdk==0.2.165` and adds `jsonschema` and `pyyaml`.

### Fixed
- `postprocess_html` (and so `document_to_html`, since 0.3.4) turned the doctype into the text `html` at the start of the document, and dropped the delimiters of HTML comments: `str()` of a BeautifulSoup doctype or comment is its bare content.

## [0.3.5] - 2026-06-12

### Added
- Exception handling for malformed tiff files. These fail with the Wand conversion. A `tifffile` fallback implemented, imagemagick is still the main image reader.

## [0.3.4] - 2026-06-11

### Added

- `html_cleanup` module and `postprocess_html` to clean common pandoc HTML artifacts (br-only placeholders, empty elements, `<li><p>` wrapping, duplicate URL paragraphs); wired into `document_to_html` post-processing.

Related to changes added in 0.3.2.

## [0.3.3] - 2026-06-10

### Added

- `document_to_html`: option to produce standalone HTML for easier readability, correct display of unicode symbols in browser.

## [0.3.2] - 2026-06-10

### Added
- `document_to_html`: option to strip certain empty HTML tags (`li`, `ol`, `ul`) from the output, default `True`. Handles case of empty list items in place of tracked change (deletion) in .docx files.

## [0.3.1] - 2026-06-08

### Added
- match multiple quotes from the same source text: order-aware quote alignment to prevent multiple quotes from matching to the same span in the source text, if that span is repeated later in the source.

## [0.3.0] - 2026-05-11

### Added
- quote matching in & similarity to source text: find the best matching span(s) in the source text for a quote and provide a score for how literal the quote is.
- visualization of quote matching.

### Changed
- use stdlib HTMLParser in `compute_plain_text` instead of regex solution.

## [0.2.1] - 2026-05-11

### Added
- make wand imports lazy to avoid unnecessary ImageMagick dependency for users who don't need image processing features.

## [0.2.0] - 2026-05-08

### Added
- type hinting support: added `py.typed` marker for PEP 561 compliance

## [0.1.0] - 2026-05-07

### Added
- `document_to_html`: convert DOCX, RTF, ODT, TeX, and PDF files to HTML via pandoc (bundled through `pypandoc-binary`); PDF falls back to `pypdf` page-by-page text extraction
- `convert_to_bounded_jpeg`: rasterize and downscale images (TIFF, JPEG, PNG, GIF, WebP, PDF) to a bounded JPEG preview via ImageMagick/Wand
- `compress_to_bounded_jpeg`: wrapper around `convert_to_bounded_jpeg` that steps down JPEG quality and then halves the pixel dimension until the output fits within a byte-size budget
- `html_to_text` / `compute_plain_text`: strip HTML tags and collapse whitespace to plain text
- All public functions accept `Path`, `str`, `bytes`, `bytearray`, or `BinaryIO` as input
