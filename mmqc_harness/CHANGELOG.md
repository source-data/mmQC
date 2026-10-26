# Changelog

All notable changes to this project will be documented here.

## [Unreleased]

### Added
- `orientation=` on `assemble_runtime` and `runtime_session`: a file copied verbatim as the runtime's `CLAUDE.md`, in place of the harness's mmQC template, for applications whose sessions do something else. A missing file, a directory or a symbolic link is refused. Without it, the runtime is as before.
- `RuntimeLayout.orientation_source` and `.orientation_sha256`; the audit (`tool_audit.json`) records both under `orientation`.
- `instruction=` on `assemble_runtime` and `runtime_session`: the text that opens the session's request, in place of mmQC's "Apply the `<entry>` check …". It is sent verbatim; an empty one is refused. `RuntimeLayout.instruction`, `.instruction_source` and `.instruction_sha256`; the audit records source and hash under `instruction`.

### Changed
- `session_cache_key` includes the SHA-256 of the runtime's `CLAUDE.md` and of the opening instruction. Keys computed before this change no longer match, including for runs on the default template.

## [0.1.0] - Unreleased

First version, separated from mmQC (`soda_mmqc.agentic`), where it was developed and benchmarked.

### Added
- Skills and their call graph (`skills`): reading versioned `SKILL.md` files, validating the graph their prose declares, call closure.
- Version pinning and model defaults (`pinning`): `version-manifest.yaml`, `model-defaults.yaml`, skill sets identified by a content digest.
- Sealed runtime assembly (`runtime`) from an `ExampleContent`, and the session's permission profile: one tool, `Skill`.
- Running a session (`session`): `run_session` returns the answer validated against the entry point's schema, the skill trace, and an audit of tool calls, cost and a fingerprint of every image sent.
- Rendering content for Anthropic and OpenAI (`render`); image parts name a file or carry their bytes.
- Figures as the model receives them (`content`): `figure_parts` / `figure_image_part` convert once with `mmqc_utils.convert_to_bounded_jpeg` (300 dpi, 2,048 px, JPEG 80).
- Publishing a production checklist to a prompt store and loading it back (`publication`), with the production rules; the `mmqc-skills` command (`pull`, `verify`, `status`).
- Documentation: `docs/guide.md`, `docs/soda-curation-integration.md`, and `examples/run_figure_checklist.py` (with `--mock`).
