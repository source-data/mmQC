# Changelog

All notable changes to this project will be documented here.

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
