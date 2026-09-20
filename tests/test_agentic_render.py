"""Neutral parts in, one provider's vocabulary out. Nothing else knows both."""

import base64

import pytest

from soda_mmqc.agentic_render import render_anthropic, render_openai

# Arbitrary bytes behind a .png name: the renderer encodes what it is given
# and never decodes an image, so a real raster would test nothing extra.
PNG = b"\x89PNG\r\n\x1a\nnot-a-real-raster"


@pytest.fixture
def root(tmp_path):
    (tmp_path / "fig.png").write_bytes(PNG)
    return tmp_path


PARTS = [
    {"kind": "text", "text": "Figure caption:\nA and B."},
    {"kind": "image", "path": "fig.png"},
]


class TestAnthropicRendering:
    def test_text_becomes_a_text_block(self, root):
        blocks = render_anthropic(PARTS, root)
        assert blocks[0] == {"type": "text", "text": "Figure caption:\nA and B."}

    def test_image_becomes_a_base64_source_block(self, root):
        blocks = render_anthropic(PARTS, root)
        assert blocks[1]["type"] == "image"
        source = blocks[1]["source"]
        assert source["type"] == "base64"
        assert source["media_type"] == "image/png"
        assert base64.b64decode(source["data"]) == PNG


class TestOpenAIRendering:
    def test_text_becomes_a_text_part(self, root):
        parts = render_openai(PARTS, root)
        assert parts[0] == {"type": "text", "text": "Figure caption:\nA and B."}

    def test_image_becomes_a_data_uri(self, root):
        parts = render_openai(PARTS, root)
        assert parts[1]["type"] == "image_url"
        url = parts[1]["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")
        assert base64.b64decode(url.split(",", 1)[1]) == PNG


class TestRenderingRefusesWhatItCannotRender:
    def test_an_unknown_kind_is_an_error(self, root):
        with pytest.raises(ValueError, match="unknown part kind 'video'"):
            render_anthropic([{"kind": "video", "path": "x"}], root)

    def test_a_path_outside_the_root_is_refused(self, root):
        with pytest.raises(ValueError, match="outside"):
            render_openai([{"kind": "image", "path": "../escape.png"}], root)

    def test_a_named_file_that_is_absent_is_an_error(self, root):
        with pytest.raises(FileNotFoundError):
            render_openai([{"kind": "image", "path": "missing.png"}], root)
