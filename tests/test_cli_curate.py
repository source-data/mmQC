"""`mmqc curate <checklist>` reaches the curation app with that checklist.

The subcommand used to take no arguments, so `mmqc curate fig-checklist` was
rejected by argparse, and the launcher read its checklist from the process's
own command line -- where it would have found `curate`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

from soda_mmqc import cli


def _launch(argv):
    """Run the CLI with Streamlit stubbed out; return the argv it was given."""
    seen = {}

    def fake_streamlit_main():
        seen["argv"] = list(sys.argv)
        return 0

    with mock.patch("streamlit.web.cli.main", side_effect=fake_streamlit_main), \
            mock.patch.object(sys, "argv", ["mmqc", *argv]):
        with pytest.raises(SystemExit) as exit_:
            cli.main(argv)
    assert exit_.value.code == 0
    return seen["argv"]


def test_the_checklist_reaches_the_app():
    argv = _launch(["curate", "fig-checklist"])
    assert argv[argv.index("--") + 1:] == ["fig-checklist"]


def test_local_prompts_are_the_default(monkeypatch):
    """`.env` carries Langfuse keys; they must not make Langfuse the default."""
    monkeypatch.delenv("SODA_MMQC_PROMPT_SOURCE", raising=False)
    _launch(["curate", "fig-checklist"])
    assert os.environ["SODA_MMQC_PROMPT_SOURCE"] == "local"


def test_langfuse_is_asked_for(monkeypatch):
    monkeypatch.delenv("SODA_MMQC_PROMPT_SOURCE", raising=False)
    _launch(["curate", "fig-checklist", "--langfuse"])
    assert os.environ["SODA_MMQC_PROMPT_SOURCE"] == "langfuse"


def test_local_prompts_flag_still_accepted(monkeypatch):
    monkeypatch.delenv("SODA_MMQC_PROMPT_SOURCE", raising=False)
    _launch(["curate", "fig-checklist", "--local-prompts"])
    assert os.environ["SODA_MMQC_PROMPT_SOURCE"] == "local"


def test_the_two_sources_are_exclusive():
    with pytest.raises(SystemExit):
        cli._build_parser().parse_args(["curate", "fig-checklist", "--langfuse", "--local-prompts"])


CURATION_APP = Path(__file__).resolve().parents[1] / "soda_mmqc" / "core" / "curation.py"


def _run_app(monkeypatch, source):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("SODA_MMQC_PROMPT_SOURCE", source)
    # Empty, not absent: load_dotenv() does not override a variable that is set.
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")
    monkeypatch.setattr(sys, "argv", ["curation.py", "fig-checklist"])
    return AppTest.from_file(str(CURATION_APP), default_timeout=120).run()


def test_langfuse_without_keys_warns_in_red_and_falls_back(monkeypatch):
    app = _run_app(monkeypatch, "langfuse")
    assert not app.exception
    assert any("Langfuse was requested" in e.value for e in app.error)


def test_the_default_says_it_uses_local_files(monkeypatch):
    app = _run_app(monkeypatch, "local")
    assert not app.exception and not app.error
    assert any("local checklist files" in c.value for c in app.caption)


def test_a_checklist_is_required():
    with pytest.raises(SystemExit) as exit_:
        cli._build_parser().parse_args(["curate"])
    assert exit_.value.code == 2
