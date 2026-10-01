"""`mmqc curate <checklist>` reaches the curation app with that checklist.

The subcommand used to take no arguments, so `mmqc curate fig-checklist` was
rejected by argparse, and the launcher read its checklist from the process's
own command line -- where it would have found `curate`.
"""

from __future__ import annotations

import sys
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


def test_local_prompts_empties_the_langfuse_keys(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    _launch(["curate", "fig-checklist", "--local-prompts"])
    import os
    assert os.environ["LANGFUSE_PUBLIC_KEY"] == ""


def test_a_checklist_is_required():
    with pytest.raises(SystemExit) as exit_:
        cli._build_parser().parse_args(["curate"])
    assert exit_.value.code == 2
