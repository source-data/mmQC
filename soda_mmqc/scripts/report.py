#!/usr/bin/env python3
"""Launch the evaluation reporting Streamlit app."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional, Sequence


def main(app_args: Optional[Sequence[str]] = None) -> None:
    """Run the app; ``app_args`` reach it after streamlit's ``--``.

    ``None`` forwards this process's own arguments, for the ``report``
    console script.
    """
    if app_args is None:
        app_args = sys.argv[1:]
    os.environ.setdefault("STREAMLIT_SERVER_RUN_ON_SAVE", "false")
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")

    import streamlit.web.cli as stcli

    app_script = (
        Path(__file__).resolve().parent.parent / "reporting" / "streamlit_app.py"
    )
    sys.argv = [
        "streamlit",
        "run",
        str(app_script),
        "--server.headless=true",
        "--server.address=localhost",
        "--server.port=8502",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        "--global.developmentMode=false",
        "--server.fileWatcherType=none",
    ]
    if app_args:
        sys.argv += ["--", *app_args]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
