"""
Integration tests for the model API that perform real OpenAI API calls.

Run only when OPENAI_API_KEY is set; otherwise skipped.
Load .env before checking so that OPENAI_API_KEY from .env is available.
Run explicitly with: pytest tests/test_model_api_integration.py -v
"""
import os
import pytest

# .env is loaded by tests/conftest.py, before this module is imported, so the
# gate below does not depend on which test module happened to import first.
from tests.conftest import requires_key

# Skip entire module if openai is absent (avoids importing heavy deps).
pytest.importorskip("openai")

# These call OpenAI, so they are gated on OpenAI's key -- never on another
# provider's, which would skip a runnable test or run an unrunnable one.
skip_no_key = requires_key("OPENAI_API_KEY")


def _minimal_example():
    """Minimal example that returns simple text content for the Responses API."""

    class MinimalExample:
        def prepare_model_input(self, prompt):
            return {
                "content": [
                    {"type": "input_text", "text": prompt or "Reply with the word ok."}
                ]
            }

    return MinimalExample()


def _minimal_schema():
    """Minimal schema for a one-field JSON response (Responses API format).
    OpenAI requires additionalProperties: false for structured output.
    """
    return {
        "format": {
            "type": "json_schema",
            "name": "minimal_reply",
            "schema": {
                "type": "object",
                "properties": {"reply": {"type": "string"}},
                "required": ["reply"],
                "additionalProperties": False,
            },
        }
    }


@pytest.mark.integration
@skip_no_key
def test_openai_valid_tool_type_web_search_preview():
    """Real API call with valid tool type web_search_preview must not return 400."""
    from soda_mmqc.lib.api import generate_response_openai
    from soda_mmqc.config import DEFAULT_MODEL

    example = _minimal_example()
    schema = _minimal_schema()
    model_config = {
        "tools": [{"type": "web_search_preview"}],
        "tool_choice": "auto",
    }
    # Use a short prompt to minimize tokens; model may or may not use web search
    result, metadata = generate_response_openai(
        example=example,
        prompt="What is 2+2? Reply with a single number.",
        schema=schema,
        model=DEFAULT_MODEL,
        metadata={},
        model_config=model_config,
    )
    assert "reply" in result
    assert metadata.get("response_id")
    assert metadata.get("model")


@pytest.mark.integration
@skip_no_key
def test_openai_invalid_tool_type_web_fetch_returns_400():
    """Real API call with invalid tool type web_fetch must return 400."""
    from openai import APIError
    from soda_mmqc.lib.api import generate_response_openai
    from soda_mmqc.config import DEFAULT_MODEL

    example = _minimal_example()
    schema = _minimal_schema()
    model_config = {
        "tools": [{"type": "web_fetch"}],
        "tool_choice": "auto",
    }
    with pytest.raises(APIError) as exc_info:
        generate_response_openai(
            example=example,
            prompt="Hello",
            schema=schema,
            model=DEFAULT_MODEL,
            metadata={},
            model_config=model_config,
        )
    assert exc_info.value.status_code == 400
    assert "web_fetch" in str(exc_info.value).lower() or "invalid" in str(exc_info.value).lower()


@pytest.mark.integration
@skip_no_key
def test_openai_tool_type_web_search_alone():
    """Real API call with tool type web_search as sole tool.
    Same path as api.py: generate_response_openai -> client.responses.create,
    model=DEFAULT_MODEL, text=schema. The API may accept web_search when alone
    (current behavior) or return 400; we only assert no unexpected errors.
    Production configs use web_search_preview per API docs.
    """
    from openai import APIError
    from soda_mmqc.lib.api import generate_response_openai
    from soda_mmqc.config import DEFAULT_MODEL

    example = _minimal_example()
    schema = _minimal_schema()
    model_config = {
        "tools": [{"type": "web_search"}],
        "tool_choice": "auto",
    }
    try:
        result, metadata = generate_response_openai(
            example=example,
            prompt="Hello",
            schema=schema,
            model=DEFAULT_MODEL,
            metadata={},
            model_config=model_config,
        )
        assert metadata.get("model") == DEFAULT_MODEL or metadata.get("model")
        assert "reply" in result or result
    except APIError as e:
        if e.status_code == 400:
            assert "web_search" in str(e).lower() or "invalid" in str(e).lower()
        else:
            raise


@pytest.mark.integration
@skip_no_key
def test_openai_original_failing_config_web_search_and_web_fetch_returns_400():
    """Exact config that failed in production: [web_search, web_fetch].
    API must return 400 (web_fetch is unsupported; web_search is not valid either).
    Same endpoint and model as run_check: responses.create, DEFAULT_MODEL.
    """
    from openai import APIError
    from soda_mmqc.lib.api import generate_response_openai
    from soda_mmqc.config import DEFAULT_MODEL

    example = _minimal_example()
    schema = _minimal_schema()
    model_config = {
        "tools": [{"type": "web_search"}, {"type": "web_fetch"}],
        "tool_choice": "auto",
    }
    with pytest.raises(APIError) as exc_info:
        generate_response_openai(
            example=example,
            prompt="Hello",
            schema=schema,
            model=DEFAULT_MODEL,
            metadata={},
            model_config=model_config,
        )
    assert exc_info.value.status_code == 400
    # Error should mention at least one of the invalid tool types
    err_text = str(exc_info.value).lower()
    assert "web_fetch" in err_text or "web_search" in err_text or "invalid" in err_text
