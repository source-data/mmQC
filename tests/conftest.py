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

import logging
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


@pytest.fixture(autouse=True)
def _propagate_package_logs():
    """Let `caplog` see this package's log records.

    `soda_mmqc/__init__.py` sets `logger.propagate = False` and installs its
    own handlers, so records never reach the root logger -- which is exactly
    where pytest's `caplog` attaches its own. Without this, `caplog.text` and
    `caplog.records` come back empty and a test asserting on an error message
    compares against "", which fails in a way that looks nothing like the
    cause. `capsys` does not see them either: the package's StreamHandler
    holds the `stderr` it captured at import, not the one pytest swaps in.

    Autouse, because the trap is silent and catches any test that asserts on
    a log message, not just the ones that hit it today.
    """
    package_logger = logging.getLogger("soda_mmqc")
    previous = package_logger.propagate
    package_logger.propagate = True
    try:
        yield
    finally:
        package_logger.propagate = previous
