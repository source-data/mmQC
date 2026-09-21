import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from tqdm import tqdm
from soda_mmqc.lib.api import generate_response
from soda_mmqc.lib.cache import ModelCache
from soda_mmqc.config import (
    CHECKLIST_DIR,
    CACHE_DIR,
    EVALUATION_DIR,
    DEFAULT_SENTENCE_TRANSFORMER_MODEL,
    DEFAULT_MODEL,
    API_PROVIDER,
    DEFAULT_MODEL_CONFIG_PATH,
    EVALUATION_CONTRACT_FILES,
    owns_evaluation_contracts,
)
from soda_mmqc.lib.api import validate_model_for_provider, get_compatible_models
from soda_mmqc import logger
from soda_mmqc.core.eval_manifest import load_eval_manifest
from soda_mmqc.core.evaluation import FlatEvaluator
from soda_mmqc.core.examples import EXAMPLE_FACTORY, Example
from soda_mmqc.core.leaves import _default_semantic_embedder
from soda_mmqc.core.scoring import (
    ModelResult,
    analyze_results,
    save_analysis,
)
# Load env vars and initialize Langfuse client for prompt fetching
try:
    from dotenv import load_dotenv
    try:
        load_dotenv()
    except Exception:
        pass
except Exception:
    pass

# Optional Langfuse SDK integration for fetching prompts
try:
    if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
        # No Langfuse configuration present; operate as a no-op.
        langfuse_client = None
    else:
        from langfuse import get_client as _get_langfuse_client
        try:
            langfuse_client = _get_langfuse_client()
        except Exception:
            langfuse_client = None
except Exception:
    langfuse_client = None


@dataclass
class CheckData:
    """Container for all data needed to process a single check.
    
    This dataclass holds the essential information required to run a check
    against a set of examples, including the schema, examples, and metadata.
    
    Attributes:
        check_dir_name: Directory name of the check (e.g., 
            "error-bars-defined")
        check_name: Human-readable name of the check (e.g., 
            "Error Bars Defined")
        schema: JSON schema defining the expected output structure
        examples: List of Example instances
        expected_outputs: List of expected outputs for each example
        model_config: API options (e.g. tools, tool_choice). From check's
            model_config.json if present, else default model_config.json.
    """
    check_dir_name: str
    check_name: str
    schema: Dict[str, Any]
    examples: List[Example]
    expected_outputs: List[Dict[str, Any]]
    model_config: Dict[str, Any]


@dataclass
class ModelInput:
    """Container for model input data.
    
    Holds all the data needed to generate a response from the model,
    including the example, prompt, and expected output schema.
    
    Attributes:
        example: The Example instance containing image and caption data
        prompt: The prompt template to send to the model
        schema: JSON schema defining the expected structured output format
    """
    example: Example
    prompt: str
    schema: Dict[str, Any]
    # Full prompt key/name used for tracing and disambiguation, e.g.
    # "checklists/fig-checklist/panel-data-replication-validation".
    prompt_name: Optional[str] = None
    # Prompt object returned by Langfuse SDK (if available). Keep separate
    # from `prompt_name` so we don't attempt to JSON-serialize it.
    prompt_obj: Optional[object] = None


def load_json(file_path):
    """Load JSON data from a file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


# In-code fallback when no default model_config.json file exists
_DEFAULT_MODEL_CONFIG = {"tools": [], "tool_choice": "none"}


def load_model_config(check_dir: Path) -> Dict[str, Any]:
    """Load model/API config for a check, with fallback to default.
    
    Uses check_dir / "model_config.json" if present; otherwise
    DEFAULT_MODEL_CONFIG_PATH; otherwise an in-code default (no tools).
    
    Args:
        check_dir: Path to the check directory.
    Returns:
        Model config dict (e.g. tools, tool_choice).
    """
    per_check = check_dir / "model_config.json"
    if per_check.exists():
        try:
            return load_json(per_check)
        except Exception as e:
            logger.warning(
                f"Failed to load {per_check}, using default model config: {e}"
            )
    if DEFAULT_MODEL_CONFIG_PATH.exists():
        try:
            return load_json(DEFAULT_MODEL_CONFIG_PATH)
        except Exception as e:
            logger.warning(
                f"Failed to load default model config "
                f"{DEFAULT_MODEL_CONFIG_PATH}, using in-code default: {e}"
            )
    return dict(_DEFAULT_MODEL_CONFIG)


def _log_model_config_summary(check_name: str, model_config: Dict[str, Any]) -> None:
    """Log a short summary of model config (tools, permissions) for a check."""
    tools = model_config.get("tools") or []
    tool_choice = model_config.get("tool_choice", "none")
    if not tools:
        logger.info(
            f"[{check_name}] Model config: no tools (tool_choice=%s)",
            tool_choice,
        )
        return
    tool_types = [t.get("type", "?") if isinstance(t, dict) else "?" for t in tools]
    extra = []
    if model_config.get("max_tool_calls") is not None:
        extra.append(f"max_tool_calls={model_config['max_tool_calls']}")
    if model_config.get("include"):
        extra.append("include=" + str(model_config["include"]))
    if model_config.get("reasoning"):
        extra.append("reasoning=" + str(model_config["reasoning"]))
    if model_config.get("max_output_tokens") is not None:
        extra.append(f"max_output_tokens={model_config['max_output_tokens']}")
    msg = (
        f"[{check_name}] Model config: tools={tool_types}, tool_choice={tool_choice}"
    )
    if extra:
        msg += " (" + ", ".join(extra) + ")"
    logger.info(msg)


def run_model(
    check_data: CheckData,
    prompt: str,
    use_cache: bool = True,
    model: str = DEFAULT_MODEL,
    prompt_name: Optional[str] = None,
    prompt_obj: Optional[object] = None,
    sub_function: str = "evaluate",
) -> List[ModelResult]:
    """Step 2: Run the model on all inputs.
    
    Args:
        inputs: Dictionary containing:
            - check_data: The checklist data
            - examples: List of Example instances
            - prompt: The prompt to use
            - schema: The schema for structured output
            - prompt_name: Name of the prompt being used
        use_cache: If True, use cached outputs when available
        mock: If True, use expected outputs as model outputs (no API calls)
        model: The model to use for generation
        
    Returns:
        List of dictionaries containing model outputs
    """
    logger.info(f"Running model on {len(check_data.examples)} inputs (model=%s)", model)
    _log_model_config_summary(check_data.check_name, check_data.model_config)

    # Initialize model cache
    cache_dir = CACHE_DIR
    model_cache = ModelCache(cache_dir)

    results = []

    check_name = check_data.check_name
    examples = check_data.examples
    schema = check_data.schema

    for example in tqdm(examples, desc="Running model", unit="example"):
        try:
            # Generate new output without caching
            model_input = ModelInput(
                example=example,
                prompt=prompt,
                schema=schema,
                prompt_name=prompt_name,
                prompt_obj=prompt_obj,
            )
            input_metadata = {
                "doc_id": example.doc_id,
                "source": example.relative_source_path,
                "example_type": example.example_class_name,
                "prompt_name": prompt_name,
                "sub_function": sub_function,
            }
            # Check cache first if enabled
            if use_cache:
                cache_key = model_cache.generate_cache_key(
                    model_input, check_name, model,
                    model_config=check_data.model_config
                )
                cached_result = model_cache.get_cached_output(cache_key)
                if cached_result:
                    logger.debug(
                        "Using cached output for "
                        f"{example.doc_id}"
                    )
                    model_output = cached_result["data"]
                    response_metadata = cached_result["metadata"]
                else:
                    try:
                        model_output, response_metadata = generate_response(
                            model_input,
                            model=model,
                            metadata=input_metadata,
                            model_config=check_data.model_config
                        )
                    except Exception as e:
                        logger.error(
                            f"Error generating response for "
                            f"{example.doc_id}: {str(e)}"
                        )
                        raise
                    # Cache the new output
                    model_cache.cache_output(
                        cache_key,
                        data=model_output,
                        metadata=response_metadata
                    )
            else:
                try:
                    model_output, response_metadata = generate_response(
                        model_input,
                        model=model,
                        metadata=input_metadata,
                        model_config=check_data.model_config
                    )
                except Exception as e:
                    logger.error(
                        f"Error generating response for "
                        f"{example.doc_id}: {str(e)}"
                    )
                    raise

            # Accumulate result
            results.append(ModelResult(
                doc_id=example.doc_id,
                model_output=model_output,
                metadata=response_metadata
            ))

        except Exception as e:
            logger.error(
                f"Error processing example "
                f"{example.doc_id}: {str(e)}"
            )
            # Continue with next example instead of failing completely
            continue
    return results



def _load_local_config(check_dir: Path) -> Dict[str, Any]:
    """Load config from local config.json, or derive from schema.json + benchmark.json."""
    config_file = check_dir / "config.json"
    if config_file.exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {config_file}: {e}")
    # Derive config from existing local files
    cfg: Dict[str, Any] = {}
    schema_file = check_dir / "schema.json"
    if schema_file.exists():
        try:
            with open(schema_file, "r", encoding="utf-8") as f:
                cfg["output_schema"] = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load {schema_file}: {e}")
    benchmark_file = check_dir / "benchmark.json"
    if benchmark_file.exists():
        try:
            with open(benchmark_file, "r", encoding="utf-8") as f:
                benchmark = json.load(f)
            cfg.update(benchmark)
        except Exception as e:
            logger.warning(f"Failed to load {benchmark_file}: {e}")
    return cfg


def _load_local_prompts(check_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load prompts from local prompt.txt or prompts/prompt*.txt files.

    Checks (in order):
      1. ``<check_dir>/prompt.txt``
      2. ``<check_dir>/prompts/prompt.txt``
      3. All ``<check_dir>/prompts/prompt*.txt`` (sorted, as multiple versions)
    """
    prompts: Dict[str, Dict[str, Any]] = {}
    # Try a single prompt.txt at the check directory root or in prompts/
    for candidate in [check_dir / "prompt.txt", check_dir / "prompts" / "prompt.txt"]:
        if candidate.exists():
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    text = f.read()
                prompts[f"{check_dir.name}::local::prompt"] = {
                    "text": text,
                    "obj": None,
                    "version_id": "local",
                    "config": None,
                }
                return prompts
            except Exception as e:
                logger.warning(f"Failed to load {candidate}: {e}")
    # Fall back to all numbered prompt files in prompts/
    prompts_dir = check_dir / "prompts"
    if prompts_dir.exists():
        for prompt_file in sorted(prompts_dir.glob("prompt*.txt")):
            try:
                with open(prompt_file, "r", encoding="utf-8") as f:
                    text = f.read()
                key = f"{check_dir.name}::local::{prompt_file.stem}"
                prompts[key] = {
                    "text": text,
                    "obj": None,
                    "version_id": f"local::{prompt_file.stem}",
                    "config": None,
                }
            except Exception as e:
                logger.warning(f"Failed to load {prompt_file}: {e}")
    return prompts


def load_prompt_config_for_check(
    check_dir: Path,
    prompt_version: Optional[str] = None,
    config_from_version: bool = False,
) -> Dict[str, Any] | None:
    """Load Langfuse prompt config for a given check.

    This helper is used to pin multiple checks to one check's prompt config.
    """
    if langfuse_client is None:
        logger.warning(
            "Langfuse client not initialized; falling back to local config.json for %s",
            check_dir.name,
        )
        cfg = _load_local_config(check_dir)
        return cfg if cfg else None

    prompt_version_norm = (
        str(prompt_version).strip().lower()
        if prompt_version is not None
        else None
    )
    checklist_name = check_dir.parent.name
    prompt_key = f"checklists/{checklist_name}/{check_dir.name}"

    try:
        prompts_resp = None
        try:
            prompts_resp = langfuse_client.api.prompts.list(name=prompt_key)
        except Exception:
            try:
                prompts_resp = getattr(
                    langfuse_client, "list_prompts", lambda **k: None
                )(name=prompt_key)
            except Exception:
                prompts_resp = None

        # If listing is unavailable, fetch directly.
        if not prompts_resp or not getattr(prompts_resp, "data", None):
            try:
                if prompt_version_norm in (None, "production"):
                    prompt_obj = langfuse_client.get_prompt(prompt_key)
                elif prompt_version_norm == "latest":
                    try:
                        prompt_obj = langfuse_client.get_prompt(
                            prompt_key, version="latest"
                        )
                    except Exception:
                        prompt_obj = langfuse_client.get_prompt(prompt_key)
                else:
                    prompt_obj = langfuse_client.get_prompt(
                        prompt_key, version=prompt_version
                    )
            except Exception as e:
                logger.error(
                    f"Failed to fetch prompt/config for {prompt_key}: {e}"
                )
                return None
            return getattr(prompt_obj, "config", {}) or {}

        prompt_entry = prompts_resp.data[0]
        cfg = getattr(prompt_entry, "config", None)
        if not cfg:
            try:
                prod_prompt = langfuse_client.get_prompt(prompt_key)
                cfg = getattr(prod_prompt, "config", {}) or {}
            except Exception:
                cfg = {}

        if not (config_from_version and prompt_version is not None):
            return cfg

        if prompt_version_norm == "production":
            try:
                prod_prompt = langfuse_client.get_prompt(prompt_key)
                return getattr(prod_prompt, "config", {}) or {}
            except Exception as e:
                logger.warning(
                    f"Failed to fetch production prompt config for {prompt_key}: {e}"
                )
                return cfg

        prompt_versions = getattr(prompt_entry, "versions", [])
        latest_idx = None
        if prompt_version_norm == "latest" and prompt_versions:
            best_idx = None
            best_num = None
            for idx, v in enumerate(prompt_versions):
                raw_ver = getattr(v, "version", None)
                try:
                    if raw_ver is not None:
                        num = int(str(raw_ver))
                        if best_num is None or num > best_num:
                            best_num = num
                            best_idx = idx
                except Exception:
                    continue
            latest_idx = best_idx if best_idx is not None else (len(prompt_versions) - 1)

        for idx, v in enumerate(prompt_versions):
            ver_id = (
                getattr(v, "id", None)
                or getattr(v, "version", None)
                or getattr(v, "name", None)
                or idx
            )
            if prompt_version_norm == "latest":
                if latest_idx is None or idx != latest_idx:
                    continue
            elif str(prompt_version) not in {str(ver_id), str(idx)}:
                continue

            try:
                full_prompt = langfuse_client.get_prompt(prompt_key, version=v)
            except Exception:
                try:
                    full_prompt = langfuse_client.get_prompt(
                        prompt_key, version=ver_id
                    )
                except Exception:
                    full_prompt = None
            version_cfg = (
                (getattr(full_prompt, "config", None) if full_prompt else None)
                or getattr(v, "config", None)
                or {}
            )
            return version_cfg

        logger.warning(
            f"Requested prompt version '{prompt_version}' not found for {prompt_key}; "
            "falling back to entry config"
        )
        return cfg
    except Exception as e:
        logger.error(f"Error loading prompt config for {prompt_key}: {e}")
        return None


def prepare_check_data(
    check_dir: Path,
    prompt_version: Optional[str] = None,
    config_from_version: bool = False,
    fixed_prompt_config: Optional[Dict[str, Any]] = None,
) -> Tuple[CheckData | None, Dict[str, str]]:
    """Prepare data for processing a check.
    
    This function consolidates common functionality for loading check data,
    schema, prompts, and gathering examples. It can be used by both
    initialize() and process_check() functions.
    
    Args:
        check_dir: Path to the check directory
        prompt_version: Optional prompt version identifier/index to select.
            If provided, only that version is processed.
        config_from_version: If True and prompt_version is provided, source
            config from the selected version prompt object instead of the
            prompt entry/production fallback.
        fixed_prompt_config: If provided, override this check's Langfuse
            prompt config with the given config.
    Returns:
        Tuple of (CheckData object, prompts dict) or (None, {}) if 
        preparation fails
    """
    logger.info(f"Preparing data for check: {check_dir.name}")
    prompt_version_norm = (
        str(prompt_version).strip().lower()
        if prompt_version is not None
        else None
    )

    # When Langfuse is unavailable, fall back to local prompt.txt and config.json
    if langfuse_client is None:
        logger.warning(
            "Langfuse client not initialized; falling back to local "
            "prompt.txt and config.json for %s",
            check_dir.name,
        )
        _cfg = _load_local_config(check_dir)
        if fixed_prompt_config is not None:
            _cfg = fixed_prompt_config
        _schema = _cfg.get("output_schema", {})
        _benchmark = {k: v for k, v in _cfg.items() if k != "output_schema"}
        _check_name = _benchmark.get("name", check_dir.name)
        _prompts = _load_local_prompts(check_dir)
        if not _prompts:
            logger.error(
                f"No local prompt files found for {check_dir.name}; "
                "cannot prepare check data without prompts"
            )
            return (None, {})
        _example_paths = _benchmark.get("examples", [])
        if not _example_paths:
            logger.warning(f"No examples found in local config for check: {check_dir.name}")
            return (None, {})
        try:
            _example_class = _benchmark["example_class"]
        except KeyError:
            logger.error(f"No example_class found in local config for {check_dir.name}")
            return (None, {})
        try:
            _examples = [
                EXAMPLE_FACTORY.create(ex_path, _example_class)
                for ex_path in _example_paths
            ]
        except Exception as _e:
            logger.error(f"Error gathering examples: {str(_e)}")
            return (None, {})
        if not _examples:
            logger.warning(f"No valid examples for check: {check_dir.name}")
            return (None, {})
        _expected_outputs = []
        for _ex in _examples:
            try:
                _out = _ex.get_expected_output(_check_name)
            except Exception as _e:
                logger.error(f"Error getting expected output ({_ex.doc_id}): {_e}")
                continue
            if _out is not None:
                _expected_outputs.append(_out)
        if not _expected_outputs or len(_expected_outputs) != len(_examples):
            logger.warning(f"Missing expected outputs for check: {check_dir.name}")
            return (None, {})
        return CheckData(
            check_dir_name=check_dir.name,
            check_name=_check_name,
            schema=_schema,
            examples=_examples,
            expected_outputs=_expected_outputs,
            model_config=load_model_config(check_dir),
        ), _prompts

    # Fetch check metadata and ALL prompt versions from Langfuse
    try:
        if langfuse_client is None:
            logger.error("Langfuse client not initialized; cannot fetch prompts/config")
            return (None, {})

        checklist_name = check_dir.parent.name
        prompt_key = f"checklists/{checklist_name}/{check_dir.name}"
        logger.info(f"Langfuse: listing prompts for key={prompt_key}")

        # Use the API listing endpoint to get versions per user's instruction
        prompts_resp = None
        try:
            prompts_resp = langfuse_client.api.prompts.list(name=prompt_key)
        except Exception as e:
            # fallback to older helper if api.prompts not available
            logger.debug(f"langfuse_client.api.prompts.list failed: {e}")
            try:
                # Try top-level list helper if present
                prompts_resp = getattr(langfuse_client, "list_prompts", lambda **k: None)(name=prompt_key)
            except Exception:
                prompts_resp = None

        if not prompts_resp or not getattr(prompts_resp, "data", None):
            # As a last resort, try get_prompt and wrap as single-version
            try:
                if prompt_version_norm in (None, "production"):
                    prompt_obj = langfuse_client.get_prompt(prompt_key)
                    prompt_key_suffix = "production"
                elif prompt_version_norm == "latest":
                    # Some SDK versions accept "latest" directly; fallback
                    # to production if unsupported.
                    try:
                        prompt_obj = langfuse_client.get_prompt(
                            prompt_key, version="latest"
                        )
                    except Exception:
                        prompt_obj = langfuse_client.get_prompt(prompt_key)
                    prompt_key_suffix = "latest"
                else:
                    prompt_obj = langfuse_client.get_prompt(
                        prompt_key, version=prompt_version
                    )
                    prompt_key_suffix = str(prompt_version)
            except Exception as e:
                logger.error(f"No prompt returned from Langfuse for key: {prompt_key} and list failed: {e}")
                return (None, {})

            cfg = getattr(prompt_obj, "config", {}) or {}
            schema = cfg.get("output_schema", {})
            benchmark_data = {k: v for k, v in cfg.items() if k != "output_schema"}
            check_name = benchmark_data.get("name", check_dir.name)

            prompts = {
                f"{check_dir.name}::{prompt_key_suffix}": {
                    "text": getattr(prompt_obj, "prompt", str(prompt_obj)),
                    "obj": prompt_obj,
                }
            }
            logger.info(f"Fetched single Langfuse prompt for {check_dir.name}")
        else:
            # prompts_resp.data[0] is the prompt entry; its .versions attribute holds versions
            prompt_entry = prompts_resp.data[0]
            prompt_versions = getattr(prompt_entry, "versions", [])

            # Default config source is the prompt entry.
            cfg = getattr(prompt_entry, "config", None)
            # Some listing responses don't include the full config; fetch the
            # production prompt via get_prompt to obtain config as a fallback.
            if not cfg:
                try:
                    prod_prompt = langfuse_client.get_prompt(prompt_key)
                    cfg = getattr(prod_prompt, "config", {}) or {}
                except Exception:
                    cfg = {}

            schema = cfg.get("output_schema", {})
            benchmark_data = {k: v for k, v in cfg.items() if k != "output_schema"}
            check_name = benchmark_data.get("name", check_dir.name)

            prompts = {}
            selected_prompt_cfg = None

            # Explicit production alias: bypass version list and load
            # production prompt directly.
            if prompt_version_norm == "production":
                try:
                    prod_prompt = langfuse_client.get_prompt(prompt_key)
                    text = (
                        getattr(prod_prompt, "prompt", None)
                        or getattr(prod_prompt, "text", None)
                        or getattr(prod_prompt, "content", None)
                        or str(prod_prompt)
                    )
                    prompts[f"{check_dir.name}::production"] = {
                        "text": text,
                        "obj": prod_prompt,
                        "version_id": "production",
                        "config": getattr(prod_prompt, "config", None),
                    }
                    if config_from_version:
                        selected_prompt_cfg = getattr(prod_prompt, "config", None) or {}
                except Exception as e:
                    logger.error(
                        f"Failed to fetch production prompt for {prompt_key}: {e}"
                    )
                    return (None, {})

            # For latest alias, select one version entry before iterating.
            latest_idx = None
            if prompt_version_norm == "latest" and prompt_versions:
                # Prefer highest numeric `version`; otherwise use the final
                # item in the returned list as the latest fallback.
                best_idx = None
                best_num = None
                for idx, v in enumerate(prompt_versions):
                    raw_ver = getattr(v, "version", None)
                    try:
                        if raw_ver is not None:
                            num = int(str(raw_ver))
                            if best_num is None or num > best_num:
                                best_num = num
                                best_idx = idx
                    except Exception:
                        continue
                latest_idx = best_idx if best_idx is not None else (len(prompt_versions) - 1)

            # Normalize versions into separate prompt entries
            for idx, v in enumerate(prompt_versions):
                try:
                    if prompt_version_norm == "production":
                        # Already handled by direct production fetch.
                        break

                    # Determine a version identifier we can pass to get_prompt
                    ver_id = (
                        getattr(v, "id", None)
                        or getattr(v, "version", None)
                        or getattr(v, "name", None)
                        or idx
                    )

                    # If a specific version is requested, keep only that one.
                    if prompt_version is not None:
                        if prompt_version_norm == "latest":
                            if latest_idx is None or idx != latest_idx:
                                continue
                        elif str(prompt_version) not in {str(ver_id), str(idx)}:
                            continue

                    # Retrieve the full prompt object for this specific version
                    full_prompt = None
                    try:
                        full_prompt = langfuse_client.get_prompt(prompt_key, version=v)
                    except Exception:
                        # Try passing the identifier instead
                        try:
                            full_prompt = langfuse_client.get_prompt(prompt_key, version=ver_id)
                        except Exception as e:
                            logger.warning(f"Failed to fetch prompt text for version {ver_id} of {prompt_key}: {e}")
                            full_prompt = None

                    if not full_prompt:
                        # If we couldn't fetch the full prompt, attempt to extract any text available on the version object
                        text = getattr(v, "prompt", None) or getattr(v, "text", None) or getattr(v, "content", None) or str(v)
                        key = f"{check_dir.name}::version::{ver_id}"
                        prompts[key] = {
                            "text": text,
                            "obj": v,
                            "version_id": str(ver_id),
                            "config": getattr(v, "config", None),
                        }
                        continue

                    # Extract textual prompt from the returned full_prompt object
                    text = getattr(full_prompt, "prompt", None) or getattr(full_prompt, "text", None) or getattr(full_prompt, "content", None) or str(full_prompt)
                    key = f"{check_dir.name}::version::{ver_id}"
                    prompts[key] = {
                        "text": text,
                        "obj": full_prompt,
                        "version_id": str(ver_id),
                        "config": getattr(full_prompt, "config", None),
                    }

                    # Optionally source config from this selected version.
                    if (
                        config_from_version
                        and prompt_version is not None
                        and (
                            (prompt_version_norm == "latest" and latest_idx == idx)
                            or str(prompt_version) in {str(ver_id), str(idx)}
                        )
                    ):
                        selected_prompt_cfg = getattr(full_prompt, "config", None) or {}
                except Exception as e:
                    logger.warning(f"Skipping malformed prompt version for {check_dir.name}: {e}")

            if prompt_version is not None and not prompts:
                logger.error(
                    f"Requested prompt version '{prompt_version}' not found for {prompt_key}"
                )
                return (None, {})

            if config_from_version and prompt_version is not None:
                if selected_prompt_cfg:
                    cfg = selected_prompt_cfg
                    schema = cfg.get("output_schema", {})
                    benchmark_data = {k: v for k, v in cfg.items() if k != "output_schema"}
                    check_name = benchmark_data.get("name", check_dir.name)
                else:
                    logger.warning(
                        "Selected prompt version config unavailable; "
                        "falling back to prompt entry/production config"
                    )

            if config_from_version and prompt_version is None:
                logger.warning(
                    "--config-from-version set without --prompt-version; "
                    "using prompt entry/production config"
                )

            logger.info(f"Fetched {len(prompts)} prompt versions for {check_dir.name} from Langfuse")

    except Exception as e:
        logger.error(f"Error fetching prompt/config from Langfuse for {check_dir.name}: {e}")
        return (None, {})

    if fixed_prompt_config is not None:
        cfg = fixed_prompt_config
        schema = cfg.get("output_schema", {})
        benchmark_data = {
            k: v for k, v in cfg.items() if k != "output_schema"
        }
        check_name = benchmark_data.get("name", check_dir.name)
        logger.info(
            f"Using fixed prompt config override for check: {check_dir.name}"
        )

    # Get list of paths to examples from benchmark (from Langfuse config)
    example_paths = benchmark_data.get("examples", [])
    if not example_paths:
        logger.warning(f"No examples found in check: {check_dir.name}")
        return (None, {})

    # Get example class from benchmark (from Langfuse config)
    try:
        example_class_name = benchmark_data["example_class"]
    except KeyError:
        logger.error(f"No example class found in Langfuse config for {prompt_key}")
        return (None, {})

    try:
        examples = [
            EXAMPLE_FACTORY.create(ex_path, example_class_name)
            for ex_path in example_paths
        ]
    except Exception as e:
        logger.error(f"Error gathering examples: {str(e)}")
        return (None, {})
    if not examples:
        logger.warning(
            f"No valid examples gathered for check: {check_dir.name}"
        )
        return (None, {})

    try:
        expected_outputs = []
        for example in examples:
            try:
                expected_output = example.get_expected_output(check_name)
            except Exception as e:
                logger.error(f"Error getting expected outputs ({example.doc_id}): {str(e)}")
                continue
            if expected_output is not None:
                expected_outputs.append(expected_output)
            else:
                logger.warning(
                    f"No expected output found for example: {example.doc_id}. "
                    f"This may indicate that the example is not properly "
                    f"initialized."
                )
                continue
    except Exception as e:
        logger.error(f"Error getting expected outputs: {str(e)}")
        return (None, {})
    if not expected_outputs:
        # this can happen when initializing
        logger.warning(
            f"No valid expected outputs gathered for check: {check_dir.name}"
        )
        return (None, {})
    else:
        # this should not happen and indicates some expected outputs are 
        # missing
        assert len(expected_outputs) == len(examples), (
            f"Expected outputs not found for all examples in "
            f"check: {check_dir.name}"
        )

    # Validate that we have the same number of examples with doc_ids as 
    # expected outputs
    # This ensures consistency between examples and expected_outputs
    if len(examples) != len(expected_outputs):
        logger.error(
            f"Mismatch between examples with doc_ids "
            f"({len(examples)}) and expected outputs "
            f"({len(expected_outputs)}) for check: {check_dir.name}. "
            f"This may indicate examples with None doc_ids."
        )
        return (None, {})

    model_config = load_model_config(check_dir)

    check_data = CheckData(
        check_dir_name=check_dir.name,
        check_name=check_name,
        schema=schema,
        examples=examples,
        expected_outputs=expected_outputs,
        model_config=model_config,
    )

    return check_data, prompts


def process_check(
    check_dir: Path,
    checklist_name: str,
    mock: bool = False,
    use_cache: bool = True,
    model: str = DEFAULT_MODEL,
    prompt_version: Optional[str] = None,
    config_from_version: bool = False,
    fixed_prompt_config: Optional[Dict[str, Any]] = None,
    match_threshold: float = 1.0,
    sentence_transformer_model: str = (
        DEFAULT_SENTENCE_TRANSFORMER_MODEL
    ),
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Process a single check.
    
    Args:
        check_dir: Path to the check directory
        checklist_name: Name of the checklist
        mock: If True, use expected outputs as model outputs (no API calls)
        use_cache: If True, use cached outputs when available
        model: The model to use for generation
        match_threshold: Threshold for considering a match (0-1)
        sentence_transformer_model: SentenceTransformer model for semantic similarity
        
    Returns:
        Dictionary mapping string metric names to analysis results
    """
    # Human gate 5B: "Agentic pipeline should not revert back to legacy
    # prompts." Enforced here rather than only in the CLI router, because
    # `process_checklist` also funnels through this function and the
    # `prompts/` directories are deliberately still on disk (gate 5C). A
    # converted check that quietly ran its old prompt would file a
    # prompt-path score under an agentic check's name -- the exact confusion
    # the whole-checklist routing gap produced before it was fixed. Failing
    # loudly is the point.
    if is_agentic_check(check_dir):
        raise ValueError(
            f"{check_dir.name} is an agentic check and must not be run "
            "through the legacy prompt path. Run it with "
            f"`python -m soda_mmqc.cli run <checklist> --check "
            f"{check_dir.name}`, or via `evaluate`, which routes it "
            "automatically."
        )

    # Validate model compatibility
    if not validate_model_for_provider(model):
        compatible_models = get_compatible_models()
        raise ValueError(
            f"Model '{model}' is not compatible with provider '{API_PROVIDER}'. "
            f"Compatible models: {', '.join(compatible_models)}"
        )

    
    # Prepare check data
    check_data, prompts = prepare_check_data(
        check_dir,
        prompt_version=prompt_version,
        config_from_version=config_from_version,
        fixed_prompt_config=fixed_prompt_config,
    )
    if not check_data:
        return {}

    # Dictionary to store results for each prompt
    all_results = {}

    # Process each prompt
    for prompt_name, prompt in prompts.items():
        logger.info(f"Processing prompt: {prompt_name}")
        # Build full prompt key/path so traces can be linked back to the
        # prompt stored in Langfuse. Example: "checklists/fig-checklist/...".
        prompt_key = f"checklists/{checklist_name}/{prompt_name}"
        # prompt is a dict with 'text' and 'obj' keys (see prepare_check_data)
        prompt_text = prompt["text"] if isinstance(prompt, dict) else prompt
        prompt_obj = prompt.get("obj") if isinstance(prompt, dict) else None
        if mock:
            results = [
                ModelResult(
                    doc_id=example.doc_id,
                    model_output=expected_output,
                    metadata={
                        "doc_id": example.doc_id,
                        "source": example.relative_source_path,
                        "example_type": example.example_class_name
                    }
                )
                for example, expected_output in zip(
                    check_data.examples, check_data.expected_outputs
                )
            ]
        else:
            results = run_model(
                check_data,
                prompt_text,
                use_cache=use_cache,
                model=model,
                prompt_name=prompt_key,
                prompt_obj=prompt_obj,
                sub_function="evaluate",
            )

        # Analyze results with all string metrics
        analyzed_results = analyze_results(
            results,
            check_data.schema,
            check_data.expected_outputs,
            check_dir=check_dir,
            match_threshold=match_threshold,
            sentence_transformer_model=sentence_transformer_model,
        )

        # Store results for this prompt
        all_results[prompt_name] = analyzed_results

    save_analysis(
        all_results, checklist_name, check_data.check_name, model
    )

    return all_results


def list_checks(checklist_dir: Path) -> Dict[str, Path]:
    """List all checks in a checklist.

    Only directories owning the evaluation contracts are returned, so a
    shared skill sitting beside the checks cannot become a phantom check.
    """
    return {
        check_dir.name: check_dir
        for check_dir in sorted(checklist_dir.iterdir())
        if owns_evaluation_contracts(check_dir)
    }


def initialize(
    checklist_dir: Path,
    check_names: list[str],
    use_cache: bool = True,
    model: str = DEFAULT_MODEL,
    prompt_version: Optional[str] = None,
    config_from_version: bool = False,
    fixed_prompt_config: Optional[Dict[str, Any]] = None,
):
    """Initialize expected_output.json files for all examples in a checklist.
    
    This function iterates through the checks of a checklist. For each check,
    it uses the prompts in prompts/ and the schema.json to execute the check
    using the image and caption of each example. The output becomes the
    preliminary expected_output.json which is written in the
    <doc_id>/checks/<check_name>/ folder.
    
    Args:
        checklist_dir: Path to the checklist directory
        use_cache: If True, use cached outputs when available
        model: Model to use for generation
        check_name: If set, only initialize this check (reduces output)
    """
    # Get all checks from the checklist
    checks = list_checks(checklist_dir)
    if not checks:
        logger.error(f"No checks found in checklist: {checklist_dir.name}")
        return
    # Use only the specified check names if provided
    if check_names:
        checks = {name: checks[name] for name in check_names if name in checks}

    # Process each check
    for check_dir_name, check_dir in checks.items():
        if not check_dir_name:
            logger.info(f"Processing check: {check_dir_name}")
        
        # Prepare check data (use only the first prompt)
        prepared_data, prompts = prepare_check_data(
            check_dir,
            prompt_version=prompt_version,
            config_from_version=config_from_version,
            fixed_prompt_config=fixed_prompt_config,
        )

        if not prepared_data:
            continue

        # Get the first prompt for initialization
        # sort prompts alphabetically
        prompts_sorted = sorted(prompts.keys())
        first_prompt_name = prompts_sorted[0]
        first_prompt = prompts[first_prompt_name]

        # Handle structure where prompts map to dicts with text/obj
        first_prompt_text = first_prompt["text"] if isinstance(first_prompt, dict) else first_prompt
        first_prompt_obj = first_prompt.get("obj") if isinstance(first_prompt, dict) else None

        try:
            # Build full prompt key/path like in process_check
            prompt_key = f"checklists/{checklist_dir.name}/{first_prompt_name}"
            results = run_model(
                prepared_data,
                first_prompt_text,
                use_cache=use_cache,
                model=model,
                prompt_name=prompt_key,
                prompt_obj=first_prompt_obj,
                sub_function="init",
            )

            # Write expected outputs
            for result, example in zip(results, prepared_data.examples):
                try:
                    example.save_expected_output(
                        result.model_output,
                        prepared_data.check_name,
                        True
                    )
                except Exception as e:
                    logger.error(
                        f"Error writing expected output for "
                        f"{result.doc_id}: {str(e)}"
                    )
                    continue

        except Exception as e:
            logger.error(
                f"Error running model for check {check_dir_name}: {str(e)}"
            )
            continue


def process_checklist(
    checklist_dir: Path,
    checklist_name: str,
    mock: bool = False,
    use_cache: bool = True,
    model: str = DEFAULT_MODEL,
    check_names: Optional[list[str]] = None,
    prompt_version: Optional[str] = None,
    config_from_version: bool = False,
    fixed_prompt_config: Optional[Dict[str, Any]] = None,
    match_threshold: float = 1.0,
    sentence_transformer_model: str = (
        DEFAULT_SENTENCE_TRANSFORMER_MODEL
    ),
):
    """Process an entire checklist.
    
    Args:
        checklist_dir: Path to the checklist directory
        checklist_name: Name of the checklist
        mock: If True, use expected outputs as model outputs (no API calls)
        use_cache: If True, use cached outputs when available
        model: The model to use for generation
        match_threshold: Threshold for considering a match (0-1)
        sentence_transformer_model: SentenceTransformer model for semantic similarity
    """
    # Validate model compatibility
    if not validate_model_for_provider(model):
        compatible_models = get_compatible_models()
        raise ValueError(
            f"Model '{model}' is not compatible with provider '{API_PROVIDER}'. "
            f"Compatible models: {', '.join(compatible_models)}"
        )


    # Get all checks frmo the checklist
    checks = list_checks(checklist_dir)

    if not checks:
        logger.error(
            f"Checklist not found: {checklist_name}"
        )
        return

    if check_names:
        missing_checks = [name for name in check_names if name not in checks]
        if missing_checks:
            logger.warning(
                "Some requested checks were not found: "
                + ", ".join(missing_checks)
            )
        checks = {name: checks[name] for name in check_names if name in checks}
        if not checks:
            logger.error("None of the requested checks were found")
            return

    for check_dir_name, check_dir in checks.items():
        try:
            process_check(
                check_dir,
                checklist_name,
                mock=mock,
                use_cache=use_cache,
                model=model,
                prompt_version=prompt_version,
                config_from_version=config_from_version,
                fixed_prompt_config=fixed_prompt_config,
                match_threshold=match_threshold,
                sentence_transformer_model=sentence_transformer_model
            )
        except Exception as e:
            logger.error(
                f"Error processing check in {check_dir_name}: {str(e)}"
            )
            continue


def is_agentic_check(check_dir: Path) -> bool:
    """Whether a check is run by the agentic runner rather than a prompt.

    True when the directory is a check *and* owns at least one versioned
    ``SKILL.md``. Both halves matter: a shared skill has a ``SKILL.md`` and no
    evaluation contracts, so it is not a check and must never be dispatched
    as one.

    The discriminator is deliberately **per check** rather than per checklist.
    The plan words this as "a checklist with an agentic layout dispatches",
    which is right for a fully converted checklist and wrong during the
    conversion: `fig-checklist` has one converted leaf and ten that still
    have only prompts, so checklist-level dispatch would break ten working
    checks to route one. Per-check routing satisfies the plan's own first
    clause -- "legacy checks keep present behavior" -- and converges on its
    wording as the last leaf lands.
    """
    if not owns_evaluation_contracts(check_dir):
        return False
    return any(check_dir.glob("v*/SKILL.md"))


def _agentic_main(argv: list) -> int:
    """Hand off to the agentic runner. Indirected so tests can substitute."""
    from soda_mmqc.cli import main as agentic_main

    return agentic_main(argv)


def _agentic_argv(args, check_name: str) -> list:
    """Translate the legacy flags the agentic runner understands."""
    argv = ["run", args.checklist, "--check", check_name]
    if args.mock:
        argv.append("--mock")
    if args.model:
        argv += ["--model", args.model]
    if args.no_cache:
        argv.append("--no-cache")
    return argv


def _dispatch_check(args, checklist_dir: Path, check_name: str) -> int:
    """Route one check to the agentic runner. Returns its exit code.

    The code is propagated rather than discarded: a failed agentic run must
    surface as a failure, never as a silent success and never as a reason to
    hand the check back to the prompt path (human gate 5B).
    """
    return _agentic_main(_agentic_argv(args, check_name))


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Run MMQC checks on examples"
    )
    parser.add_argument(
        "checklist", type=str, help="Name of the checklist to process"
    )
    parser.add_argument(
        "--initialize", action="store_true", 
        help="Initialize expected output files"
    )
    parser.add_argument(
        "--mock", action="store_true", 
        help="Use mock responses instead of calling the model"
    )
    parser.add_argument(
        "--no-cache", action="store_true", 
        help="Disable caching of model responses"
    )
    parser.add_argument(
        "--check", type=str, help="Name of the check to process"
    )
    parser.add_argument(
        "--checks", nargs="+",
        help="List of check names to process"
    )
    parser.add_argument(
        "--model", type=str, default=DEFAULT_MODEL, 
        help="The model to use for generation"
    )
    parser.add_argument(
        "--prompt-version", type=str,
        help=(
            "Prompt version id/index to run, or one of: production, latest"
        )
    )
    parser.add_argument(
        "--config-from-version", action="store_true",
        help=(
            "When --prompt-version is set, use that version's config "
            "instead of prompt entry/production config"
        ),
    )
    parser.add_argument(
        "--config-source-check", type=str,
        help=(
            "Use prompt config from this check (and selected --prompt-version) "
            "for all selected checks"
        )
    )
    parser.add_argument(
        "--match-threshold", type=float, default=1.0,
        help="Reserved for flat evaluator; per-field thresholds use eval-manifest.json"
    )
    parser.add_argument(
        "--sentence-transformer-model", type=str, 
        default=DEFAULT_SENTENCE_TRANSFORMER_MODEL,
        help="SentenceTransformer model for semantic similarity"
    )
    args = parser.parse_args()

    # Get the checklist directory using the config function
    checklist_name = args.checklist
    checklist_dir = CHECKLIST_DIR / checklist_name
    if not checklist_dir.exists():
        logger.error(f"Checklist directory not found: {checklist_dir}")
        return

    # Validate model compatibility with current provider
    if not validate_model_for_provider(args.model):
        compatible_models = get_compatible_models()
        logger.error(
            f"Model '{args.model}' is not compatible with provider '{API_PROVIDER}'. "
            f"Compatible models: {', '.join(compatible_models)}"
        )
        return

    if args.check and args.checks:
        logger.error("Use only one of --check or --checks")
        return

    selected_checks = list(args.checks) if args.checks else (
        [args.check] if args.check else []
    )

    fixed_prompt_config = None
    if args.config_source_check:
        if selected_checks and args.config_source_check not in selected_checks:
            logger.error(
                "--config-source-check must be included in --check/--checks"
            )
            return
        config_source_dir = checklist_dir / args.config_source_check
        if not config_source_dir.exists() or not config_source_dir.is_dir():
            logger.error(
                f"Config source check not found: {args.config_source_check}"
            )
            return
        fixed_prompt_config = load_prompt_config_for_check(
            config_source_dir,
            prompt_version=args.prompt_version,
            config_from_version=args.config_from_version,
        )
        if not fixed_prompt_config:
            logger.error(
                f"Unable to load prompt config from source check: "
                f"{args.config_source_check}"
            )
            return
        logger.info(
            f"Pinned prompt config to source check: {args.config_source_check}"
        )
    
    # Initialize if requested
    if args.initialize:
        initialize(
            checklist_dir,
            selected_checks,
            not args.no_cache,
            args.model,
            prompt_version=args.prompt_version,
            config_from_version=args.config_from_version,
            fixed_prompt_config=fixed_prompt_config,
        )
        return

    # Agentic checks are dispatched to soda_mmqc.cli; everything else keeps
    # exactly its present behaviour. `--prompt-version` has no meaning for a
    # skill, so asking for one is refused rather than silently ignored.
    # A whole-checklist run names no checks, so resolve it to the full list
    # before routing. Without this an agentic check would silently fall
    # through to its legacy prompt during a `evaluate <checklist>` run --
    # producing a prompt-path score under an agentic check's name, which is
    # the most confusing possible outcome.
    routed_checks = selected_checks or sorted(list_checks(checklist_dir))
    if routed_checks:
        agentic = [
            name for name in routed_checks
            if is_agentic_check(checklist_dir / name)
        ]
        if agentic and args.prompt_version:
            logger.error(
                "--prompt-version selects between prompt files and has no "
                "meaning for agentic check(s): %s. Skills are versioned by "
                "directory (v1, v2, ...) and pinned by manifest, not by this "
                "flag. Re-run without --prompt-version, or name only legacy "
                "checks.",
                ", ".join(agentic),
            )
            return 2
        failed = [
            name for name in agentic
            if _dispatch_check(args, checklist_dir, name)
        ]
        if failed:
            logger.error(
                "Agentic check(s) failed: %s. They are NOT re-run through "
                "the legacy prompt path.", ", ".join(failed)
            )
            return 1
        if agentic:
            # Only narrow the legacy selection when something was actually
            # routed away, so a checklist with no agentic checks keeps
            # passing the caller's original selection through untouched.
            selected_checks = [
                name for name in routed_checks if name not in agentic
            ]
            if not selected_checks:
                return

    if selected_checks and len(selected_checks) == 1:
        check_name = selected_checks[0]
        # Find the check in the checklist. A directory only counts as a check
        # if it owns the evaluation contracts, so a shared skill sitting
        # beside the checks cannot be run as one.
        check_dir = checklist_dir / check_name
        if owns_evaluation_contracts(check_dir):
            process_check(
                check_dir, args.checklist, args.mock, not args.no_cache,
                model=args.model,
                prompt_version=args.prompt_version,
                config_from_version=args.config_from_version,
                fixed_prompt_config=fixed_prompt_config,
                match_threshold=args.match_threshold,
                sentence_transformer_model=args.sentence_transformer_model
            )
        elif check_dir.is_dir():
            logger.error(
                f"Not a check (no {' / '.join(EVALUATION_CONTRACT_FILES)}): "
                f"{check_name}"
            )
        else:
            logger.error(f"Check not found: {check_name}")
    else:
        # Process the entire checklist
        process_checklist(
            checklist_dir, args.checklist, args.mock, not args.no_cache,
            model=args.model,
            check_names=selected_checks,
            prompt_version=args.prompt_version,
            config_from_version=args.config_from_version,
            fixed_prompt_config=fixed_prompt_config,
            match_threshold=args.match_threshold,
            sentence_transformer_model=args.sentence_transformer_model
        )


def initialize_main():
    """Entry point for the initialize command that passes --initialize to 
    main."""
    import sys
    sys.argv.append("--initialize")
    main()


if __name__ == "__main__":
    main()