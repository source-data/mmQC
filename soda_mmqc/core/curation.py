import streamlit as st
import json
import yaml
from pathlib import Path
from PIL import Image
import pandas as pd
import argparse
from datetime import datetime
from soda_mmqc.config import (
    CHECKLIST_DIR,
    EXAMPLES_DIR,
    owns_evaluation_contracts,
)
from soda_mmqc import logger
from soda_mmqc.core.examples import EXAMPLE_FACTORY, WordExample
# Load environment variables from .env when available
import os
try:
    from dotenv import load_dotenv
    try:
        load_dotenv()
    except Exception:
        # ignore loading errors; env may already be set in the environment
        pass
except Exception:
    # python-dotenv not installed, rely on os.environ
    pass
# Optional Langfuse SDK integration for fetching prompts
try:
    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        # No public key configured; skip importing Langfuse entirely
        langfuse_client = None
    else:
        from langfuse import get_client as _get_langfuse_client
        try:
            langfuse_client = _get_langfuse_client()
        except Exception:
            langfuse_client = None
except Exception:
    langfuse_client = None

# Set page config for wider layout
st.set_page_config(
    page_title="SODA MMQC Example Visualizer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for smaller caption text
st.markdown("""
    <style>
    /* Override Streamlit's default styles with !important */
    div[data-testid="stMarkdown"] p {
        font-size: 0.8em !important;
    }
    </style>
    """, unsafe_allow_html=True)


def _extract_body_html(document_content):
    """Return inner HTML from a standalone document, or the original fragment."""
    if not document_content:
        return document_content

    lower = document_content.lower()
    body_tag_start = lower.find("<body")
    if body_tag_start == -1:
        return document_content

    content_start = document_content.find(">", body_tag_start)
    if content_start == -1:
        return document_content
    content_start += 1

    body_tag_end = lower.rfind("</body>")
    if body_tag_end == -1:
        return document_content[content_start:].strip()
    return document_content[content_start:body_tag_end].strip()


def get_workspace_root():
    """Get the workspace root directory."""
    current_dir = Path(__file__).resolve().parent
    return current_dir.parent.parent


def get_example_class(checklist):
    """Return example_class from the first check with benchmark metadata."""
    for check_data in checklist.values():
        benchmark = check_data.get("benchmark") or {}
        example_class = benchmark.get("example_class")
        if example_class:
            return example_class
    return "figure"


def get_document_examples(examples_dir, checklist):
    """List doc_id values for document-level curation."""
    benchmark_lists = [
        check_data.get("benchmark", {}).get("examples")
        for check_data in checklist.values()
        if "examples" in check_data.get("benchmark", {})
    ]

    if benchmark_lists:
        doc_ids = set()
        for examples in benchmark_lists:
            doc_ids.update(examples)
        return sorted(
            doc_id for doc_id in doc_ids
            if (examples_dir / doc_id).is_dir()
        )

    check_names = set(checklist.keys())
    discovered = []
    for doc_id_dir in sorted(examples_dir.glob("*")):
        if not doc_id_dir.is_dir():
            continue
        content_dir = doc_id_dir / "content"
        checks_dir = doc_id_dir / "checks"
        if not content_dir.exists() or not list(content_dir.glob("*.docx")):
            continue
        if checks_dir.exists() and any(
            (checks_dir / check_name).exists() for check_name in check_names
        ):
            discovered.append(doc_id_dir.name)
    return discovered


def get_word_docx_path(examples_dir, doc_id):
    """Return path to the single .docx for a document example.

    Raises:
        FileNotFoundError: Missing example dir, content/, or .docx
        ValueError: Multiple .docx files present
    """
    source_path = examples_dir / doc_id
    if not source_path.is_dir():
        raise FileNotFoundError(f"Example directory not found: {source_path}")

    content_path = source_path / "content"
    if not content_path.is_dir():
        raise FileNotFoundError(f"Content directory not found: {content_path}")

    word_files = sorted(content_path.glob("*.docx"))
    if not word_files:
        raise FileNotFoundError(
            f"No .docx file found in {content_path}. "
            "Exactly one .docx file is required."
        )
    if len(word_files) > 1:
        names = ", ".join(path.name for path in word_files)
        raise ValueError(
            f"Expected exactly one .docx in {content_path}, "
            f"found {len(word_files)}: {names}"
        )
    return word_files[0]


def word_example_cache_key(doc_id, docx_mtime):
    """Build session cache key for a loaded WordExample."""
    return f"{doc_id}:{docx_mtime}"


def load_cached_word_example(doc_id, examples_dir, cache):
    """Load WordExample from cache or convert docx; cache keyed by doc_id + mtime."""
    docx_path = get_word_docx_path(examples_dir, doc_id)
    cache_key = word_example_cache_key(doc_id, docx_path.stat().st_mtime)

    if cache_key not in cache:
        example = EXAMPLE_FACTORY.create(doc_id, "word")
        cache[cache_key] = example
        stale_keys = [
            key for key in cache
            if key.startswith(f"{doc_id}:") and key != cache_key
        ]
        for key in stale_keys:
            del cache[key]

    return cache[cache_key]


def _get_word_example_cache():
    if "word_example_cache" not in st.session_state:
        st.session_state.word_example_cache = {}
    return st.session_state.word_example_cache


def _load_check_outputs(example, checklist):
    """Load expected outputs for checks present in the checklist."""
    check_outputs = {}
    if checklist is None:
        return check_outputs

    for check_name in checklist.keys():
        try:
            check_outputs[check_name] = example.get_expected_output(check_name)
        except FileNotFoundError:
            st.warning(f"Expected output not found for {check_name}")
    return check_outputs


def load_example_data(
    relative_path,
    checklist=None,
    example_class="figure",
    examples_dir=None,
):
    """Load all relevant data for an example.

    Args:
        relative_path: Figure path (doc_id/content/fig_id) or doc_id for word examples
        checklist: Optional dictionary of valid checks
        example_class: "figure" or "word"
        examples_dir: Root examples directory (required for word caching)

    Returns:
        Dictionary containing example data, or None if loading fails
    """
    try:
        if isinstance(relative_path, Path):
            relative_path = str(relative_path)

        if example_class == "word":
            base_dir = examples_dir or EXAMPLES_DIR
            example = load_cached_word_example(
                relative_path,
                base_dir,
                _get_word_example_cache(),
            )
        else:
            example = EXAMPLE_FACTORY.create(relative_path, example_class)

        data = {
            "doc_id": example.doc_id,
            "example_class": example_class,
            "check_outputs": _load_check_outputs(example, checklist),
            "_example": example,
        }

        if example_class == "figure":
            data["figure_id"] = example.figure_id
            data["caption"] = example.caption
            data["image_path"] = (
                str(example.image_path) if example.image_path else None
            )
        else:
            data["document_content"] = example.content
            data["document_path"] = (
                str(example.word_file_path) if example.word_file_path else None
            )

        return data
    except FileNotFoundError as e:
        st.error(str(e))
        return None
    except ValueError as e:
        st.error(str(e))
        return None
    except Exception as e:
        st.error(f"Error loading example data: {e}")
        return None


def save_check_output(relative_path, check_name, output_data, example_class="figure"):
    """Save the updated check output.

    Args:
        relative_path: Figure path or doc_id for word examples
        check_name: Name of the check
        output_data: Dictionary containing the output data
        example_class: "figure" or "word"

    Returns:
        bool: True if save was successful, False otherwise
    """
    try:
        if isinstance(relative_path, Path):
            relative_path = str(relative_path)

        example = EXAMPLE_FACTORY.create(relative_path, example_class)
        example.save_expected_output(output_data, check_name, overwrite=True)
        return True
    except Exception as e:
        st.error(f"Error saving output: {e}")
        return False


def get_example_hierarchy(examples_dir):
    """Get the hierarchical structure of examples.
    
    Returns:
        Dictionary mapping doc_id to list of relative paths to figure directories.
        Example: {"doc_id": ["doc_id/content/1", "doc_id/content/2"]}
    """
    hierarchy = {}
    for doc_id_dir in examples_dir.glob("*"):
        if doc_id_dir.is_dir():
            hierarchy[doc_id_dir.name] = []
            # Look for content directory within each doc_id directory
            content_dir = doc_id_dir / "content"
            if content_dir.exists():
                # Find figure directories within content directory
                for fig_dir in content_dir.glob("*"):
                    if fig_dir.is_dir():
                        # Only include numeric figure directories (typical figure IDs)
                        if fig_dir.name.isdigit():
                            # Return relative path instead of absolute
                            relative_path = fig_dir.relative_to(examples_dir)
                            hierarchy[doc_id_dir.name].append(relative_path)
    return hierarchy


def _load_local_prompts(check_dir, prompts_dict):
    """Load prompt files from a check directory into prompts_dict."""
    prompt_txt = check_dir / "prompt.txt"
    prompts_dir = check_dir / "prompts"
    if prompt_txt.exists():
        try:
            with open(prompt_txt, "r", encoding="utf-8") as f:
                prompts_dict["prompt.txt"] = f.read()
        except Exception as e:
            logger.warning(f"Failed to load {prompt_txt}: {e}")
    elif prompts_dir.exists():
        for prompt_file in sorted(prompts_dir.glob("prompt*.txt")):
            try:
                with open(prompt_file, "r", encoding="utf-8") as f:
                    prompts_dict[prompt_file.name] = f.read()
            except Exception as e:
                logger.warning(f"Failed to load {prompt_file}: {e}")


def _load_json_file(path, label):
    """Load JSON from path; return None if missing, empty, or invalid."""
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            logger.warning("Empty %s at %s", label, path)
            return None
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning("Invalid %s at %s: %s", label, path, e)
        return None


def load_checklist(checklist_dir):
    """Load the checklist."""
    checklist = {}
    # load the whole checklist structure as a dictionary with the same structure as the checklist_dir
    # there is a schema.json file in this directory
    # and there is a benchmark.json file
    # then there is a prompts/ subdirectorie that includes several *.txt prompt files
    
    for check_dir in checklist_dir.glob("*"):
        if not check_dir.is_dir():
            continue

        # A directory is a check only if it owns the evaluation contracts.
        # Shared skills sit as flat siblings of the checks and carry at most a
        # runtime schema.json, so they are not curatable and must not appear
        # in the check selector. Same rule the runner enumerates by.
        if not owns_evaluation_contracts(check_dir):
            continue

        schema_path = check_dir / "schema.json"
        schema = _load_json_file(schema_path, "schema.json")
        if schema_path.exists() and schema is None:
            st.warning(
                f"Skipping check '{check_dir.name}': schema.json is empty or invalid"
            )
            continue

        benchmark_path = check_dir / "benchmark.json"
        benchmark = _load_json_file(benchmark_path, "benchmark.json")
        if benchmark_path.exists() and benchmark is None:
            st.warning(
                f"Skipping check '{check_dir.name}': benchmark.json is empty or invalid"
            )
            continue

        checklist[check_dir.name] = {
            "schema": schema or {},
            "benchmark": benchmark or {},
            "prompts": {},
        }

        if (
            schema
            and "format" in schema
            and "name" in schema["format"]
            and schema["format"]["name"] != check_dir.name
        ):
            schema_name = schema["format"]["name"]
            st.error(
                f"The name of the schema {schema_name} does not match "
                f"the name of the check {check_dir.name}"
            )

        if langfuse_client is None:
            _load_local_prompts(check_dir, checklist[check_dir.name]["prompts"])
        else:
            try:
                checklist_name = (
                    checklist_dir.name if hasattr(checklist_dir, "name") else str(checklist_dir)
                )
                prompt_key = f"checklists/{checklist_name}/{check_dir.name}"
                logger.info(f"Langfuse: fetching prompt for key={prompt_key}")
                prompt_text = langfuse_client.get_prompt(prompt_key)
                if prompt_text:
                    prompt_filename = f"{check_dir.name}.txt"
                    checklist[check_dir.name]["prompts"][prompt_filename] = prompt_text.name
                else:
                    _load_local_prompts(check_dir, checklist[check_dir.name]["prompts"])
            except Exception as e:
                logger.info(f"Langfuse prompt fetch skipped or failed for {check_dir.name}: {e}")
                try:
                    st.warning(f"Could not load prompts from Langfuse for {check_dir.name}: {e}")
                except Exception:
                    pass
                _load_local_prompts(check_dir, checklist[check_dir.name]["prompts"])
    return checklist
   

def serialize_value(value):
    """Serialize a value to a string representation."""
    if value is None:
        return None
    elif isinstance(value, str):
        return value
    elif isinstance(value, (list, tuple, dict)):
        return yaml.dump(value, default_flow_style=False, sort_keys=False, allow_unicode=True)
    else:
        return str(value)


def deserialize_value(value, schema):
    """Deserialize a value according to its schema type.
    
    Args:
        value: The value to deserialize
        schema: The JSON schema defining the value's type and structure
        
    Returns:
        The deserialized value. If value is None, returns an appropriate empty value
        based on the schema type (empty string for strings, empty list for arrays,
        empty dict for objects, None for other types).
    """
    if value is None:
        schema_type = schema.get("type")
        if schema_type == "string":
            return ""
        elif schema_type == "array":
            return []
        elif schema_type == "object":
            return {}
        else:
            return None  # For numbers, booleans, etc.
    
    schema_type = schema.get("type")
    
    if schema_type == "array":
        try:
            # Try to parse as YAML first
            if isinstance(value, str):
                parsed = yaml.safe_load(value)
            else:
                parsed = value
            if isinstance(parsed, list):
                # deserialize each item in the list
                parsed_list = [deserialize_value(item, schema["items"]) for item in parsed]
                return parsed_list
            return value
            # Otherwise try JSON as fallback
        except Exception as e:
            error_msg = f"{e.__class__.__name__} deserializing YAML string: {value}\n{e}"
            st.session_state.deserialization_errors.append(error_msg)
            logger.error(error_msg)
            return value
    elif schema_type == "object":
        try:
            # Try to parse as YAML first
            if isinstance(value, str):
                parsed = yaml.safe_load(value)
            else:
                parsed = value
            if isinstance(parsed, dict):
                # deserialize each item in the dictionary
                parsed_dict = {k: deserialize_value(parsed[k], schema["properties"][k]) for k in schema["required"]}
                return parsed_dict
            return value
        except Exception as e:
            error_msg = f"{e.__class__.__name__} deserializing YAML string: {value} with schema requiring: {schema['required']}"
            st.session_state.deserialization_errors.append(error_msg)
            logger.error(error_msg)
            return value
    elif schema_type == "string":
        return str(value)
    elif schema_type == "number":
        try:
            return float(value)
        except ValueError:
            return value
    elif schema_type == "integer":
        try:
            return int(value)
        except ValueError:
            return value
    elif schema_type == "boolean":
        if isinstance(value, str):
            return value.lower() == "true"
        return bool(value)
    else:
        # If no type specified or unknown type, try YAML first, then JSON
        try:
            return yaml.safe_load(value)
        except yaml.YAMLError:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value


def build_document_viewer_html(document_content):
    """Build iframe HTML for the document viewer with client-side search."""
    body_html = _extract_body_html(document_content)
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0;
    width: 100%;
    height: 100%;
    font-family: Georgia, "Times New Roman", serif;
    font-size: 14px;
    line-height: 1.5;
    color: #1a1a1a;
  }}
  #viewer {{
    width: 100%;
    height: 100%;
    min-height: 80vh;
    display: flex;
    flex-direction: column;
    border: 1px solid #ddd;
    border-radius: 4px;
    overflow: hidden;
  }}
  #doc-search-bar {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: #f8f9fa;
    border-bottom: 1px solid #ddd;
    flex-shrink: 0;
  }}
  #doc-search-input {{
    flex: 1;
    min-width: 0;
    padding: 6px 10px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font: 13px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }}
  #doc-search-count {{
    font: 12px/1 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    color: #666;
    white-space: nowrap;
    min-width: 72px;
    text-align: center;
  }}
  .doc-search-btn {{
    padding: 5px 10px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background: #fff;
    cursor: pointer;
    font: 13px/1 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }}
  .doc-search-btn:hover {{ background: #eef2f6; }}
  #doc-content {{
    flex: 1;
    overflow: auto;
    padding: 20px 28px 28px;
    width: 100%;
    max-width: none;
    font-size: 15px;
    line-height: 1.6;
  }}
  #doc-content > * {{
    max-width: none !important;
  }}
  #doc-content h1, #doc-content h2, #doc-content h3 {{
    font-family: Georgia, "Times New Roman", serif;
    line-height: 1.25;
    margin: 1.2em 0 0.5em;
    color: #111;
  }}
  #doc-content h1 {{ font-size: 1.45em; }}
  #doc-content h2 {{ font-size: 1.25em; }}
  #doc-content h3 {{ font-size: 1.1em; }}
  #doc-content p {{
    margin: 0.65em 0;
  }}
  #doc-content table {{
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 0.92em;
  }}
  #doc-content th, #doc-content td {{
    border: 1px solid #d0d7de;
    padding: 6px 10px;
    vertical-align: top;
  }}
  #doc-content th {{
    background: #f6f8fa;
    font-weight: 600;
  }}
  #doc-content ul, #doc-content ol {{
    margin: 0.65em 0;
    padding-left: 1.5em;
  }}
  #doc-content blockquote {{
    margin: 1em 0;
    padding: 0.5em 1em;
    border-left: 3px solid #d0d7de;
    color: #444;
  }}
  #doc-content a {{
    color: #0b57d0;
    text-decoration: underline;
    text-underline-offset: 2px;
    word-break: break-word;
  }}
  #doc-content a:hover {{
    color: #0842a0;
  }}
  mark.doc-search-hit {{
    background: #fff176;
    padding: 0 1px;
    border-radius: 2px;
  }}
  mark.doc-search-current {{
    background: #ffb74d;
    outline: 2px solid #e65100;
  }}
</style>
</head>
<body>
<div id="viewer">
  <div id="doc-search-bar">
    <input id="doc-search-input" type="search" placeholder="Search document..." autocomplete="off">
    <span id="doc-search-count"></span>
    <button type="button" class="doc-search-btn" id="doc-search-prev" title="Previous match (Shift+Enter)">↑</button>
    <button type="button" class="doc-search-btn" id="doc-search-next" title="Next match (Enter)">↓</button>
  </div>
  <div id="doc-content">{body_html}</div>
</div>
<script>
(function () {{
  const input = document.getElementById("doc-search-input");
  const countEl = document.getElementById("doc-search-count");
  const prevBtn = document.getElementById("doc-search-prev");
  const nextBtn = document.getElementById("doc-search-next");
  const root = document.getElementById("doc-content");
  let hits = [];
  let currentIndex = -1;
  let debounceTimer = null;

  function configureLinks() {{
    root.querySelectorAll("a[href]").forEach(function (link) {{
      link.setAttribute("target", "_blank");
      link.setAttribute("rel", "noopener noreferrer");
    }});
  }}

  configureLinks();

  function escapeRegex(value) {{
    return value.replace(/[.*+?^${{}}()|[\\]\\\\]/g, "\\\\$&");
  }}

  function updateCount(total, index) {{
    if (!total) {{
      countEl.textContent = input.value.trim() ? "0 matches" : "";
      return;
    }}
    countEl.textContent = (index + 1) + " / " + total;
  }}

  function clearHighlights() {{
    root.querySelectorAll("mark.doc-search-hit").forEach(function (mark) {{
      const parent = mark.parentNode;
      parent.replaceChild(document.createTextNode(mark.textContent), mark);
      parent.normalize();
    }});
    hits = [];
    currentIndex = -1;
  }}

  function setCurrent(index) {{
    hits.forEach(function (hit) {{ hit.classList.remove("doc-search-current"); }});
    if (index < 0 || index >= hits.length) {{
      updateCount(hits.length, -1);
      return;
    }}
    currentIndex = index;
    hits[currentIndex].classList.add("doc-search-current");
    hits[currentIndex].scrollIntoView({{ block: "center", behavior: "smooth" }});
    updateCount(hits.length, currentIndex);
  }}

  function highlight(term) {{
    clearHighlights();
    const trimmed = term.trim();
    if (!trimmed) {{
      updateCount(0, -1);
      return;
    }}

    const regex = new RegExp(escapeRegex(trimmed), "gi");
    const walker = document.createTreeWalker(
      root,
      NodeFilter.SHOW_TEXT,
      {{
        acceptNode: function (node) {{
          if (node.parentElement && node.parentElement.closest("mark.doc-search-hit")) {{
            return NodeFilter.FILTER_REJECT;
          }}
          return NodeFilter.FILTER_ACCEPT;
        }},
      }}
    );

    const textNodes = [];
    while (walker.nextNode()) {{
      textNodes.push(walker.currentNode);
    }}

    textNodes.forEach(function (node) {{
      const text = node.nodeValue;
      if (!regex.test(text)) {{
        regex.lastIndex = 0;
        return;
      }}
      regex.lastIndex = 0;

      const fragment = document.createDocumentFragment();
      let lastIndex = 0;
      let match;
      while ((match = regex.exec(text)) !== null) {{
        if (match.index > lastIndex) {{
          fragment.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
        }}
        const mark = document.createElement("mark");
        mark.className = "doc-search-hit";
        mark.textContent = match[0];
        fragment.appendChild(mark);
        lastIndex = regex.lastIndex;
      }}
      if (lastIndex < text.length) {{
        fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
      }}
      node.parentNode.replaceChild(fragment, node);
    }});

    hits = Array.from(root.querySelectorAll("mark.doc-search-hit"));
    if (hits.length) {{
      setCurrent(0);
    }} else {{
      updateCount(0, -1);
    }}
  }}

  function runSearch() {{
    highlight(input.value);
  }}

  function step(delta) {{
    if (!hits.length) {{
      runSearch();
      return;
    }}
    const nextIndex = (currentIndex + delta + hits.length) % hits.length;
    setCurrent(nextIndex);
  }}

  input.addEventListener("input", function () {{
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(runSearch, 200);
  }});

  input.addEventListener("keydown", function (event) {{
    if (event.key === "Enter") {{
      event.preventDefault();
      if (event.shiftKey) {{
        step(-1);
      }} else {{
        step(1);
      }}
    }}
  }});

  prevBtn.addEventListener("click", function () {{ step(-1); }});
  nextBtn.addEventListener("click", function () {{ step(1); }});
}})();
</script>
</body>
</html>"""


def render_document_viewer(document_content):
    """Render manuscript HTML from WordExample.content."""
    st.header("Document")
    if not document_content:
        st.info("No document content available")
        return

    st.html(
        build_document_viewer_html(document_content),
        width="stretch",
        unsafe_allow_javascript=True,
    )


def render_expected_output_panel(
    example_data,
    checklist,
    checklist_name,
    selected_source,
    example_class,
):
    """Render check selector, prompt, editable output table, and save controls."""
    st.header("Expected Output")
    if not example_data["check_outputs"]:
        st.info("No check outputs available for this example")
        return

    selected_check = st.selectbox(
        "Select Check",
        list(example_data["check_outputs"].keys()),
        help=f"Select one of the checks from {checklist_name}",
    )
    if not selected_check:
        return

    prompts = checklist[selected_check]["prompts"]
    first_prompt = None
    if prompts:
        first_prompt = list(prompts.values())[0]
        with st.expander("Prompt"):
            st.code(first_prompt, language="text", wrap_lines=True)
    else:
        st.warning(f"No prompts available for check '{selected_check}'")

    if example_class == "word" and first_prompt:
        example = example_data.get("_example")
        if isinstance(example, WordExample):
            full_input = example.prepare_model_input(first_prompt)
            with st.expander("Full model input"):
                st.code(
                    full_input["content"][0]["text"],
                    language="text",
                    wrap_lines=True,
                )

    output_data = example_data["check_outputs"][selected_check]
    if "outputs" not in output_data:
        return

    if selected_check not in checklist:
        st.error(f"Check {selected_check} not found in checklist")
        return

    schema_format = checklist[selected_check]["schema"]["format"]
    schema = schema_format["schema"]
    schema_props = schema["properties"]["outputs"]
    schema_path = schema_props["items"]["properties"]

    processed_outputs = []
    for item in output_data["outputs"]:
        processed_item = item.copy()
        for key, value in processed_item.items():
            if key in schema_path:
                processed_item[key] = serialize_value(value)
        if not all(value is None for value in processed_item.values()):
            processed_outputs.append(processed_item)

    df = pd.DataFrame(processed_outputs)
    edited_df = st.data_editor(df, num_rows="dynamic", height=300)

    file_key = f"{selected_source}_{selected_check}"

    has_been_saved = file_key in st.session_state.saved_files
    if "updated_at" not in output_data and not has_been_saved:
        st.error("This annotation file has never been checked!")
    else:
        st.success(f"Last saved on {output_data['updated_at']}")

    if st.session_state.deserialization_errors:
        for error in st.session_state.deserialization_errors:
            st.error(error)
        st.session_state.deserialization_errors = []

    if st.button(f"Save changes for {selected_check}"):
        st.session_state.deserialization_errors = []

        processed_records = []
        for _, row in edited_df.iterrows():
            processed_record = row.to_dict()
            for key, value in processed_record.items():
                if key in schema_path:
                    processed_record[key] = deserialize_value(
                        value,
                        schema_path[key],
                    )
            processed_records.append(processed_record)

        output_data["outputs"] = processed_records
        output_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if save_check_output(
            selected_source,
            selected_check,
            output_data,
            example_class=example_class,
        ):
            st.session_state.saved_files[file_key] = True
            st.rerun()


def render_figure_curation(
    checklist,
    checklist_name,
    examples_dir,
    example_hierarchy,
):
    """Render figure-level curation UI."""
    col_select_doc_id, col_select_fig, _ = st.columns([0.2, 0.2, 0.6])

    with col_select_doc_id:
        selected_doc_id = st.selectbox(
            "Select Paper",
            list(example_hierarchy.keys()),
            help="Select the paper to curate",
        )

    if not selected_doc_id:
        return

    with col_select_fig:
        selected_fig = st.selectbox(
            "Select Figure",
            example_hierarchy[selected_doc_id],
            format_func=lambda x: x.name if hasattr(x, "name") else x.split("/")[-1],
            help="Select the figure to curate",
        )

    if not selected_fig:
        return

    example_data = load_example_data(
        selected_fig,
        checklist,
        example_class="figure",
    )
    if not example_data:
        return

    col1, col2, col3 = st.columns([1, 0.7, 1.3])

    with col1:
        st.header("Figure")
        if example_data["image_path"]:
            try:
                image = Image.open(example_data["image_path"])
                st.image(image)
            except Exception as e:
                st.error(f"Error displaying image: {e}")
        else:
            st.info("No image available")

    with col2:
        st.header("Caption")
        st.markdown(example_data["caption"])

    with col3:
        render_expected_output_panel(
            example_data,
            checklist,
            checklist_name,
            selected_fig,
            example_class="figure",
        )


def render_document_curation(checklist, checklist_name, examples_dir):
    """Render document-level curation UI."""
    document_examples = get_document_examples(examples_dir, checklist)
    if not document_examples:
        has_benchmark_lists = any(
            "examples" in check_data.get("benchmark", {})
            for check_data in checklist.values()
        )
        if has_benchmark_lists:
            st.warning(
                "No benchmark examples found on disk. "
                "Check that benchmark.json `examples` paths exist under EXAMPLES_DIR."
            )
        else:
            st.warning("No document examples found")
        return

    col_select_doc_id, _ = st.columns([0.3, 0.7])
    with col_select_doc_id:
        selected_doc_id = st.selectbox(
            "Select Paper",
            document_examples,
            help="Select the manuscript to curate",
        )

    if not selected_doc_id:
        return

    try:
        docx_path = get_word_docx_path(examples_dir, selected_doc_id)
    except FileNotFoundError as e:
        st.error(str(e))
        return
    except ValueError as e:
        st.error(str(e))
        return

    with st.spinner(f"Loading {docx_path.name}..."):
        example_data = load_example_data(
            selected_doc_id,
            checklist,
            example_class="word",
            examples_dir=examples_dir,
        )
    if not example_data:
        return

    if not example_data.get("document_content"):
        st.error(
            f"Document conversion produced no content for {selected_doc_id}. "
            "Check the .docx file and conversion logs."
        )
        return

    col_doc, col_output = st.columns([2, 3], gap="medium")

    with col_doc:
        render_document_viewer(example_data["document_content"])

    with col_output:
        render_expected_output_panel(
            example_data,
            checklist,
            checklist_name,
            selected_doc_id,
            example_class="word",
        )


def main(checklist_name):
    checklist_dir = CHECKLIST_DIR / checklist_name
    checklist = load_checklist(checklist_dir)
    example_class = get_example_class(checklist)

    if example_class == "word":
        st.title("mmQC Benchmark Curation — Documents")
    else:
        st.title("mmQC Benchmark Curation — Figures")

    if "saved_files" not in st.session_state:
        st.session_state.saved_files = {}
    if "deserialization_errors" not in st.session_state:
        st.session_state.deserialization_errors = []

    st.subheader(checklist_name)

    examples_dir = EXAMPLES_DIR
    if not examples_dir.exists():
        st.error(f"Examples directory not found at {examples_dir}")
        return

    if example_class == "word":
        render_document_curation(checklist, checklist_name, examples_dir)
        return

    example_hierarchy = get_example_hierarchy(examples_dir)
    if not example_hierarchy:
        st.warning("No example directories found")
        return

    render_figure_curation(
        checklist,
        checklist_name,
        examples_dir,
        example_hierarchy,
    )


if __name__ == "__main__":
    # takes a command line argument for the checklist file
    # use argparse to parse the command line argument
    parser = argparse.ArgumentParser()
    parser.add_argument("checklist", type=str, help="Name of the checklist to curate.")
    args = parser.parse_args()
    main(args.checklist)