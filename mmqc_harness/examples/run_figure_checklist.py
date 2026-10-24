#!/usr/bin/env python3
"""Run a published checklist on one figure: the whole path an application takes.

A reference, not a supported tool: an application makes these calls from its
own pipeline. It exists to show the exact sequence, runnably, and a test keeps
it working.

From the mmQC repository, on one of the benchmark's figures:

    uv run --env-file .env mmqc-skills pull fig-checklist --entry do-fig-checklist-pm --dest /tmp/skills
    F=soda_mmqc/data/examples/10.1038_s44318-026-00715-1/content/1/content
    uv run --env-file .env python mmqc_harness/examples/run_figure_checklist.py \
        --checklist-dir /tmp/skills/fig-checklist \
        --figure $F/44318_2026_715_Fig1_HTML.webp --caption-file $F/caption.txt --mock

Without --mock it runs a real session: about a minute, about $0.15.

In general:

    # Get the checklist (needs the `langfuse` extra and LANGFUSE_* variables):
    mmqc-skills pull fig-checklist --entry do-fig-checklist-pm --dest skills/

    # Run it on a figure (needs ANTHROPIC_API_KEY, and ImageMagick):
    python run_figure_checklist.py --checklist-dir skills/fig-checklist \\
        --figure figure-3.tif --caption-file figure-3.txt --out answer.json

    # The same path with no model call and no API key: a stand-in session
    # returns an empty, schema-valid answer.
    python run_figure_checklist.py --checklist-dir skills/fig-checklist \\
        --figure figure-3.tif --caption "Figure 3. ..." --mock

Steps, each a call an application makes:

1. verify the local checklist (offline: content hashes, production rules);
2. build the content: the caption, and the figure converted once as the
   benchmark converts it (`figure_parts`);
3. assemble a sealed runtime for the entry point, run one session in it, and
   remove it (`runtime_session`, `run_session`);
4. use the answer -- already validated against the entry point's schema --
   and the audit: skills invoked, turns, cost, and the fingerprint of the
   image sent.

The answer goes to --out (or stdout); a summary goes to stderr.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from mmqc_harness import (
    ExampleContent,
    effective_session_options,
    figure_parts,
    load_model_defaults,
    run_session,
    runtime_session,
    validate_skills,
)
from mmqc_harness.publication import verify_local_checklist


def mock_client(answer: dict):
    """A stand-in for the Agent SDK: one structured result, no model call."""

    async def client(parts, options):
        yield {"result": json.dumps(answer)}

    return client


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--checklist-dir", type=Path, required=True,
                        help="a checklist pulled with `mmqc-skills pull` (it holds release.json)")
    parser.add_argument("--figure", type=Path, required=True, help="the figure file: TIFF, PDF, EPS, PNG, JPEG, ...")
    caption = parser.add_mutually_exclusive_group(required=True)
    caption.add_argument("--caption")
    caption.add_argument("--caption-file", type=Path)
    parser.add_argument("--model", help="overrides the checklist's model-defaults.yaml")
    parser.add_argument("--runtime-parent", type=Path, default=Path(tempfile.gettempdir()),
                        help="where the throwaway runtime is created (default: the system temp directory)")
    parser.add_argument("--keep-runtime", action="store_true", help="keep the runtime, to inspect it")
    parser.add_argument("--out", type=Path, help="write the answer here (default: stdout)")
    parser.add_argument("--mock", action="store_true", help="no model call: a stand-in session answers")
    args = parser.parse_args(argv)

    # 1. The checklist, as pulled: verified offline before anything runs.
    try:
        record = verify_local_checklist(args.checklist_dir)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    entry = record["entry"]
    skills = validate_skills(args.checklist_dir)
    defaults = load_model_defaults(args.checklist_dir)

    # 2. The content. The runtime stages `source_root`; the figure itself
    #    travels in the request, so an empty directory is enough.
    caption_text = args.caption if args.caption is not None else args.caption_file.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as staged:
        content = ExampleContent(
            source_root=Path(staged),
            parts=figure_parts(args.figure, caption_text),
            files={},
            label=args.figure.name,
        )

        # 3. One sealed session.
        with runtime_session(args.checklist_dir, entry, content,
                             parent=args.runtime_parent, keep=args.keep_runtime) as layout:
            options = effective_session_options(layout, skills, defaults=defaults.session)
            options["model"] = args.model or defaults.model_for("claude-sdk")
            client = mock_client({"outputs": []}) if args.mock else None
            answer, trace, audit = asyncio.run(run_session(layout, options=options, client=client))
            if args.keep_runtime:
                print(f"runtime kept at {layout.root}", file=sys.stderr)

    # 4. The answer, and what the session did.
    text = json.dumps(answer, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    usage = audit.usage or {}
    image = audit.inputs[0] if audit.inputs else {}
    print(f"checklist {record['checklist']} release {record['release'][:12]}, entry {entry}, "
          f"model {options['model']}{' (mock)' if args.mock else ''}", file=sys.stderr)
    print(f"panels answered: {len(answer.get('outputs', []))}; skills invoked: {len(trace.invoked)} "
          f"({', '.join(dict.fromkeys(trace.invoked)) or 'none'})", file=sys.stderr)
    print(f"turns {usage.get('num_turns', '-')}, cost ${usage.get('total_cost_usd') or 0:.3f}; image sent: "
          f"{image.get('media_type')} {image.get('dimensions')} sha256 {str(image.get('sha256'))[:12]}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
