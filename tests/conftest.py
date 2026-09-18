"""Shared gating for tests that spend money on a real provider.

Two things make an ad-hoc gate unreliable, and both are handled here.

``load_dotenv()`` runs at import: ``soda_mmqc.config`` loads ``.env`` as a
side effect of being imported, so a gate that reads ``os.environ`` at import
time can see a key only because some *other* test module was imported first.
Loading it here makes the answer the same however the suite is invoked.

And a gate is per-provider. A test that calls Anthropic must not be gated on
``OPENAI_API_KEY``: with only one of the two keys present that either skips a
test that could have run, or runs one that cannot.
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()

# Placeholders a developer leaves in `.env` to remember the name of the
# variable. Treated as absent, because they fail at the provider, not here.
_PLACEHOLDERS = ("your_key_here", "your-key-here", "changeme", "")


def requires_key(name: str):
    """Skip the test unless ``name`` holds something usable.

    Returns a marker, so it decorates a test directly::

        @requires_key("ANTHROPIC_API_KEY")
        def test_something_live(): ...
    """
    value = (os.getenv(name) or "").strip()
    return pytest.mark.skipif(
        value.lower() in _PLACEHOLDERS,
        reason=f"{name} not set; live test skipped",
    )
