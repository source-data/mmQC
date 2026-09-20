"""What an example's content is, stated by the example and no one else."""

import pytest

from soda_mmqc.config import EXAMPLES_DIR
from soda_mmqc.core.examples import EXAMPLE_FACTORY

FIGURE_EXAMPLE = "10.1038_s44318-026-00715-1/content/1"

requires_figure_example = pytest.mark.skipif(
    not (EXAMPLES_DIR / FIGURE_EXAMPLE).is_dir(),
    reason=f"example store has no {FIGURE_EXAMPLE}",
)


@requires_figure_example
class TestFigureExampleStatesItsContent:
    def test_the_parts_are_the_caption_then_the_image(self):
        example = EXAMPLE_FACTORY.create(FIGURE_EXAMPLE, "figure")
        parts = example.input_parts()
        assert [part["kind"] for part in parts] == ["text", "image"]
        assert example.caption in parts[0]["text"]

    def test_the_image_part_names_a_file_under_content(self):
        example = EXAMPLE_FACTORY.create(FIGURE_EXAMPLE, "figure")
        image = next(p for p in example.input_parts() if p["kind"] == "image")
        content = example.source_path / "content"
        assert (content / image["path"]).is_file()
        assert image["path"] == example.image_path.name

    def test_no_part_carries_provider_vocabulary(self):
        """`Example` states content; drivers render it. Neither leaks."""
        example = EXAMPLE_FACTORY.create(FIGURE_EXAMPLE, "figure")
        for part in example.input_parts():
            assert set(part) <= {"kind", "text", "path"}
            assert part["kind"] in {"text", "image"}

    def test_supporting_files_are_the_source_data(self):
        example = EXAMPLE_FACTORY.create(FIGURE_EXAMPLE, "figure")
        supporting = example.supporting_files()
        assert set(supporting) == {"source_data"}
        content = example.source_path / "content"
        assert supporting["source_data"]
        for entry in supporting["source_data"]:
            assert entry.startswith("source_data/")
            assert (content / entry).is_file()

    def test_no_path_escapes_content(self):
        """A path climbing out of content/ would break the runtime's seal."""
        example = EXAMPLE_FACTORY.create(FIGURE_EXAMPLE, "figure")
        paths = [p["path"] for p in example.input_parts() if p["kind"] == "image"]
        paths += example.supporting_files()["source_data"]
        for entry in paths:
            assert not entry.startswith("/")
            assert ".." not in entry.split("/")


WORD_EXAMPLE = "10.1038_embor.2009.217"

requires_word_example = pytest.mark.skipif(
    not (EXAMPLES_DIR / WORD_EXAMPLE).is_dir(),
    reason=f"example store has no {WORD_EXAMPLE}",
)


@requires_word_example
class TestWordExampleStatesItsContent:
    def test_the_content_is_the_converted_html(self):
        example = EXAMPLE_FACTORY.create(WORD_EXAMPLE, "word")
        parts = example.input_parts()
        assert [part["kind"] for part in parts] == ["text"]
        assert parts[0]["text"] == example.content

    def test_the_conversion_is_never_written_to_disk(self):
        """A part is a message, not a file. The example store is unchanged."""
        example = EXAMPLE_FACTORY.create(WORD_EXAMPLE, "word")
        example.input_parts()
        content = example.source_path / "content"
        assert not list(content.glob("*.html"))

    def test_the_docx_is_offered_as_a_supporting_file(self):
        example = EXAMPLE_FACTORY.create(WORD_EXAMPLE, "word")
        supporting = example.supporting_files()
        assert supporting["manuscript"].endswith(".docx")
        content = example.source_path / "content"
        assert (content / supporting["manuscript"]).is_file()

    def test_nothing_here_assumes_an_image(self):
        example = EXAMPLE_FACTORY.create(WORD_EXAMPLE, "word")
        assert all(p["kind"] == "text" for p in example.input_parts())
