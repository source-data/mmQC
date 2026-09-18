import os
import tempfile
from pathlib import Path
import logging
from typing import Optional

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
EVALUATION_DIR = DATA_DIR / "evaluation"

# A checklist subdirectory is a check when it owns these files. Everything
# else beside the checks (shared skills, generated docs) is not scoreable and
# must not be enumerated. See owns_evaluation_contracts().
EVALUATION_CONTRACT_FILES = ("schema.json", "benchmark.json")


def owns_evaluation_contracts(candidate_dir: Path) -> bool:
    """Return whether a directory owns a check's evaluation contracts.

    A *check* is a directory that can be scored: it carries the output
    ``schema.json`` and the ``benchmark.json`` naming the examples to score
    against. Shared skills live as flat siblings of the checks in the same
    checklist directory and carry at most a runtime ``schema.json``, so they
    are not checks -- not because a name convention or marker file filters
    them out, but because there is nothing to score.

    ``eval-manifest.json`` is deliberately not part of this test. It is
    required when scoring, but several legacy checklists predate it and must
    keep enumerating as they do today.

    This lives in config so that every enumerator -- the runner and the
    curation UI -- shares one definition of what a check is.
    """
    if not candidate_dir.is_dir():
        return False
    return all(
        (candidate_dir / name).is_file()
        for name in EVALUATION_CONTRACT_FILES
    )


# Default model/API options when a check has no model_config.json
DEFAULT_MODEL_CONFIG_PATH = DATA_DIR / "model_config.json"

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
#    join the session -- see AGENTIC_SETTING_SOURCES.
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

#: Directory name the runtime is assembled into, under AGENTIC_RUNTIME_DIR.
AGENTIC_RUNTIME_PREFIX = "soda-mmqc-agentic-"

#: Where the SDK expects to find skills, relative to the runtime root.
AGENTIC_SKILLS_SUBDIR = Path(".claude") / "skills"

#: Where the session writes intermediate artifacts and the final prediction,
#: relative to the runtime root. The only writable location in the profile.
AGENTIC_ARTIFACTS_SUBDIR = Path("artifacts")

#: Where the current example's inputs are copied, relative to the runtime root.
AGENTIC_INPUT_SUBDIR = Path("input")

#: The generated per-run orientation file, relative to the runtime root.
AGENTIC_ORIENTATION_FILENAME = "ORIENTATION.md"

#: Setting sources passed to the SDK session.
#:
#: **"user" is deliberately absent.** It is what loads `~/.claude/skills/`,
#: which has nothing to do with this repository and would put whatever the
#: operator happens to have installed into a scored run -- silently, and
#: differently on every machine. Only "project" is used, and because the
#: runtime root is outside any repository, that resolves to exactly the
#: skills assembled under the runtime root.
#:
#: Widening this is a containment change and needs the same scrutiny as
#: widening the tool allowlist.
AGENTIC_SETTING_SOURCES = ("project",)

# ---------------------------------------------------------------------------
# Agentic permission profile
# ---------------------------------------------------------------------------
#
# Deny by default. The session may do exactly three things: read inside the
# runtime, write inside the runtime's artifacts directory, and invoke a skill.
#
# Three facts from the Agent SDK's permission documentation shape this, and
# each one invalidates an obvious-looking construction:
#
# 1. `allowed_tools` is NOT an allowlist. It is a list of *auto-approvals*.
#    "Any other tool not listed in allowed_tools is still available to Claude,
#    and a call to it that needs approval falls through to the permission mode
#    and canUseTool." So listing three tools does not remove the rest.
#
# 2. `permission_mode="dontAsk"` is what turns it into one: "Any call that
#    would otherwise prompt is denied [...] canUseTool is never called." The
#    documentation names `allowed_tools` + `dontAsk` as *the* locked-down
#    pairing. `default` -- what this profile used first -- leaves unlisted
#    tools falling through to a callback that does not exist.
#
# 3. Even under `dontAsk`, some calls "need no approval" and run regardless:
#    read-only shell commands, file reads inside the working directory, and
#    "tools like Agent that don't ask before running". The only way to put a
#    tool out of reach is a bare name in `disallowed_tools`, which removes it
#    from the model's context entirely. That is why the denials below are not
#    redundant with the allowlist -- for `Agent` in particular they are the
#    only thing that works.

#: Tool names the session may use. The rules actually passed to the SDK are
#: built per-runtime by cli.session_options(), because two of the three are
#: scoped to paths that only exist once a runtime is assembled.
#:
#: `Edit` rather than `Write` is deliberate and is a documented trap:
#: "Edit(path) rules govern all built-in tools that write files, including
#: Write and NotebookEdit; a Write(path) rule is never matched by the file
#: permission checks." A scoped `Write(...)` rule would silently match nothing.
AGENTIC_ALLOWED_TOOL_NAMES = ("Read", "Edit", "Skill")

#: Tools removed from the model's context entirely, each for a specific
#: reason. Bare names are required: a scoped rule leaves the tool available.
AGENTIC_FORBIDDEN_TOOLS = {
    # Shell and code execution: would let the session leave the runtime
    # directory entirely, making every other control cosmetic. Note that
    # read-only shell commands are auto-approved even under dontAsk, so the
    # bare-name denial is the only thing that actually removes Bash.
    "Bash": "shell access escapes the sealed runtime",
    "BashOutput": "shell access escapes the sealed runtime",
    "KillShell": "shell access escapes the sealed runtime",
    "NotebookEdit": "executes code",
    # Subagents: a spawned agent negotiates its own context and permissions,
    # which reopens containment from another direction, and its skill calls
    # do not appear in this session's trace -- so the per-example record of
    # which skills actually fired would be incomplete. The SDK documents
    # `Agent` as running without asking, so only a bare-name denial stops it.
    "Task": "subagents reopen containment and break the Skill trace",
    "Agent": "subagents reopen containment and break the Skill trace",
    # Network: nothing in a figure check needs the internet, and a fetch is
    # both an exfiltration path for gold-derived content and a source of
    # irreproducibility between runs.
    "WebFetch": "no network capability is justified by any skill's needs",
    "WebSearch": "no network capability is justified by any skill's needs",
    # --- Added 2026-09-14 after observing the SDK's *reported* tool set ---
    # The first live session reported 20 tools where this profile names 3.
    # `allowed_tools` auto-approves; it does not remove. Everything below was
    # present in the model's context and none of it was considered when the
    # profile was written -- which is precisely why gate 3B asks for the
    # reported set rather than trusting the allowlist.
    #
    # Egress and persistence. These are the serious ones: a session that can
    # message, notify or schedule can move gold-derived content out of the
    # runtime and can act after the run is over.
    "SendMessage": "egress path out of the sealed runtime",
    "PushNotification": "egress path out of the sealed runtime",
    "ScheduleWakeup": "would let the session act after the run ends",
    "CronCreate": "would let the session act after the run ends",
    "CronDelete": "scheduling surface, unused by any check",
    "CronList": "scheduling surface, unused by any check",
    "Monitor": "background observation, unused by any check",
    "Workflow": "orchestration surface, unused by any check",
    # Filesystem navigation beyond the runtime.
    "EnterWorktree": "moves the session out of the sealed runtime",
    "ExitWorktree": "moves the session out of the sealed runtime",
    # Discovery surfaces. Gate 3B decided Read/Edit/Skill is sufficient, so
    # these are excluded by that decision rather than by a new one.
    "Glob": "gate 3B: Read/Write/Skill is sufficient",
    "Grep": "gate 3B: Read/Write/Skill is sufficient",
    "ToolSearch": "tool discovery, unused by any check",
    "ListAgents": "agent enumeration; subagents are already denied",
    "DesignSync": "unused by any check",
    "ReportFindings": "unused by any check",
    # NOTE: `Write` is deliberately NOT denied. The session must create
    # prediction.json, and the SDK documents `Edit(path)` as governing every
    # file-writing tool including `Write` -- so the scoped Edit rule confines
    # it to the artifacts directory. Denying it by name would leave only
    # `Edit`, which cannot create a file that does not yet exist.
}

#: Model for agentic sessions.
#:
#: Deliberately separate from DEFAULT_MODEL, which follows API_PROVIDER and
#: resolves to an OpenAI model by default -- the agentic runner drives Claude
#: Code and cannot use one. The bare alias tracks the current Sonnet rather
#: than pinning a dated snapshot; Sonnet rather than Opus because the first
#: runs are small and diagnostic, and cost should not discourage rerunning
#: them. Model choice is a gate 4C decision, so overriding it is explicit.
AGENTIC_DEFAULT_MODEL = os.getenv("SODA_MMQC_AGENTIC_MODEL", "sonnet")

#: Permission mode. `dontAsk` denies anything that would otherwise prompt,
#: which is what makes the scoped allowlist total. The runtime is unattended,
#: so there is no human to prompt anyway -- and `default` would leave unlisted
#: tools resolving through a `canUseTool` callback that is not supplied.
#:
#: Consequence worth knowing: under `dontAsk` the SDK never calls
#: `canUseTool`, so per-call human approval cannot be layered on top of this
#: mode. Interactive review has to come from a `PreToolUse` hook, which runs
#: before every other step in every mode. See the milestone 3 results doc.
AGENTIC_PERMISSION_MODE = "dontAsk"

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



