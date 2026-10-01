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
    parser.add_argument(
        "--local-prompts",
        action="store_true",
        help="Load prompts from local files only (disable Langfuse)",
    )
    # `argv` is passed by `mmqc curate`; run directly, it falls back to the
    # process's own arguments.
    args = parser.parse_args(argv)

    if args.local_prompts:
        # Empty values block load_dotenv() from re-loading Langfuse keys from .env
        os.environ["LANGFUSE_PUBLIC_KEY"] = ""
        os.environ["LANGFUSE_SECRET_KEY"] = ""
    
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