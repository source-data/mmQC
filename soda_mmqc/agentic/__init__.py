"""mmQC's side of the agentic harness: the benchmark, the runs, the views.

The harness itself -- skills, pinning, runtime assembly, sessions, rendering
-- is :mod:`mmqc_utils.agentic`, which applications install too. What stays
here is mmQC's: the benchmark adapter (:mod:`.benchmark`), benchmark runs with
arms and replicates (:mod:`.runner`), the generated checklist views
(:mod:`.views`) and the research-only OpenAI driver (:mod:`.openai_driver`).

Deliberately empty of re-exports, so that an import line names the layer
being used.
"""
