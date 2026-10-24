"""The agentic harness on a checklist built here, with no mmQC in sight.

An application will hand the harness its own checklist directory and its own
content; these tests do the same with a toy checklist:

    do-toy (entry point, owns schema.json)
      └── check-a (v1, v2: same edges, different prose; owns schema.json)
            └── shared (no schema)
    extra (shared, pinned, reached by nothing)

No session reaches the Agent SDK: `run_session` takes a client, and the tests
pass one that replays messages.
"""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

import pytest

from mmqc_utils.agentic import (
    ExampleContent,
    assemble_runtime,
    run_session,
    runtime_session,
    session_options,
)
from mmqc_utils.agentic.render import render_anthropic
from mmqc_utils.agentic.runtime import (
    AGENTIC_FORBIDDEN_TOOLS,
    AGENTIC_INPUT_MANIFEST_FILENAME,
    ASSEMBLY_ALL,
)

# Smallest valid PNG (1x1, transparent).
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYAAAAAYAAj"
    "CB0C8AAAAASUVORK5CYII="
)

SCHEMA = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": ["pass", "fail"]}},
    "required": ["verdict"],
    "additionalProperties": False,
}


def _skill(root: Path, name: str, version: str, *, requires=(), prose=""):
    calls = "".join(f"\nInvoke the `{r}` skill with the `Skill` tool.\n" for r in requires)
    text = (
        "---\n"
        f"name: {name}\n"
        f"description: {name}, described unambiguously.\n"
        f"requires: [{', '.join(repr(r) for r in requires)}]\n"
        "---\n\n"
        f"# {name}\n\n{prose or 'Do the thing.'}\n{calls}"
    )
    path = root / name / version / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _schema(root: Path, name: str):
    envelope = {"format": {"type": "json_schema", "name": name, "schema": SCHEMA}}
    (root / name / "schema.json").write_text(json.dumps(envelope), encoding="utf-8")


@pytest.fixture
def checklist(tmp_path) -> Path:
    root = tmp_path / "toy"
    _skill(root, "do-toy", "v1", requires=("check-a",))
    _schema(root, "do-toy")
    _skill(root, "check-a", "v1", requires=("shared",), prose="Look closely.")
    _skill(root, "check-a", "v2", requires=("shared",), prose="Look very closely.")
    _schema(root, "check-a")
    _skill(root, "shared", "v1")
    _skill(root, "extra", "v1")
    (root / "version-manifest.yaml").write_text(
        "checklist: toy\nskills:\n  do-toy: v1\n  check-a: v2\n  shared: v1\n  extra: v1\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def content(tmp_path) -> ExampleContent:
    source = tmp_path / "example"
    (source / "data").mkdir(parents=True)
    (source / "figure.png").write_bytes(PNG)
    (source / "data" / "table.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    return ExampleContent(
        source_root=source,
        parts=(
            {"kind": "text", "text": "Figure caption:\nA cell."},
            {"kind": "image", "path": "figure.png"},
        ),
        files={"source_data": ["data/table.csv"]},
        label="example-1",
    )


def _skills_in(layout) -> set:
    return {p.parent.name for p in layout.skills_root.glob("*/SKILL.md")}


# --- assembly ---------------------------------------------------------------


def test_the_closure_is_assembled_and_nothing_else(checklist, content, tmp_path):
    layout = assemble_runtime(checklist, "do-toy", content, root=tmp_path / "rt")
    assert _skills_in(layout) == {"do-toy", "check-a", "shared"}


def test_all_assembles_every_pinned_skill(checklist, content, tmp_path):
    layout = assemble_runtime(checklist, "do-toy", content, root=tmp_path / "rt", assembly=ASSEMBLY_ALL)
    assert _skills_in(layout) == {"do-toy", "check-a", "shared", "extra"}


def test_the_manifest_picks_the_prose(checklist, content, tmp_path):
    layout = assemble_runtime(checklist, "do-toy", content, root=tmp_path / "rt")
    assert "very closely" in (layout.skills_root / "check-a" / "SKILL.md").read_text()


def test_explicit_pins_override_the_manifest(checklist, content, tmp_path):
    pins = {"do-toy": "v1", "check-a": "v1", "shared": "v1", "extra": "v1"}
    layout = assemble_runtime(checklist, "do-toy", content, root=tmp_path / "rt", pins=pins)
    assert "very closely" not in (layout.skills_root / "check-a" / "SKILL.md").read_text()


def test_the_content_is_staged_and_named(checklist, content, tmp_path):
    layout = assemble_runtime(checklist, "do-toy", content, root=tmp_path / "rt")
    assert (layout.input_root / "figure.png").read_bytes() == PNG
    manifest = json.loads((layout.input_root / AGENTIC_INPUT_MANIFEST_FILENAME).read_text())
    assert manifest == {"source_data": ["input/data/table.csv"]}
    assert layout.input_parts[1] == {"kind": "image", "path": "input/figure.png"}
    assert layout.example == "example-1"


def test_a_fresh_runtime_goes_under_the_parent(checklist, content, tmp_path):
    parent = tmp_path / "runtimes"
    parent.mkdir()
    layout = assemble_runtime(checklist, "do-toy", content, parent=parent)
    assert layout.root.parent == parent


def test_an_entry_point_needs_a_schema(checklist, content, tmp_path):
    with pytest.raises(ValueError, match="schema.json"):
        assemble_runtime(checklist, "shared", content, root=tmp_path / "rt")


def test_an_unknown_entry_point_is_refused(checklist, content, tmp_path):
    with pytest.raises(ValueError, match="no SKILL.md"):
        assemble_runtime(checklist, "nope", content, root=tmp_path / "rt")


def test_a_missing_checklist_is_refused(tmp_path, content):
    with pytest.raises(FileNotFoundError):
        assemble_runtime(tmp_path / "nowhere", "do-toy", content, root=tmp_path / "rt")


def test_gold_in_the_content_is_refused_unless_excluded(checklist, content, tmp_path):
    (content.source_root / "checks").mkdir()
    (content.source_root / "checks" / "expected_output.json").write_text("{}", encoding="utf-8")
    root = tmp_path / "rt"
    with pytest.raises(ValueError, match="checks"):
        assemble_runtime(checklist, "do-toy", content, root=root)
    assert not root.exists(), "a refused assembly leaves nothing behind"

    excluded = ExampleContent(**{**vars(content), "exclude": ("checks",)})
    layout = assemble_runtime(checklist, "do-toy", excluded, root=root)
    assert not (layout.input_root / "checks").exists()


def test_the_runtime_session_removes_the_runtime(checklist, content, tmp_path):
    with runtime_session(checklist, "do-toy", content, root=tmp_path / "rt") as layout:
        assert layout.root.is_dir()
    assert not layout.root.exists()


# --- the permission profile -------------------------------------------------


def test_the_session_has_one_tool_and_no_way_out(checklist, content, tmp_path):
    layout = assemble_runtime(checklist, "do-toy", content, root=tmp_path / "rt")
    options = session_options(layout)
    assert options["tools"] == ["Skill"]
    assert options["allowed_tools"] == ["Skill"]
    assert options["permission_mode"] == "dontAsk"
    assert options["setting_sources"] == ["project"]
    assert {"Bash", "Agent", "WebFetch"} <= set(options["disallowed_tools"])
    assert set(options["disallowed_tools"]) == set(AGENTIC_FORBIDDEN_TOOLS)
    assert options["skills"] == sorted(_skills_in(layout))
    assert Path(options["env"]["CLAUDE_CONFIG_DIR"]).is_relative_to(layout.root)
    assert options["output_format"] == {"type": "json_schema", "schema": SCHEMA}


def test_the_content_renders_for_anthropic(checklist, content, tmp_path):
    layout = assemble_runtime(checklist, "do-toy", content, root=tmp_path / "rt")
    blocks = render_anthropic(layout.input_parts, layout.root)
    assert blocks[0] == {"type": "text", "text": "Figure caption:\nA cell."}
    assert blocks[1]["type"] == "image"
    assert base64.b64decode(blocks[1]["source"]["data"]) == PNG


# --- running a session ------------------------------------------------------


def _client(*messages):
    async def client(parts, options):
        for message in messages:
            yield message

    return client


def _skill_call(name, use_id):
    return {"content": [{"name": "Skill", "input": {"skill": name}, "id": use_id}]}


def test_a_session_returns_its_validated_answer_and_its_trace(checklist, content, tmp_path):
    layout = assemble_runtime(checklist, "do-toy", content, root=tmp_path / "rt")
    client = _client(
        _skill_call("check-a", "t1"),
        _skill_call("shared", "t2"),
        {"result": json.dumps({"verdict": "pass"})},
    )
    prediction, trace, audit = asyncio.run(run_session(layout, client=client))
    assert prediction == {"verdict": "pass"}
    assert trace.invoked == ["check-a", "shared"]
    assert json.loads((layout.artifacts_root / "prediction.json").read_text()) == prediction


def test_an_answer_outside_the_schema_is_refused(checklist, content, tmp_path):
    layout = assemble_runtime(checklist, "do-toy", content, root=tmp_path / "rt")
    client = _client({"result": json.dumps({"verdict": "maybe"})})
    with pytest.raises(ValueError):
        asyncio.run(run_session(layout, client=client))


def test_a_prose_answer_is_refused(checklist, content, tmp_path):
    layout = assemble_runtime(checklist, "do-toy", content, root=tmp_path / "rt")
    client = _client({"result": "I cannot answer within this schema."})
    with pytest.raises(ValueError, match="not JSON"):
        asyncio.run(run_session(layout, client=client))


# --- a figure as the model receives it --------------------------------------


@pytest.fixture
def large_figure(tmp_path) -> Path:
    """A PNG wider than the figure limit, so the builder has to downscale."""
    from PIL import Image

    path = tmp_path / "large.png"
    Image.new("RGB", (3000, 1200), "white").save(path)
    return path


def test_the_builder_converts_once(large_figure):
    """The bytes sent are `convert_to_bounded_jpeg`'s, not a re-encode of them."""
    from mmqc_utils import convert_to_bounded_jpeg
    from mmqc_utils.agentic import figure_image_part
    from mmqc_utils.agentic.content import (
        FIGURE_JPEG_QUALITY, FIGURE_MAX_DIMENSION, FIGURE_RASTERIZATION_DPI)

    part = figure_image_part(large_figure)
    once = convert_to_bounded_jpeg(
        large_figure, rasterization_dpi=FIGURE_RASTERIZATION_DPI,
        max_dimension=FIGURE_MAX_DIMENSION, compression_quality=FIGURE_JPEG_QUALITY)
    assert part == {"kind": "image", "media_type": "image/jpeg", "data": once}
    assert figure_image_part(large_figure)["data"] == once, "deterministic"


def test_the_builder_bounds_the_figure(large_figure):
    from PIL import Image
    import io

    from mmqc_utils.agentic import figure_parts

    caption, image = figure_parts(large_figure, "A wide figure.")
    assert caption == {"kind": "text", "text": "Figure caption:\nA wide figure."}
    with Image.open(io.BytesIO(image["data"])) as decoded:
        assert decoded.format == "JPEG"
        assert max(decoded.size) == 2048


def _inline(content: ExampleContent) -> ExampleContent:
    parts = (content.parts[0], {"kind": "image", "media_type": "image/png", "data": PNG})
    return ExampleContent(**{**vars(content), "parts": parts})


def test_an_image_carrying_its_bytes_is_sent_not_staged(checklist, content, tmp_path):
    (content.source_root / "figure.png").unlink()
    layout = assemble_runtime(checklist, "do-toy", _inline(content), root=tmp_path / "rt")
    assert layout.input_parts[1]["data"] == PNG
    assert not list(layout.input_root.glob("*.png")), "nothing derived is written in"
    block = render_anthropic(layout.input_parts, layout.root)[1]
    assert block["source"]["media_type"] == "image/png"
    assert base64.b64decode(block["source"]["data"]) == PNG


def test_an_image_part_names_a_file_or_carries_bytes_not_both(tmp_path):
    from mmqc_utils.agentic.render import image_bytes

    with pytest.raises(ValueError, match="exactly one"):
        image_bytes({"kind": "image", "path": "a.png", "data": PNG,
                     "media_type": "image/png"}, tmp_path)
    with pytest.raises(ValueError, match="exactly one"):
        image_bytes({"kind": "image"}, tmp_path)
    with pytest.raises(ValueError, match="media_type"):
        image_bytes({"kind": "image", "data": PNG}, tmp_path)


@pytest.mark.parametrize("inline", [False, True], ids=["staged", "inline"])
def test_the_session_records_what_the_model_was_shown(checklist, content, tmp_path, inline):
    import hashlib

    example = _inline(content) if inline else content
    layout = assemble_runtime(checklist, "do-toy", example, root=tmp_path / "rt")
    client = _client({"result": json.dumps({"verdict": "pass"})})
    _, _, audit = asyncio.run(run_session(layout, client=client))
    assert audit.inputs == [{
        "part": 1,
        "source": "inline" if inline else "input/figure.png",
        "media_type": "image/png",
        "bytes": len(PNG),
        "dimensions": [1, 1],
        "sha256": hashlib.sha256(PNG).hexdigest(),
    }]
    recorded = json.loads(audit.path.read_text(encoding="utf-8"))
    assert recorded["inputs"] == audit.inputs
