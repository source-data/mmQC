from bs4 import BeautifulSoup

from mmqc_utils.html_cleanup import (
    is_br_only,
    is_empty_tag,
    postprocess_html,
    remove_br_only_elements,
    remove_empty_elements,
    remove_orphan_url_paragraphs,
    unwrap_li_paragraphs,
    visible_text,
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


# --- helpers ---


def test_visible_text_normalizes_whitespace() -> None:
    soup = _soup("<p>  Hello \n  <em>world</em>  </p>")
    paragraph = soup.find("p")
    assert paragraph is not None
    assert visible_text(paragraph) == "Hello world"


def test_is_br_only_detects_br_placeholders() -> None:
    soup = _soup("<p><br/> <br/></p><p>text<br/></p><p></p>")
    paragraphs = soup.find_all("p")
    assert is_br_only(paragraphs[0]) is True
    assert is_br_only(paragraphs[1]) is False
    assert is_br_only(paragraphs[2]) is False  # empty, not br-only


def test_is_empty_tag() -> None:
    soup = _soup("<p>   </p><p>text</p><p><br/></p>")
    paragraphs = soup.find_all("p")
    assert is_empty_tag(paragraphs[0]) is True
    assert is_empty_tag(paragraphs[1]) is False
    assert is_empty_tag(paragraphs[2]) is False  # br-only is not "empty"


# --- remove_br_only_elements ---


def test_remove_br_only_elements() -> None:
    soup = _soup("<p><br/></p><div><br/><br/></div><p>keep<br/></p>")

    removed = remove_br_only_elements(soup)

    assert removed == 2
    assert str(soup) == "<p>keep<br/></p>"


# --- remove_empty_elements ---


def test_remove_empty_elements() -> None:
    soup = _soup('<p></p><span>  </span><a href="#"></a><p>keep</p>')

    removed = remove_empty_elements(soup)

    assert removed == 3
    assert str(soup) == "<p>keep</p>"


def test_remove_empty_elements_preserves_td_th() -> None:
    html = "<table><tr><th></th><th>h</th></tr><tr><td></td><td>x</td></tr></table>"
    soup = _soup(html)

    removed = remove_empty_elements(soup)

    assert removed == 0
    assert len(soup.find_all("td")) == 2
    assert len(soup.find_all("th")) == 2


# --- unwrap_li_paragraphs ---


def test_unwrap_li_paragraphs() -> None:
    soup = _soup("<ul><li><p>one</p></li><li><p>a</p><p>b</p></li></ul>")

    count = unwrap_li_paragraphs(soup)

    assert count == 1
    items = soup.find_all("li")
    assert str(items[0]) == "<li>one</li>"
    assert items[1].find("p") is not None  # multi-paragraph li untouched


# --- remove_orphan_url_paragraphs ---


def test_remove_orphan_url_paragraph_when_url_in_context() -> None:
    html = "<p>See http://example.com/x for details.</p><p>http://example.com/x</p>"
    soup = _soup(html)

    removed = remove_orphan_url_paragraphs(soup)

    assert removed == 1
    assert len(soup.find_all("p")) == 1


def test_keep_orphan_url_paragraph_when_url_not_in_context() -> None:
    html = "<p>Unrelated text.</p><p>http://example.com/new</p>"
    soup = _soup(html)

    removed = remove_orphan_url_paragraphs(soup)

    assert removed == 0
    assert len(soup.find_all("p")) == 2


# --- pipeline ---


def test_postprocess_html_runs_all_steps() -> None:
    html = "<p><br/></p><span></span><ul><li><p>item</p></li></ul>"

    cleaned = postprocess_html(html)

    assert cleaned == "<ul><li>item</li></ul>"


def test_postprocess_html_handles_empty_input() -> None:
    assert postprocess_html("") == ""


def test_postprocess_html_keeps_doctype_and_comments() -> None:
    """Pandoc's standalone output starts with a doctype; it must not become the text ``html``."""
    html = "<!DOCTYPE html>\n<html><!-- generated --><body><p>text</p></body></html>"

    cleaned = postprocess_html(html)

    assert cleaned.startswith("<!DOCTYPE html>")
    assert "<!-- generated -->" in cleaned
    assert BeautifulSoup(cleaned, "html.parser").get_text().strip() == "text"
