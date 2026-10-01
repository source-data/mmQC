#!/usr/bin/env python3
"""Launch the curation interface using streamlit."""

import sys
import os
from pathlib import Path
import argparse


def main(argv=None):
    # Set environment variables before importing streamlit
    os.environ["STREAMLIT_SERVER_RUN_ON_SAVE"] = "false"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"  # Disable file watching completely
    
    # Import streamlit after environment is configured
    import streamlit.web.cli as stcli
    
    # Get the path to the curation.py file
    workspace_root = Path(__file__).resolve().parent.parent
    curation_script = workspace_root / "core" / "curation.py"
    
    # Parse command line arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("checklist", type=str, help="Name of the checklist to curate")
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--langfuse",
        action="store_true",
        help="Fetch prompts from Langfuse instead of the local checklist files",
    )
    source.add_argument(
        "--local-prompts",
        action="store_true",
        help="Load prompts from the local checklist files (the default; kept for old habits)",
    )
    # `argv` is passed by `mmqc curate`; run directly, it falls back to the
    # process's own arguments.
    args = parser.parse_args(argv)

    # Local files are the default. `.env` carries Langfuse keys, and the app
    # loads `.env` itself, so keying the choice on whether those variables are
    # set made Langfuse the default on any machine with a `.env` -- and every
    # launch needed --local-prompts. The source is now asked for, not inferred.
    os.environ["SODA_MMQC_PROMPT_SOURCE"] = "langfuse" if args.langfuse else "local"
    
    # Prepare streamlit arguments
    sys.argv = [
        "streamlit",
        "run",
        str(curation_script),
        "--server.headless=true",
        "--server.address=localhost",
        "--server.port=8501",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        "--global.developmentMode=false",
        "--server.fileWatcherType=none",  # Disable file watching via CLI as well
        "--",  # This tells streamlit that the following arguments are for the script
        args.checklist  # Pass the checklist argument to the script
    ]
    
    # Run streamlit
    sys.exit(stcli.main())


if __name__ == "__main__":
    main() 