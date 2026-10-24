import os
import tempfile
from pathlib import Path
import logging
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# Lazy device cache so torch is not imported at config load time (avoids
# abort in some environments when running tests that don't need torch).
_device_cache: Optional[str] = None


# Device validation and setup (torch imported lazily inside)
def _validate_and_setup_device() -> str:
    """Validate the requested device and return the best available device.
    
    Returns:
        str: The device string to use ('cuda', 'mps', or 'cpu')
    """
    import torch

    requested_device = os.getenv("DEVICE", "cpu").lower()
    
    # Setup logging for device validation
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    if requested_device == "mps":
        if torch.backends.mps.is_available():
            logger.info(
                "✅ MPS (Metal Performance Shaders) is available "
                "and will be used"
            )
            return "mps"
        else:
            logger.warning(
                "⚠️  MPS requested but not available, falling back to CPU"
            )
            return "cpu"
    elif requested_device in ["cuda", "gpu"]:
        if torch.cuda.is_available():
            logger.info(
                f"✅ CUDA is available with {torch.cuda.device_count()} GPU(s)"
            )
            return "cuda"
        else:
            logger.warning(
                "⚠️  CUDA requested but not available, falling back to CPU"
            )
            return "cpu"
    elif requested_device == "cpu":
        logger.info("📱 CPU device selected")
        return "cpu"
    else:
        logger.warning(
            f"⚠️  Unknown device '{requested_device}' requested, "
            "falling back to CPU"
        )
        return "cpu"


def get_device() -> str:
    """Return the validated device string, initializing once (lazy)."""
    global _device_cache, DEVICE
    if _device_cache is None:
        _device_cache = _validate_and_setup_device()
        DEVICE = _device_cache
    return _device_cache


# Set on first get_device() call so code that imports DEVICE after device
# is used still sees the value. Prefer get_device() to avoid importing torch
# until device is actually needed.
DEVICE = None  # type: ignore[assignment]

# Get the package root directory
PACKAGE_ROOT = Path(__file__).parent

# Base data directory - can be overridden by environment variable
DATA_DIR = PACKAGE_ROOT / "data"
CACHE_DIR = Path(os.getenv("SODA_MMQC_CACHE_DIR", DATA_DIR / "cache"))

# Subdirectories
CHECKLIST_DIR = DATA_DIR / "checklist"
EXAMPLES_DIR = DATA_DIR / "examples"

#: Environment variable that pins the gold to a snapshot -- see soda_mmqc/gold.py.
GOLD_DIR_ENV = "SODA_MMQC_GOLD_DIR"


def gold_root() -> Path:
    """Where gold (``<example>/checks/<check>/expected_output.json``) is read.

    The live examples tree, unless ``SODA_MMQC_GOLD_DIR`` pins a snapshot of the
    gold at a git tag. A frozen experiment scores against the gold its findings
    used, not the gold as later curated (contract cleanup, W5a). Read when the
    gold is read, not at import, so a notebook's first cell can still set it.
    Only gold is redirected: an example's inputs are always read from
    ``EXAMPLES_DIR``.
    """
    pinned = os.environ.get(GOLD_DIR_ENV)
    return Path(pinned) if pinned else EXAMPLES_DIR
EVALUATION_DIR = DATA_DIR / "evaluation"

# A checklist subdirectory is a check when it owns these files. Everything
# else beside the checks (shared skills, generated docs) is not scoreable and
# must not be enumerated. See owns_evaluation_contracts().
EVALUATION_CONTRACT_FILES = ("schema.json", "benchmark.json")


#: The one file that makes a directory a leaf. See
#: :func:`owns_evaluation_contracts`.
LEAF_SCHEMA_FILE = "schema.json"


def owns_evaluation_contracts(candidate_dir: Path) -> bool:
    """Return whether a directory is a **leaf** of its checklist.

    The discriminator is the output ``schema.json``, and only that. A leaf
    answers with structured output, so it owns the contract describing that
    output; an intermediate skill reports into the session it is already
    running in, answers nothing on its own, and therefore owns no schema, no
    benchmark and no manifest.

    One discriminator matters more than which one. Deriving leaf-ness from a
    name convention, a marker file, or a combination of files gives two
    answers that can disagree, and a shared skill that carries a schema is
    then advertising an output contract nobody asked it to satisfy.

    A leaf also needs ``benchmark.json`` to be scored, but that is a
    *completeness* question rather than an identity one, so a half-built
    check still enumerates and fails by name when it is run or scored.

    ``eval-manifest.json`` is deliberately not part of this test. It is
    required when scoring, but several legacy checklists predate it and must
    keep enumerating as they do today.

    This lives in config so that every enumerator -- the runner and the
    curation UI -- shares one definition of what a leaf is.
    """
    if not candidate_dir.is_dir():
        return False
    return (candidate_dir / LEAF_SCHEMA_FILE).is_file()


def list_checks(checklist_dir: Path) -> Dict[str, Path]:
    """Every check in a checklist, keyed by directory name.

    Only directories owning the evaluation contracts are returned, so a
    shared skill sitting beside the checks cannot become a phantom check.

    This lives beside ``owns_evaluation_contracts`` rather than in a runner,
    because enumerating checks and deciding what a check *is* are one
    question, and two answers to it drift.
    """
    return {
        check_dir.name: check_dir
        for check_dir in sorted(checklist_dir.iterdir())
        if owns_evaluation_contracts(check_dir)
    }


#: What goes to production: the agentic checklists published as skills
#: (``skills``), and the prompt-based runner's per-check prompt versions
#: (``checks``). Read by the publishers in .github/scripts/.
PRODUCTION_MANIFEST = DATA_DIR / "production_prompts" / "production.json"


def production_skill_checklists() -> List[str]:
    """The checklists published to production as skills."""
    import json

    return list(json.loads(PRODUCTION_MANIFEST.read_text(encoding="utf-8")).get("skills") or [])


def resolve_check_dir(checklist: str, check: str) -> Path:
    """Return the directory of ``check`` within the named ``checklist``.

    Raises:
        FileNotFoundError: If the checklist or the check directory is absent.
        ValueError: If the directory exists but is not a check, i.e. it does
            not own the evaluation contracts (a shared skill, for instance).
    """
    return check_dir_in(CHECKLIST_DIR / checklist, check)


def check_dir_in(checklist_dir: Path, check: str) -> Path:
    """Return the directory of ``check`` within the checklist at ``checklist_dir``.

    Raises:
        FileNotFoundError: If the checklist or the check directory is absent.
        ValueError: If the directory exists but is not a check.
    """
    checklist_dir = Path(checklist_dir)
    if not checklist_dir.is_dir():
        raise FileNotFoundError(f"Checklist not found: {checklist_dir}")

    check_dir = checklist_dir / check
    if not check_dir.is_dir():
        known = ", ".join(sorted(list_checks(checklist_dir))) or "none"
        raise FileNotFoundError(
            f"Check not found: {check_dir}. Known checks: {known}"
        )
    if not owns_evaluation_contracts(check_dir):
        raise ValueError(
            f"{check_dir} is not a check: it does not own "
            f"{' and '.join(EVALUATION_CONTRACT_FILES)}. Shared skills sit "
            "beside the checks but cannot be scored."
        )
    return check_dir


# ---------------------------------------------------------------------------
# Agentic runtime root
# ---------------------------------------------------------------------------
#
# Where cli.py assembles the sealed, per-example runtime directory that an
# agent session is pointed at. It defaults to a system temp location and must
# never resolve inside the repository.
#
# The reason is the Agent SDK's skill discovery, which is filesystem-driven
# and implicit. Per Anthropic's Agent SDK documentation, with default options
# the SDK loads skills from `~/.claude/skills/`, `<cwd>/.claude/skills/`, and
# `.claude/skills/` in *every parent directory of cwd up to the repository
# root*. So a runtime rooted anywhere inside this repo would silently pull in
# repo-level skills, and a session run from the repo would see them whether or
# not we assembled them.
#
# Two consequences, and both are containment requirements rather than
# preferences:
#
# 1. The runtime root lives outside the repository, so the upward crawl finds
#    nothing of ours. Example inputs are *copied in*; the repo is never mapped
#    in, never symlinked, and never added as an extra directory.
# 2. Being outside the repo is not on its own sufficient, because
#    `~/.claude/skills/` is loaded regardless of where cwd sits. The session
#    must therefore also pin its setting sources so personal skills cannot
#    join the session -- see agentic.runtime.AGENTIC_SETTING_SOURCES.
AGENTIC_RUNTIME_DIR = Path(
    os.getenv("SODA_MMQC_AGENTIC_RUNTIME_DIR", tempfile.gettempdir())
)

#: Directory-name markers of consumer file-sync clients. A runtime assembled
#: inside one of these would upload gold-derived intermediates to a third
#: party. The plan treats this as unverifiable by test -- "a person has to look
#: at the actual machine" -- but that only holds for *detecting* an arbitrary
#: sync tool. The common ones are named, on every platform, so the common case
#: is checkable anywhere and does not depend on who is looking or which OS
#: they are on.
CLOUD_SYNC_MARKERS = (
    "mobile documents",      # macOS iCloud Drive
    "com~apple~clouddocs",   # macOS iCloud Drive
    "cloudstorage",          # macOS third-party file providers
    "icloapture",            # defensive: iCloud variants
    "icloud drive",
    "dropbox",
    "onedrive",
    "google drive",
    "googledrive",
    "box sync",
    "pcloud",
    "nextcloud",
    "yandex.disk",
)


def _normalized_parts(path: Path) -> tuple:
    """Path components, case-folded, for portable comparison.

    macOS and Windows have case-insensitive filesystems, so a plain string
    or ``Path`` comparison can miss a match that the filesystem itself would
    resolve to the same place.
    """
    return tuple(os.path.normcase(part).lower() for part in path.parts)


def _is_within(child: Path, parent: Path) -> bool:
    """Portable "is child inside parent", case-insensitive where it matters."""
    child_parts = _normalized_parts(child)
    parent_parts = _normalized_parts(parent)
    return child_parts[: len(parent_parts)] == parent_parts

#: Model for agentic sessions.
#:
#: Deliberately separate from DEFAULT_MODEL, which follows API_PROVIDER and
#: resolves to an OpenAI model by default -- the agentic runner drives Claude
#: Code and cannot use one. The bare alias tracks the current Sonnet rather
#: than pinning a dated snapshot; Sonnet rather than Opus because the first
#: runs are small and diagnostic, and cost should not discourage rerunning
#: them. Model choice is a gate 4C decision, so overriding it is explicit.
AGENTIC_DEFAULT_MODEL = os.getenv("SODA_MMQC_AGENTIC_MODEL", "sonnet")

#: How many SkillSets an unpinned comparison may produce before the runner
#: says so. Not a limit -- expansion multiplies sessions, and cost is the
#: operator's call, not the runner's. It is set at 4 because that is where an
#: expansion stops being a comparison and starts being a sweep: at 4 sets over
#: the pilot's 3-example scope the run is 12 sessions, which is still
#: something a person watches finish; the next step up (2 skills x 3 versions,
#: or 3 skills x 2) is 6-8 sets and no longer is.
AGENTIC_SKILLSET_WARN_THRESHOLD = 4


def resolve_agentic_runtime_root() -> Path:
    """Return the runtime root, refusing anywhere it must not be.

    Deliberately OS-neutral. ``tempfile.gettempdir()`` already resolves to the
    right place on every platform -- ``/tmp`` on Linux, a per-user
    ``AppData\\Local\\Temp`` on Windows, a per-user ``/var/folders/...`` on
    macOS -- so the *default* needs no branching. What did need care is the
    checking: both refusals below compare case-insensitively, because macOS
    and Windows would otherwise let a differently-cased path slip past a rule
    their own filesystem treats as the same place.

    Raises:
        ValueError: If the root is inside the repository, or inside a
            recognised file-sync directory. Both defeat the containment the
            sealed runtime exists to provide, so they fail at configuration
            time rather than leaking at session time.
    """
    root = AGENTIC_RUNTIME_DIR.expanduser().resolve()
    repo_root = PACKAGE_ROOT.parent.resolve()

    if _is_within(root, repo_root):
        raise ValueError(
            f"AGENTIC_RUNTIME_DIR resolves inside the repository: {root}. "
            "The agent session must not be able to reach the repository, "
            "its other checklists, or the gold data. Set "
            f"SODA_MMQC_AGENTIC_RUNTIME_DIR to a path outside {repo_root}."
        )

    synced = {
        part
        for part in _normalized_parts(root)
        if part in CLOUD_SYNC_MARKERS
    }
    if synced:
        raise ValueError(
            f"AGENTIC_RUNTIME_DIR resolves inside a file-sync directory "
            f"({', '.join(sorted(synced))}): {root}. Runtime directories "
            "hold intermediates derived from unpublished figures; syncing "
            "them to a third party is a disclosure. Set "
            "SODA_MMQC_AGENTIC_RUNTIME_DIR to a local path."
        )
    return root
# Manifest string_compare modes (see core/leaves.py StringCompareMode)
STRING_COMPARE_MODES = ("exact", "fuzzy", "semantic")

# SentenceTransformer model for string_compare: semantic
DEFAULT_SENTENCE_TRANSFORMER_MODEL = "all-MiniLM-L6-v2"


# API Provider validation and setup
def _validate_and_setup_api_provider() -> str:
    """Validate the requested API provider and return the provider name.
    
    Returns:
        str: The API provider to use ('openai' or 'anthropic')
    """
    requested_provider = os.getenv("API_PROVIDER", "openai").lower()
    
    # Setup logging for API provider validation
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    if requested_provider == "openai":
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            logger.info("✅ OpenAI API provider configured")
        else:
            logger.warning(
                "⚠️  OpenAI selected but OPENAI_API_KEY not found in environment"
            )
        return "openai"
    elif requested_provider == "anthropic":
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            logger.info("✅ Anthropic API provider configured")
        else:
            logger.warning(
                "⚠️  Anthropic selected but ANTHROPIC_API_KEY not found in environment"
            )
        return "anthropic"
    else:
        logger.warning(
            f"⚠️  Unknown API provider '{requested_provider}' requested, "
            "falling back to OpenAI"
        )
        return "openai"


# API Provider configuration
API_PROVIDER = _validate_and_setup_api_provider()

# Default models for each provider
DEFAULT_MODELS = {
    "openai":"gpt-5-mini-2025-08-07",
    "anthropic": "claude-opus-4-5-20251101"
}

# Get the default model for the current provider
DEFAULT_MODEL = DEFAULT_MODELS.get(API_PROVIDER, DEFAULT_MODELS["openai"])



