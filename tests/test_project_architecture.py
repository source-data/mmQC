#!/usr/bin/env python3
"""Test project architecture and imports after reorganization."""

import unittest

from soda_mmqc import logger
from soda_mmqc.config import (
    PACKAGE_ROOT,
    DATA_DIR,
    CHECKLIST_DIR,
    EXAMPLES_DIR,
    EVALUATION_DIR,
    CACHE_DIR
)


class TestProjectArchitecture(unittest.TestCase):
    """Test the project architecture and imports after reorganization."""
    
    def test_package_structure(self):
        """Test that the package structure is correct."""
        # Check that core modules exist
        self.assertTrue((PACKAGE_ROOT / "core").exists())
        self.assertTrue((PACKAGE_ROOT / "core" / "examples.py").exists())
        self.assertTrue((PACKAGE_ROOT / "core" / "evaluation.py").exists())
        self.assertTrue((PACKAGE_ROOT / "core" / "curation.py").exists())
        
        # Check that lib modules exist
        self.assertTrue((PACKAGE_ROOT / "lib").exists())
        self.assertTrue((PACKAGE_ROOT / "lib" / "api.py").exists())
        self.assertTrue((PACKAGE_ROOT / "lib" / "cache.py").exists())
        
        # Check that scripts exist (CLI entry points)
        self.assertTrue((PACKAGE_ROOT / "scripts").exists())
        self.assertTrue((PACKAGE_ROOT / "scripts" / "run.py").exists())
        self.assertTrue((PACKAGE_ROOT / "scripts" / "curate.py").exists())
        self.assertTrue((PACKAGE_ROOT / "scripts" / "report.py").exists())
        
        # Check that utils exist
        self.assertTrue((PACKAGE_ROOT / "utils").exists())
        self.assertTrue((PACKAGE_ROOT / "utils" / "hash_utils.py").exists())
        
        # Check that data directory exists
        self.assertTrue((PACKAGE_ROOT / "data").exists())
        
        # Check that config and init files exist
        self.assertTrue((PACKAGE_ROOT / "config.py").exists())
        self.assertTrue((PACKAGE_ROOT / "__init__.py").exists())
    
    def test_core_imports(self):
        """Test that core modules can be imported."""
        try:
            from soda_mmqc.core import examples, evaluation, curation
            self.assertTrue(hasattr(examples, 'EXAMPLE_FACTORY'))
            self.assertTrue(hasattr(evaluation, 'FlatEvaluator'))
            self.assertTrue(hasattr(curation, 'load_example_data'))
            logger.info("Core imports successful")
        except ImportError as e:
            self.fail(f"Failed to import core modules: {e}")
    
    def test_lib_imports(self):
        """Test that lib modules can be imported."""
        try:
            from soda_mmqc.lib import api, cache
            self.assertTrue(hasattr(api, 'generate_response'))
            self.assertTrue(hasattr(cache, 'ModelCache'))
            logger.info("Lib imports successful")
        except ImportError as e:
            self.fail(f"Failed to import lib modules: {e}")
    
    def test_scripts_are_launchers_only(self):
        """scripts/ launches things; it holds no library code.

        The rule that makes this checkable: nothing imports from
        soda_mmqc.scripts except cli.py, which calls the two Streamlit
        launchers. Library code that grew here (visualize.py) was dead and
        duplicated soda_mmqc/reporting/.
        """
        from soda_mmqc.scripts import curate, report
        self.assertTrue(callable(curate.main))
        self.assertTrue(callable(report.main))

        scripts_dir = PACKAGE_ROOT / "scripts"
        for retired in ("visualize.py", "check_data.py",
                        "analysis_json_to_html.py"):
            self.assertFalse(
                (scripts_dir / retired).exists(),
                f"{retired} was deleted as dead code; do not restore it "
                "without a caller",
            )
    
    def test_utils_imports(self):
        """Test that utils modules can be imported."""
        try:
            from soda_mmqc.utils import hash_utils
            self.assertTrue(hasattr(hash_utils, 'hash_document_and_json'))
            self.assertTrue(hasattr(hash_utils, 'verify_hash'))
            logger.info("Utils imports successful")
        except ImportError as e:
            self.fail(f"Failed to import utils modules: {e}")
    
    def test_config_paths(self):
        """Test that configuration paths are correct."""
        # Check that all config paths exist or can be created
        self.assertTrue(PACKAGE_ROOT.exists())
        self.assertTrue(DATA_DIR.exists())
        self.assertTrue(CHECKLIST_DIR.exists())
        self.assertTrue(EXAMPLES_DIR.exists())
        self.assertTrue(EVALUATION_DIR.exists())
        
        # CACHE_DIR might not exist initially, but should be creatable
        CACHE_DIR.mkdir(exist_ok=True)
        self.assertTrue(CACHE_DIR.exists())
    
    def test_no_duplicate_modules(self):
        """Test that there are no duplicate modules between core and scripts."""
        core_files = set()
        scripts_files = set()
        
        # Get core module names
        core_dir = PACKAGE_ROOT / "core"
        for file in core_dir.glob("*.py"):
            if file.name != "__init__.py":
                core_files.add(file.stem)
        
        # Get scripts module names
        scripts_dir = PACKAGE_ROOT / "scripts"
        for file in scripts_dir.glob("*.py"):
            if file.name != "__init__.py":
                scripts_files.add(file.stem)
        
        # Check for duplicates
        duplicates = core_files.intersection(scripts_files)
        self.assertEqual(duplicates, set(), 
                        f"Found duplicate modules between core and scripts: {duplicates}")
    
    def test_cli_entry_points(self):
        """Test that CLI entry points are properly configured."""
        # Check that the main CLI functions exist
        try:
            from soda_mmqc.scripts.run import main as run_main
            from soda_mmqc.scripts.run import initialize_main
            from soda_mmqc.scripts.curate import main as curate_main
            
            self.assertTrue(callable(run_main))
            self.assertTrue(callable(initialize_main))
            self.assertTrue(callable(curate_main))
            logger.info("CLI entry points exist and are callable")
        except ImportError as e:
            self.fail(f"Failed to import CLI entry points: {e}")
    
    def test_data_structure(self):
        """Test that the data directory structure is correct."""
        # Check that key data subdirectories exist
        self.assertTrue((DATA_DIR / "checklist").exists())
        self.assertTrue((DATA_DIR / "examples").exists())
        self.assertTrue((DATA_DIR / "evaluation").exists())
        
        # Check that there are some checklists
        checklist_dir = DATA_DIR / "checklist"
        self.assertTrue((checklist_dir / "doc-checklist").exists())
        self.assertTrue((checklist_dir / "fig-checklist").exists())
        
        # Check that there are some examples
        examples_dir = DATA_DIR / "examples"
        example_dirs = list(examples_dir.glob("*"))
        self.assertGreater(len(example_dirs), 0, "No examples found")
    
    def test_logging_setup(self):
        """Test that logging is properly configured."""
        # Check that logger is available
        self.assertIsNotNone(logger)
        self.assertTrue(hasattr(logger, 'info'))
        self.assertTrue(hasattr(logger, 'error'))
        self.assertTrue(hasattr(logger, 'debug'))
        
        # Test that we can log messages
        try:
            logger.info("Test logging message")
            logger.debug("Test debug message")
            logger.error("Test error message")
        except Exception as e:
            self.fail(f"Logging failed: {e}")


class TestNoLegacyDependency(unittest.TestCase):
    """The agentic package must not reach through scripts.run for config.

    `EVALUATION_CONTRACT_FILES` and `owns_evaluation_contracts` are defined
    in config.py; scripts.run only re-exported them. Importing them from
    there made three live modules depend on a module we are deleting.
    """

    def test_list_checks_lives_in_config(self):
        from soda_mmqc.config import list_checks, CHECKLIST_DIR
        checks = list_checks(CHECKLIST_DIR / "fig-checklist")
        self.assertIn("micrograph-scale-bar", checks)
        self.assertTrue(checks["micrograph-scale-bar"].is_dir())

    def test_a_shared_skill_is_not_a_check(self):
        """owns_evaluation_contracts is the discriminator; list_checks must
        use it, or a shared skill beside the checks becomes a phantom."""
        from soda_mmqc.config import list_checks, CHECKLIST_DIR
        root = CHECKLIST_DIR / "fig-checklist"
        for name in list_checks(root):
            self.assertTrue(
                (root / name / "schema.json").is_file(),
                f"{name} was listed as a check but owns no schema.json",
            )

    def test_agentic_does_not_import_scripts_run(self):
        import pathlib
        pkg = pathlib.Path(__file__).resolve().parents[1] / "soda_mmqc"
        offenders = [
            path.name
            for path in (pkg / "agentic").glob("*.py")
            if "scripts.run" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main() 