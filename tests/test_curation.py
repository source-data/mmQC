import os
import json
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

from soda_mmqc.core.curation import (
    load_checklist,
    load_example_data,
    get_example_hierarchy,
    get_document_examples,
    get_example_class,
    save_check_output,
    build_document_viewer_html,
    _extract_body_html,
    get_word_docx_path,
    word_example_cache_key,
    load_cached_word_example,
)
from soda_mmqc.config import CHECKLIST_DIR, EXAMPLES_DIR


class TestCuration(unittest.TestCase):
    """Test cases for the curation module."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test checklist
        self.test_dir = tempfile.mkdtemp()
        self.test_checklist_dir = Path(self.test_dir) / "test-checklist"
        self.test_checklist_dir.mkdir()
        
        # Create a test check directory structure
        self.test_check_dir = self.test_checklist_dir / "test-check"
        self.test_check_dir.mkdir()
        
        # Create schema.json
        self.test_schema = {
            "format": {
                "name": "test-check",
                "description": "Test check for unit testing",
                "schema": {
                    "type": "object",
                    "properties": {
                        "outputs": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "test_field": {"type": "string"},
                                    "test_number": {"type": "number"}
                                },
                                "required": ["test_field"]
                            }
                        }
                    },
                    "required": ["outputs"]
                }
            }
        }
        
        schema_file = self.test_check_dir / "schema.json"
        with open(schema_file, "w") as f:
            json.dump(self.test_schema, f, indent=2)
        
        # Create benchmark.json
        self.test_benchmark = {
            "name": "test-check",
            "description": "Test benchmark",
            "metrics": ["accuracy", "precision"]
        }
        
        benchmark_file = self.test_check_dir / "benchmark.json"
        with open(benchmark_file, "w") as f:
            json.dump(self.test_benchmark, f, indent=2)
        
        # Create prompts directory and files
        prompts_dir = self.test_check_dir / "prompts"
        prompts_dir.mkdir()
        
        prompt1_content = "This is test prompt 1"
        prompt1_file = prompts_dir / "prompt.1.txt"
        with open(prompt1_file, "w") as f:
            f.write(prompt1_content)
        
        prompt2_content = "This is test prompt 2"
        prompt2_file = prompts_dir / "prompt.2.txt"
        with open(prompt2_file, "w") as f:
            f.write(prompt2_content)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.test_dir)

    def test_save_check_output_with_actual_data(self):
        """Test save_check_output with actual data from EXAMPLES_DIR."""
        # Check if EXAMPLES_DIR exists
        if not EXAMPLES_DIR.exists():
            self.skipTest(f"EXAMPLES_DIR does not exist: {EXAMPLES_DIR}")
        
        # Find a valid example to test with
        example_dirs = [d for d in EXAMPLES_DIR.iterdir() if d.is_dir()]
        if not example_dirs:
            self.skipTest(f"No example directories found in {EXAMPLES_DIR}")
        
        # Find a doc_id directory with content subdirectories
        doc_id = None
        fig_path = None
        
        for doc_dir in example_dirs:
            content_dir = doc_dir / "content"
            if content_dir.exists():
                # Look for figure directories (numeric names)
                for fig_dir in content_dir.iterdir():
                    if fig_dir.is_dir() and fig_dir.name.isdigit():
                        doc_id = doc_dir.name
                        fig_path = fig_dir
                        break
                if doc_id and fig_path:
                    break
        
        if not doc_id or not fig_path:
            self.skipTest("No valid figure examples found")
        
        # Test the function with actual data
        output_data = {
            "outputs": [
                {"test_field": "test_value", "test_number": 42}
            ],
            "updated_at": "2024-01-01T00:00:00Z"
        }
        
        result = save_check_output(fig_path, "test-check", output_data)
        
        # The function should return True (success)
        self.assertTrue(result)
        
        # Verify the expected output file was created
        expected_output_file = fig_path / "checks" / "test-check" / "expected_output.json"
        self.assertTrue(expected_output_file.exists())
        
        # Verify the content
        with open(expected_output_file, "r") as f:
            saved_data = json.load(f)
        
        self.assertEqual(saved_data["outputs"], output_data["outputs"])
        self.assertEqual(saved_data["updated_at"], output_data["updated_at"])
        
        # Clean up - remove the test file
        import shutil
        shutil.rmtree(fig_path / "checks" / "test-check")

    def test_save_check_output_with_invalid_path(self):
        """Test save_check_output with an invalid path."""
        # Test with a non-existent path
        invalid_path = Path("/nonexistent/path")
        output_data = {"outputs": [], "updated_at": "2024-01-01T00:00:00Z"}
        
        result = save_check_output(invalid_path, "test-check", output_data)
        
        # Should return False for invalid paths
        self.assertFalse(result)

    def test_save_check_output_overwrite_parameter(self):
        """Test that save_check_output respects the overwrite parameter."""
        # Check if EXAMPLES_DIR exists
        if not EXAMPLES_DIR.exists():
            self.skipTest(f"EXAMPLES_DIR does not exist: {EXAMPLES_DIR}")
        
        # Find a valid example to test with
        example_dirs = [d for d in EXAMPLES_DIR.iterdir() if d.is_dir()]
        if not example_dirs:
            self.skipTest(f"No example directories found in {EXAMPLES_DIR}")
        
        # Find a doc_id directory with content subdirectories
        doc_id = None
        fig_path = None
        
        for doc_dir in example_dirs:
            content_dir = doc_dir / "content"
            if content_dir.exists():
                # Look for figure directories (numeric names)
                for fig_dir in content_dir.iterdir():
                    if fig_dir.is_dir() and fig_dir.name.isdigit():
                        doc_id = doc_dir.name
                        fig_path = fig_dir
                        break
                if doc_id and fig_path:
                    break
        
        if not doc_id or not fig_path:
            self.skipTest("No valid figure examples found")
        
        # Test with overwrite=True (should always save)
        output_data_1 = {
            "outputs": [{"test_field": "value1"}],
            "updated_at": "2024-01-01T00:00:00Z"
        }
        
        result_1 = save_check_output(fig_path, "test-check-overwrite", output_data_1)
        self.assertTrue(result_1)
        
        # Test with overwrite=True again (should overwrite)
        output_data_2 = {
            "outputs": [{"test_field": "value2"}],
            "updated_at": "2024-01-01T01:00:00Z"
        }
        
        result_2 = save_check_output(fig_path, "test-check-overwrite", output_data_2)
        self.assertTrue(result_2)
        
        # Verify the file was overwritten with the new data
        expected_output_file = fig_path / "checks" / "test-check-overwrite" / "expected_output.json"
        self.assertTrue(expected_output_file.exists())
        
        with open(expected_output_file, "r") as f:
            saved_data = json.load(f)
        
        self.assertEqual(saved_data["outputs"], output_data_2["outputs"])
        self.assertEqual(saved_data["updated_at"], output_data_2["updated_at"])
        
        # Clean up
        import shutil
        shutil.rmtree(fig_path / "checks" / "test-check-overwrite")

    def test_get_example_hierarchy_with_test_data(self):
        """Test get_example_hierarchy with temporary test data."""
        # Create a test examples directory structure
        test_examples_dir = Path(tempfile.mkdtemp())
        try:
            # Create a doc_id directory
            doc_id_dir = test_examples_dir / "test-doc-123"
            doc_id_dir.mkdir()
            
            # Create content directory
            content_dir = doc_id_dir / "content"
            content_dir.mkdir()
            
            # Create figure directories (numeric)
            fig1_dir = content_dir / "1"
            fig1_dir.mkdir()
            fig2_dir = content_dir / "2"
            fig2_dir.mkdir()
            
            # Create non-figure directories (should be ignored)
            checks_dir = content_dir / "checks"
            checks_dir.mkdir()
            other_dir = content_dir / "other"
            other_dir.mkdir()
            
            # Create another doc_id directory
            doc_id_dir2 = test_examples_dir / "test-doc-456"
            doc_id_dir2.mkdir()
            content_dir2 = doc_id_dir2 / "content"
            content_dir2.mkdir()
            fig3_dir = content_dir2 / "3"
            fig3_dir.mkdir()
            
            # Test the function
            hierarchy = get_example_hierarchy(test_examples_dir)
            
            # Verify the structure
            self.assertIn("test-doc-123", hierarchy)
            self.assertIn("test-doc-456", hierarchy)
            
            # Verify only numeric figure directories are included
            doc1_figures = [f.name for f in hierarchy["test-doc-123"]]
            doc2_figures = [f.name for f in hierarchy["test-doc-456"]]
            
            self.assertEqual(set(doc1_figures), {"1", "2"})
            self.assertEqual(set(doc2_figures), {"3"})
            
            # Verify non-figure directories are excluded
            self.assertNotIn("checks", doc1_figures)
            self.assertNotIn("other", doc1_figures)
            
        finally:
            import shutil
            shutil.rmtree(test_examples_dir)

    def test_get_example_hierarchy_with_actual_data(self):
        """Test get_example_hierarchy with actual data from EXAMPLES_DIR."""
        # Check if EXAMPLES_DIR exists
        if not EXAMPLES_DIR.exists():
            self.skipTest(f"EXAMPLES_DIR does not exist: {EXAMPLES_DIR}")
        
        # Test with actual data
        hierarchy = get_example_hierarchy(EXAMPLES_DIR)
        
        # Verify the hierarchy is not empty
        self.assertIsInstance(hierarchy, dict)
        self.assertGreater(len(hierarchy), 0)
        
        # Verify each doc_id has a list of figure paths
        for doc_id, figure_paths in hierarchy.items():
            self.assertIsInstance(doc_id, str)
            self.assertIsInstance(figure_paths, list)
            
            # Verify all figure paths are Path objects
            for fig_path in figure_paths:
                self.assertIsInstance(fig_path, Path)
                
                # Verify the path structure is correct (relative paths)
                # Should be: doc_id/content/figure_id
                path_parts = fig_path.parts
                self.assertEqual(len(path_parts), 3)  # doc_id/content/figure_id
                self.assertEqual(path_parts[1], "content")
                self.assertEqual(path_parts[0], doc_id)
                
                # Verify figure names are numeric (typical figure IDs)
                self.assertTrue(path_parts[2].isdigit(), 
                              f"Figure name '{path_parts[2]}' is not numeric")
                
                # Verify the relative path resolves to an existing directory
                full_path = EXAMPLES_DIR / fig_path
                self.assertTrue(full_path.exists())

    def test_get_example_hierarchy_with_empty_directory(self):
        """Test get_example_hierarchy with an empty directory."""
        empty_dir = Path(tempfile.mkdtemp())
        try:
            hierarchy = get_example_hierarchy(empty_dir)
            self.assertEqual(hierarchy, {})
        finally:
            import shutil
            shutil.rmtree(empty_dir)

    def test_get_example_hierarchy_with_no_content_directories(self):
        """Test get_example_hierarchy with doc directories that have no content subdirectory."""
        test_dir = Path(tempfile.mkdtemp())
        try:
            # Create a doc_id directory without content
            doc_id_dir = test_dir / "test-doc"
            doc_id_dir.mkdir()
            
            # Create some other directories
            other_dir = doc_id_dir / "other"
            other_dir.mkdir()
            
            hierarchy = get_example_hierarchy(test_dir)
            
            # Should include the doc_id but with empty list since no content directory exists
            self.assertIn("test-doc", hierarchy)
            self.assertEqual(hierarchy["test-doc"], [])
            
        finally:
            import shutil
            shutil.rmtree(test_dir)

    def test_get_example_hierarchy_with_empty_content_directories(self):
        """Test get_example_hierarchy with content directories that have no figure directories."""
        test_dir = Path(tempfile.mkdtemp())
        try:
            # Create a doc_id directory with empty content
            doc_id_dir = test_dir / "test-doc"
            doc_id_dir.mkdir()
            content_dir = doc_id_dir / "content"
            content_dir.mkdir()
            
            hierarchy = get_example_hierarchy(test_dir)
            
            # Should have the doc_id but no figures
            self.assertIn("test-doc", hierarchy)
            self.assertEqual(hierarchy["test-doc"], [])
            
        finally:
            import shutil
            shutil.rmtree(test_dir)

    def test_get_example_hierarchy_with_non_numeric_figure_directories(self):
        """Test get_example_hierarchy with non-numeric figure directories (should be ignored)."""
        test_dir = Path(tempfile.mkdtemp())
        try:
            # Create a doc_id directory
            doc_id_dir = test_dir / "test-doc"
            doc_id_dir.mkdir()
            content_dir = doc_id_dir / "content"
            content_dir.mkdir()
            
            # Create non-numeric directories (should be ignored)
            non_numeric_dir = content_dir / "figure1"
            non_numeric_dir.mkdir()
            alpha_dir = content_dir / "abc"
            alpha_dir.mkdir()
            
            # Create one numeric directory (should be included)
            numeric_dir = content_dir / "1"
            numeric_dir.mkdir()
            
            hierarchy = get_example_hierarchy(test_dir)
            
            # Should only include the numeric directory
            self.assertIn("test-doc", hierarchy)
            figure_names = [f.name for f in hierarchy["test-doc"]]
            self.assertEqual(set(figure_names), {"1"})
            self.assertNotIn("figure1", figure_names)
            self.assertNotIn("abc", figure_names)
            
        finally:
            import shutil
            shutil.rmtree(test_dir)

    def test_load_checklist_with_test_data(self):
        """Test load_checklist with temporary test data."""
        checklist = load_checklist(self.test_checklist_dir)
        
        # Verify the structure
        self.assertIn("test-check", checklist)
        self.assertIn("schema", checklist["test-check"])
        self.assertIn("benchmark", checklist["test-check"])
        self.assertIn("prompts", checklist["test-check"])
        
        # Verify schema content
        self.assertEqual(
            checklist["test-check"]["schema"]["format"]["name"],
            "test-check"
        )
        
        # Verify benchmark content
        self.assertEqual(
            checklist["test-check"]["benchmark"]["name"],
            "test-check"
        )
        
        # Verify prompts content
        self.assertIn("prompt.1.txt", checklist["test-check"]["prompts"])
        self.assertIn("prompt.2.txt", checklist["test-check"]["prompts"])
        self.assertEqual(
            checklist["test-check"]["prompts"]["prompt.1.txt"],
            "This is test prompt 1"
        )
        self.assertEqual(
            checklist["test-check"]["prompts"]["prompt.2.txt"],
            "This is test prompt 2"
        )

    def test_load_checklist_with_actual_data(self):
        """Test load_checklist with actual checklist data from CHECKLIST_DIR."""
        # Check if CHECKLIST_DIR exists
        if not CHECKLIST_DIR.exists():
            self.skipTest(f"CHECKLIST_DIR does not exist: {CHECKLIST_DIR}")
        
        # Get the first available checklist
        checklist_dirs = [
            d for d in CHECKLIST_DIR.iterdir() if d.is_dir()
        ]
        if not checklist_dirs:
            self.skipTest(
                f"No checklist directories found in {CHECKLIST_DIR}"
            )
        
        # Test with the first checklist directory
        test_checklist_dir = checklist_dirs[0]
        checklist = load_checklist(test_checklist_dir)
        
        # Verify the checklist is not empty
        self.assertIsInstance(checklist, dict)
        self.assertGreater(len(checklist), 0)
        
        # Verify each check has the expected structure
        for check_name, check_data in checklist.items():
            self.assertIsInstance(check_name, str)
            self.assertIsInstance(check_data, dict)
            
            # Verify required keys exist
            self.assertIn("schema", check_data)
            self.assertIn("benchmark", check_data)
            self.assertIn("prompts", check_data)
            
            # Verify schema structure
            if check_data["schema"]:  # Skip if schema is empty
                self.assertIn("format", check_data["schema"])
                self.assertIn("name", check_data["schema"]["format"])
                # Verify schema name matches directory name
                schema_name = check_data["schema"]["format"]["name"]
                self.assertEqual(schema_name, check_name)
            
            # Verify benchmark structure
            if check_data["benchmark"]:  # Skip if benchmark is empty
                self.assertIsInstance(check_data["benchmark"], dict)
            
            # Verify prompts structure
            self.assertIsInstance(check_data["prompts"], dict)
            # Verify all prompt files are text content
            for prompt_name, prompt_content in check_data["prompts"].items():
                self.assertTrue(prompt_name.endswith(".txt"))
                self.assertIsInstance(prompt_content, str)
                self.assertGreater(len(prompt_content), 0)

    def test_load_checklist_with_missing_files(self):
        """A directory missing the evaluation contracts is not a check.

        Previously any subdirectory was loaded, with empty schema/benchmark
        dicts. A check is now a directory that owns schema.json *and*
        benchmark.json, so that a shared skill sitting beside the checks
        cannot appear in the curation check selector as a phantom entry.
        The entry this used to produce was unusable anyway: it carried no
        schema to render an output table from.
        """
        # Create a check directory without schema and benchmark files
        incomplete_check_dir = self.test_checklist_dir / "incomplete-check"
        incomplete_check_dir.mkdir()
        
        # Create prompts directory
        prompts_dir = incomplete_check_dir / "prompts"
        prompts_dir.mkdir()
        
        # Create a prompt file
        prompt_file = prompts_dir / "prompt.1.txt"
        with open(prompt_file, "w") as f:
            f.write("Test prompt")
        
        checklist = load_checklist(self.test_checklist_dir)
        
        # Owns neither contract: not a check.
        self.assertNotIn("incomplete-check", checklist)
        
        # The real checks in the fixture are unaffected.
        self.assertIn("test-check", checklist)

    def test_load_checklist_skips_empty_schema_file(self):
        """Test load_checklist skips checks with empty schema.json."""
        empty_schema_dir = self.test_checklist_dir / "empty-schema-check"
        empty_schema_dir.mkdir()
        (empty_schema_dir / "schema.json").write_text("")
        (empty_schema_dir / "benchmark.json").write_text(
            json.dumps({"example_class": "word", "examples": []})
        )

        with patch("soda_mmqc.core.curation.st.warning") as mock_warning:
            checklist = load_checklist(self.test_checklist_dir)

        self.assertNotIn("empty-schema-check", checklist)
        mock_warning.assert_any_call(
            "Skipping check 'empty-schema-check': schema.json is empty or invalid"
        )

    def test_load_checklist_with_empty_directory(self):
        """Test load_checklist with an empty checklist directory."""
        empty_dir = Path(tempfile.mkdtemp())
        try:
            checklist = load_checklist(empty_dir)
            self.assertEqual(checklist, {})
        finally:
            import shutil
            shutil.rmtree(empty_dir)

    def test_load_checklist_with_non_directory_items(self):
        """Test load_checklist with non-directory items in checklist directory."""
        # Create a file in the checklist directory
        test_file = self.test_checklist_dir / "test_file.txt"
        with open(test_file, "w") as f:
            f.write("This is a test file")
        
        checklist = load_checklist(self.test_checklist_dir)
        
        # Verify only directories are processed
        self.assertIn("test-check", checklist)
        self.assertNotIn("test_file.txt", checklist)

    def test_load_checklist_schema_name_validation(self):
        """Test that schema name validation works correctly."""
        # Create a check with mismatched schema name
        mismatched_check_dir = self.test_checklist_dir / "mismatched-check"
        mismatched_check_dir.mkdir()
        
        mismatched_schema = {
            "format": {
                "name": "different-name",  # Different from directory name
                "description": "Test check",
                "schema": {"type": "object", "properties": {}}
            }
        }
        
        schema_file = mismatched_check_dir / "schema.json"
        with open(schema_file, "w") as f:
            json.dump(mismatched_schema, f, indent=2)
        
        # benchmark.json is required for the directory to count as a check at
        # all; without it the name mismatch below would never be reached.
        benchmark_file = mismatched_check_dir / "benchmark.json"
        with open(benchmark_file, "w") as f:
            json.dump({"name": "mismatched-check", "examples": []}, f, indent=2)
        
        # The function should still load the checklist but log an error
        # We can't easily test the st.error call, but we can verify the data
        # is loaded
        checklist = load_checklist(self.test_checklist_dir)
        
        self.assertIn("mismatched-check", checklist)
        self.assertIn("schema", checklist["mismatched-check"])

    def test_load_example_data_with_actual_data(self):
        """Test load_example_data with actual example data from EXAMPLES_DIR."""
        # Check if EXAMPLES_DIR exists
        if not EXAMPLES_DIR.exists():
            self.skipTest(f"EXAMPLES_DIR does not exist: {EXAMPLES_DIR}")
        
        # Find a valid example directory structure
        example_dirs = [d for d in EXAMPLES_DIR.iterdir() if d.is_dir()]
        if not example_dirs:
            self.skipTest(f"No example directories found in {EXAMPLES_DIR}")
        
        # Find a doc_id directory with content subdirectories
        doc_id = None
        fig_path = None
        
        for doc_dir in example_dirs:
            content_dir = doc_dir / "content"
            if content_dir.exists():
                # Look for figure directories (numeric names)
                for fig_dir in content_dir.iterdir():
                    if fig_dir.is_dir() and fig_dir.name.isdigit():
                        doc_id = doc_dir.name
                        fig_path = fig_dir
                        break
                if doc_id and fig_path:
                    break
        
        if not doc_id or not fig_path:
            self.skipTest("No valid figure examples found")
        
        # Test with actual data
        example_data = load_example_data(fig_path)
        
        # Verify the example data is loaded correctly
        self.assertIsNotNone(example_data)
        self.assertIsInstance(example_data, dict)
        
        # Verify required fields exist
        self.assertIn("doc_id", example_data)
        self.assertIn("figure_id", example_data)
        self.assertIn("caption", example_data)
        self.assertIn("image_path", example_data)
        self.assertIn("check_outputs", example_data)
        
        # Verify the values are correct
        self.assertEqual(example_data["doc_id"], doc_id)
        self.assertEqual(example_data["figure_id"], fig_path.name)
        self.assertIsInstance(example_data["caption"], str)
        self.assertGreater(len(example_data["caption"]), 0)
        
        # Verify image path exists
        if example_data["image_path"]:
            self.assertTrue(Path(example_data["image_path"]).exists())
        
        # Verify check_outputs is a dictionary
        self.assertIsInstance(example_data["check_outputs"], dict)

    def test_load_example_data_with_checklist_filtering(self):
        """Test load_example_data with checklist filtering."""
        # Check if EXAMPLES_DIR exists
        if not EXAMPLES_DIR.exists():
            self.skipTest(f"EXAMPLES_DIR does not exist: {EXAMPLES_DIR}")
        
        # Find a valid example
        example_dirs = [d for d in EXAMPLES_DIR.iterdir() if d.is_dir()]
        if not example_dirs:
            self.skipTest(f"No example directories found in {EXAMPLES_DIR}")
        
        doc_id = None
        fig_path = None
        
        for doc_dir in example_dirs:
            content_dir = doc_dir / "content"
            if content_dir.exists():
                for fig_dir in content_dir.iterdir():
                    if fig_dir.is_dir() and fig_dir.name.isdigit():
                        doc_id = doc_dir.name
                        fig_path = fig_dir
                        break
                if doc_id and fig_path:
                    break
        
        if not doc_id or not fig_path:
            self.skipTest("No valid figure examples found")
        
        # Create a mock checklist with only one check
        mock_checklist = {"test-check": {}}
        
        # Test with checklist filtering
        example_data = load_example_data(fig_path, mock_checklist)
        
        # Verify the example data is loaded
        self.assertIsNotNone(example_data)
        self.assertIsInstance(example_data, dict)
        
        # Verify that only checks in the checklist are loaded
        # (if there are any existing checks, they should be filtered out)
        for check_name in example_data["check_outputs"].keys():
            self.assertIn(check_name, mock_checklist)

    def test_load_example_data_with_nonexistent_path(self):
        """Test load_example_data with a nonexistent figure path."""
        # Test with a path that doesn't exist
        nonexistent_path = Path("/nonexistent/path")
        example_data = load_example_data(nonexistent_path)
        
        # Should return None for nonexistent paths
        self.assertIsNone(example_data)

    def test_load_example_data_with_invalid_structure(self):
        """Test load_example_data with invalid directory structure."""
        # Create a temporary directory with invalid structure
        temp_dir = Path(tempfile.mkdtemp())
        try:
            # Create a directory without the required content structure
            invalid_fig_dir = temp_dir / "invalid-fig"
            invalid_fig_dir.mkdir()
            
            example_data = load_example_data(invalid_fig_dir)
            
            # Should return None for invalid structure
            self.assertIsNone(example_data)
        finally:
            import shutil
            shutil.rmtree(temp_dir)

    def test_load_checklist_with_empty_prompts_directory(self):
        """Test load_checklist with a check that has an empty prompts directory."""
        # Create a check directory with empty prompts
        empty_prompts_check_dir = self.test_checklist_dir / "empty-prompts-check"
        empty_prompts_check_dir.mkdir()
        
        # Create schema.json
        schema = {
            "format": {
                "name": "empty-prompts-check",
                "description": "Test check with empty prompts",
                "schema": {"type": "object", "properties": {}}
            }
        }
        
        schema_file = empty_prompts_check_dir / "schema.json"
        with open(schema_file, "w") as f:
            json.dump(schema, f, indent=2)
        
        # Create benchmark.json
        benchmark = {
            "name": "empty-prompts-check",
            "description": "Test benchmark"
        }
        
        benchmark_file = empty_prompts_check_dir / "benchmark.json"
        with open(benchmark_file, "w") as f:
            json.dump(benchmark, f, indent=2)
        
        # Create empty prompts directory (no files)
        prompts_dir = empty_prompts_check_dir / "prompts"
        prompts_dir.mkdir()
        
        checklist = load_checklist(self.test_checklist_dir)
        
        # Verify the check is loaded
        self.assertIn("empty-prompts-check", checklist)
        
        # Verify prompts dictionary is empty
        self.assertEqual(checklist["empty-prompts-check"]["prompts"], {})
        
        # Verify other components are loaded
        self.assertIn("schema", checklist["empty-prompts-check"])
        self.assertIn("benchmark", checklist["empty-prompts-check"])

    def test_load_checklist_with_missing_prompts_directory(self):
        """Test load_checklist with a check that has no prompts directory."""
        # Create a check directory without prompts
        no_prompts_check_dir = self.test_checklist_dir / "no-prompts-check"
        no_prompts_check_dir.mkdir()
        
        # Create schema.json
        schema = {
            "format": {
                "name": "no-prompts-check",
                "description": "Test check without prompts directory",
                "schema": {"type": "object", "properties": {}}
            }
        }
        
        schema_file = no_prompts_check_dir / "schema.json"
        with open(schema_file, "w") as f:
            json.dump(schema, f, indent=2)
        
        # Create benchmark.json
        benchmark = {
            "name": "no-prompts-check",
            "description": "Test benchmark"
        }
        
        benchmark_file = no_prompts_check_dir / "benchmark.json"
        with open(benchmark_file, "w") as f:
            json.dump(benchmark, f, indent=2)
        
        # Don't create prompts directory at all
        
        checklist = load_checklist(self.test_checklist_dir)
        
        # Verify the check is loaded
        self.assertIn("no-prompts-check", checklist)
        
        # Verify prompts dictionary is empty
        self.assertEqual(checklist["no-prompts-check"]["prompts"], {})
        
        # Verify other components are loaded
        self.assertIn("schema", checklist["no-prompts-check"])
        self.assertIn("benchmark", checklist["no-prompts-check"])

    def test_get_example_class_from_benchmark(self):
        checklist = {
            "url-check": {
                "benchmark": {"example_class": "word"},
            }
        }
        self.assertEqual(get_example_class(checklist), "word")

    def test_get_example_class_defaults_to_figure(self):
        self.assertEqual(get_example_class({}), "figure")

    def test_get_document_examples_from_benchmark_list(self):
        test_examples_dir = Path(tempfile.mkdtemp())
        try:
            for doc_id in ("doc-a", "doc-b", "missing-doc"):
                if doc_id != "missing-doc":
                    (test_examples_dir / doc_id / "content").mkdir(parents=True)

            checklist = {
                "url-check": {
                    "benchmark": {
                        "example_class": "word",
                        "examples": ["doc-b", "doc-a", "missing-doc"],
                    }
                }
            }

            doc_ids = get_document_examples(test_examples_dir, checklist)
            self.assertEqual(doc_ids, ["doc-a", "doc-b"])
        finally:
            shutil.rmtree(test_examples_dir)

    def test_get_document_examples_empty_benchmark_list(self):
        test_examples_dir = Path(tempfile.mkdtemp())
        try:
            (test_examples_dir / "discovered-doc" / "content").mkdir(parents=True)
            (test_examples_dir / "discovered-doc" / "content" / "paper.docx").write_bytes(
                b"PK\x03\x04"
            )
            checks_dir = test_examples_dir / "discovered-doc" / "checks" / "url-check"
            checks_dir.mkdir(parents=True)
            (checks_dir / "expected_output.json").write_text("{}")

            checklist = {
                "url-check": {
                    "benchmark": {
                        "example_class": "word",
                        "examples": [],
                    }
                }
            }

            doc_ids = get_document_examples(test_examples_dir, checklist)
            self.assertEqual(doc_ids, [])
        finally:
            shutil.rmtree(test_examples_dir)

    def test_get_document_examples_discovers_from_layout(self):
        test_examples_dir = Path(tempfile.mkdtemp())
        try:
            doc_dir = test_examples_dir / "EMBOJ-2024-119734R"
            content_dir = doc_dir / "content"
            content_dir.mkdir(parents=True)
            (content_dir / "paper.docx").write_bytes(b"PK\x03\x04")
            checks_dir = doc_dir / "checks" / "url-check"
            checks_dir.mkdir(parents=True)
            (checks_dir / "expected_output.json").write_text("{}")

            checklist = {"url-check": {"benchmark": {}}}
            doc_ids = get_document_examples(test_examples_dir, checklist)
            self.assertEqual(doc_ids, ["EMBOJ-2024-119734R"])
        finally:
            shutil.rmtree(test_examples_dir)


class TestDocumentViewer(unittest.TestCase):
    """Tests for document viewer HTML generation."""

    def test_build_document_viewer_html_includes_content_and_search_ui(self):
        content = "<p>Deposit at https://example.org/data</p>"
        html = build_document_viewer_html(content)

        self.assertIn(content, html)
        self.assertIn('id="doc-search-input"', html)
        self.assertIn("mark.doc-search-hit", html)
        self.assertIn("doc-search-current", html)
        self.assertIn("function escapeRegex", html)

    def test_build_document_viewer_html_preserves_nested_markup(self):
        content = "<section><h1>Title</h1><p>See <strong>Figure 1</strong>.</p></section>"
        html = build_document_viewer_html(content)

        self.assertIn("<strong>Figure 1</strong>", html)
        self.assertIn('id="doc-content"', html)

    def test_extract_body_html_strips_wrapper(self):
        wrapped = (
            "<html><head><title>T</title></head>"
            "<body><p>Inside body</p></body></html>"
        )
        self.assertEqual(_extract_body_html(wrapped), "<p>Inside body</p>")

    def test_extract_body_html_returns_fragment_unchanged(self):
        fragment = "<p>Already a fragment</p>"
        self.assertEqual(_extract_body_html(fragment), fragment)

    def test_build_document_viewer_html_opens_links_in_new_tab(self):
        content = '<p>See <a href="https://example.org">link</a></p>'
        html = build_document_viewer_html(content)
        self.assertIn('setAttribute("target", "_blank")', html)
        self.assertIn("configureLinks", html)


class TestWordExampleCache(unittest.TestCase):
    """Tests for WordExample loading helpers and session cache."""

    def test_get_word_docx_path_requires_single_docx(self):
        test_dir = Path(tempfile.mkdtemp())
        try:
            content_dir = test_dir / "doc-a" / "content"
            content_dir.mkdir(parents=True)
            docx = content_dir / "paper.docx"
            docx.write_bytes(b"PK\x03\x04")

            path = get_word_docx_path(test_dir, "doc-a")
            self.assertEqual(path, docx)
        finally:
            shutil.rmtree(test_dir)

    def test_get_word_docx_path_raises_for_multiple_docx(self):
        test_dir = Path(tempfile.mkdtemp())
        try:
            content_dir = test_dir / "doc-a" / "content"
            content_dir.mkdir(parents=True)
            (content_dir / "a.docx").write_bytes(b"PK\x03\x04")
            (content_dir / "b.docx").write_bytes(b"PK\x03\x04")

            with self.assertRaises(ValueError):
                get_word_docx_path(test_dir, "doc-a")
        finally:
            shutil.rmtree(test_dir)

    def test_load_cached_word_example_reuses_cache(self):
        test_dir = Path(tempfile.mkdtemp())
        try:
            content_dir = test_dir / "doc-a" / "content"
            content_dir.mkdir(parents=True)
            docx = content_dir / "paper.docx"
            docx.write_bytes(b"PK\x03\x04")

            cache = {}
            with patch(
                "soda_mmqc.core.curation.EXAMPLE_FACTORY.create"
            ) as mock_create:
                mock_create.return_value = object()
                first = load_cached_word_example("doc-a", test_dir, cache)
                second = load_cached_word_example("doc-a", test_dir, cache)

            self.assertIs(first, second)
            mock_create.assert_called_once()
            self.assertEqual(
                list(cache.keys()),
                [word_example_cache_key("doc-a", docx.stat().st_mtime)],
            )
        finally:
            shutil.rmtree(test_dir)


if __name__ == "__main__":
    unittest.main() 