import os
import json
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from soda_mmqc.lib.api import (
    generate_response_openai,
    generate_response_anthropic,
    generate_response,
    _create_tool_from_schema
)
from soda_mmqc.lib.cache import ModelCache
from soda_mmqc.core.examples import FigureExample
from soda_mmqc.scripts.run import ModelInput


class TestModelApi(unittest.TestCase):
    """Test cases for the model_api module."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary test image file
        self.test_image = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        # Create a minimal valid JPEG image data
        minimal_jpeg = (
            b'\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00'
            b'\xFF\xDB\x00C\x00\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'
            b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'
            b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'
            b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'
            b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'
            b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'
            b'\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF'
            b'\xFF\xC0\x00\x0B\x08\x00\x01\x00\x01\x01\x01\x11\x00\xFF\xC4\x00'
            b'\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00\x00\xFF\xDA\x00\x08\x01\x01\x00\x00\x3F\x00?'
            b'\xFF\xD9'
        )
        self.test_image.write(minimal_jpeg)
        self.test_image.close()
        
        # Create a temporary directory structure for the example
        self.test_dir = tempfile.mkdtemp()
        self.content_dir = Path(self.test_dir) / "content"
        self.content_dir.mkdir()
        
        # Move the test image to the content directory
        import shutil
        shutil.move(self.test_image.name, self.content_dir / "test_image.jpg")
        
        # Create a caption file
        caption_file = self.content_dir / "caption.txt"
        caption_file.write_text("Test figure caption")
        
        # Test data
        self.test_prompt = "Analyze this figure for error bars."
        self.test_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "panels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "panel_label": {"type": "string"},
                            "error_bar_on_figure": {"type": "string"},
                            "error_bar_defined_in_legend": {"type": "string"},
                            "error_bar_meaning": {"type": "string"}
                        },
                        "required": [
                            "panel_label",
                            "error_bar_on_figure",
                            "error_bar_defined_in_legend",
                            "error_bar_meaning"
                        ]
                    }
                }
            },
            "required": ["name", "panels"]
        }
        self.test_model = "gpt-4o-2024-08-06"
        self.test_metadata = {"test": "metadata"}

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up the temporary directory
        import shutil
        shutil.rmtree(self.test_dir)

    @patch('openai.OpenAI')
    @patch('soda_mmqc.lib.api.os.getenv')
    def test_generate_response_openai_success(self, mock_getenv, mock_openai):
        """Test successful response generation with OpenAI API."""
        # Mock environment variables
        mock_getenv.return_value = "test-api-key"
        
        # Mock OpenAI client and response
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Mock the response object for responses API
        mock_response = MagicMock()
        mock_response.output_text = '{"name": "test", "panels": []}'
        mock_response.id = "test-response-id"
        mock_response.model = "gpt-4o-2024-08-06"
        mock_response.metadata = {}
        
        mock_client.responses.create.return_value = mock_response
        
        # Create a test example
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        
        # Call the function
        result, metadata = generate_response_openai(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema,
            model=self.test_model,
            metadata=self.test_metadata
        )
        
        # Verify the result
        self.assertEqual(result, {"name": "test", "panels": []})
        self.assertIn("response_id", metadata)
        self.assertIn("model", metadata)
        self.assertEqual(metadata["response_id"], "test-response-id")
        self.assertEqual(metadata["model"], "gpt-4o-2024-08-06")
        
        # Verify the API was called correctly
        mock_client.responses.create.assert_called_once()
        call_args = mock_client.responses.create.call_args
        self.assertEqual(call_args[1]["model"], self.test_model)
        self.assertIn("text", call_args[1])
        self.assertEqual(
            call_args[1]["text"], 
            self.test_schema
        )
        self.assertNotIn("tools", call_args[1])

    @patch('openai.OpenAI')
    @patch('soda_mmqc.lib.api.os.getenv')
    def test_generate_response_openai_with_tools_config(self, mock_getenv, mock_openai):
        """Test that model_config with tools is passed to responses.create.
        Uses web_search_preview (valid Responses API type; web_search is not).
        """
        mock_getenv.return_value = "test-api-key"
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_text = '{"name": "test", "panels": []}'
        mock_response.id = "test-response-id"
        mock_response.model = "gpt-4o-2024-08-06"
        mock_response.metadata = {}
        mock_client.responses.create.return_value = mock_response

        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        model_config = {
            "tools": [{"type": "web_search_preview"}],
            "tool_choice": "auto",
        }

        result, _ = generate_response_openai(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema,
            model=self.test_model,
            metadata=self.test_metadata,
            model_config=model_config
        )

        self.assertEqual(result, {"name": "test", "panels": []})
        call_args = mock_client.responses.create.call_args
        self.assertEqual(call_args[1]["tools"], [{"type": "web_search_preview"}])
        self.assertEqual(call_args[1]["tool_choice"], "auto")

    @patch('openai.OpenAI')
    @patch('soda_mmqc.lib.api.os.getenv')
    def test_generate_response_openai_reasoning_and_max_output_tokens(self, mock_getenv, mock_openai):
        """Test that model_config reasoning and max_output_tokens are passed to responses.create."""
        mock_getenv.return_value = "test-api-key"
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.output_text = '{"name": "test", "panels": []}'
        mock_response.id = "test-response-id"
        mock_response.model = "gpt-5"
        mock_response.metadata = {}
        mock_client.responses.create.return_value = mock_response

        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        model_config = {
            "reasoning": {"effort": "medium"},
            "max_output_tokens": 16384,
        }

        result, _ = generate_response_openai(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema,
            model="gpt-5",
            metadata=self.test_metadata,
            model_config=model_config
        )

        self.assertEqual(result, {"name": "test", "panels": []})
        call_args = mock_client.responses.create.call_args
        self.assertEqual(call_args[1]["reasoning"], {"effort": "medium"})
        self.assertEqual(call_args[1]["max_output_tokens"], 16384)

    @patch('openai.OpenAI')
    @patch('soda_mmqc.lib.api.os.getenv')
    def test_generate_response_openai_json_error(self, mock_getenv, mock_openai):
        """Test handling of JSON parsing errors."""
        # Mock environment variables
        mock_getenv.return_value = "test-api-key"
        
        # Mock OpenAI client and response
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Mock the response object with invalid JSON
        mock_response = MagicMock()
        mock_response.output_text = '{"invalid": json}'
        mock_response.id = "test-response-id"
        mock_response.model = "gpt-4o-2024-08-06"
        mock_response.metadata = {}
        mock_client.responses.create.return_value = mock_response
        
        # Create a test example
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        
        # Call the function and expect it to raise an exception
        with self.assertRaises(json.JSONDecodeError):
            generate_response_openai(
                example=example,
                prompt=self.test_prompt,
                schema=self.test_schema,
                model=self.test_model,
                metadata=self.test_metadata
            )

    @patch('openai.OpenAI')
    @patch('soda_mmqc.lib.api.os.getenv')
    def test_generate_response_openai_missing_content(self, mock_getenv, mock_openai):
        """Test handling of missing content in response."""
        # Mock environment variables
        mock_getenv.return_value = "test-api-key"
        
        # Mock OpenAI client and response
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Mock the response object with None content
        mock_response = MagicMock()
        mock_response.output_text = ""
        mock_response.id = "test-response-id"
        mock_response.model = "gpt-4o-2024-08-06"
        mock_response.metadata = {}
        mock_client.responses.create.return_value = mock_response
        
        # Create a test example
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        
        # Call the function and expect it to raise an exception
        with self.assertRaises(ValueError):
            generate_response_openai(
                example=example,
                prompt=self.test_prompt,
                schema=self.test_schema,
                model=self.test_model,
                metadata=self.test_metadata
            )

    @patch('soda_mmqc.lib.api.API_PROVIDER', 'openai')
    @patch('soda_mmqc.lib.api.generate_response_openai')
    def test_generate_response_wrapper(self, mock_generate_openai):
        """Test the generate_response wrapper function."""
        # Mock the underlying function
        mock_generate_openai.return_value = ({"test": "result"}, {"test": "metadata"})
        
        # Create a test example
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        
        # Create ModelInput object
        model_input = ModelInput(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema
        )
        
        # Call the wrapper function
        result, metadata = generate_response(
            model_input=model_input,
            model=self.test_model,
            metadata=self.test_metadata
        )
        
        # Verify the result
        self.assertEqual(result, {"test": "result"})
        self.assertEqual(metadata, {"test": "metadata"})
        
        # Verify the underlying function was called correctly
        mock_generate_openai.assert_called_once_with(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema,
            model=self.test_model,
            metadata=self.test_metadata,
            model_config=None,
            prompt_obj=None
        )

    @patch('openai.OpenAI')
    @patch('soda_mmqc.lib.api.os.getenv')
    def test_generate_response_openai_with_retry(self, mock_getenv, mock_openai):
        """Test that the function retries on JSON errors."""
        # Mock environment variables
        mock_getenv.return_value = "test-api-key"
        
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Mock the response objects to fail twice then succeed
        def create_mock_response(content):
            mock_response = MagicMock()
            mock_response.output_text = content
            mock_response.id = "test-response-id"
            mock_response.model = "gpt-4o-2024-08-06"
            mock_response.metadata = {}
            return mock_response
        
        mock_response1 = create_mock_response('{"invalid": json}')  # Invalid JSON
        mock_response2 = create_mock_response('{"invalid": json}')  # Invalid JSON again
        mock_response3 = create_mock_response(
            '{"name": "test", "panels": []}'
        )  # Valid JSON
        
        # Set up the mock to return different responses on subsequent calls
        mock_client.responses.create.side_effect = [
            mock_response1, mock_response2, mock_response3
        ]
        
        # Create a test example
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        
        # Call the function - it should retry and eventually succeed
        result, metadata = generate_response_openai(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema,
            model=self.test_model,
            metadata=self.test_metadata
        )
        
        # Verify the result
        self.assertEqual(result, {"name": "test", "panels": []})
        self.assertEqual(metadata["response_id"], "test-response-id")
        
        # Verify the API was called 3 times (2 failures + 1 success)
        self.assertEqual(
            mock_client.responses.create.call_count, 3
        )

    # Tests for Anthropic API
    def test_create_tool_from_schema(self):
        """Test the helper function that creates Anthropic tools from JSON schema."""
        schema = {
            "type": "object",
            "properties": {
                "result": {"type": "string"}
            },
            "required": ["result"]
        }
        
        tool = _create_tool_from_schema(schema)
        
        self.assertEqual(tool["name"], "structured_output")
        self.assertEqual(
            tool["description"], 
            "Provide structured output according to the schema"
        )
        self.assertEqual(tool["input_schema"], schema)

    def test_create_tool_from_schema_nested(self):
        """Test _create_tool_from_schema with nested schema format."""
        from soda_mmqc.lib.api import _create_tool_from_schema
        
        # Test with nested schema (like our actual schemas)
        nested_schema = {
            "format": {
                "type": "json_schema",
                "name": "test",
                "schema": {
                    "type": "object",
                    "properties": {
                        "test": {"type": "string"}
                    }
                }
            }
        }
        
        result = _create_tool_from_schema(nested_schema)
        
        self.assertEqual(result["name"], "structured_output")
        self.assertEqual(
            result["description"], 
            "Provide structured output according to the schema"
        )
        self.assertEqual(
            result["input_schema"], 
            nested_schema["format"]["schema"]
        )
    
    def test_create_tool_from_schema_direct(self):
        """Test _create_tool_from_schema with direct schema."""
        from soda_mmqc.lib.api import _create_tool_from_schema
        
        # Test with direct schema
        direct_schema = {
            "type": "object",
            "properties": {
                "test": {"type": "string"}
            }
        }
        
        result = _create_tool_from_schema(direct_schema)
        
        self.assertEqual(result["name"], "structured_output")
        self.assertEqual(
            result["description"], 
            "Provide structured output according to the schema"
        )
        self.assertEqual(result["input_schema"], direct_schema)

    @patch.dict(os.environ, {'API_PROVIDER': 'anthropic'})
    @patch('anthropic.Anthropic')
    def test_generate_response_anthropic_success(self, mock_anthropic):
        """Test successful response generation with Anthropic API."""
        # Mock Anthropic client and response
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        
        # Mock the response object for Anthropic messages API
        mock_response = MagicMock()
        mock_response.id = "test-response-id"
        mock_response.model = "claude-3-5-sonnet-20241022"
        mock_response.stop_reason = "tool_use"
        
        # Mock usage data
        mock_usage = MagicMock()
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50
        mock_response.usage = mock_usage
        
        # Mock content with tool use
        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.input = {"name": "test", "panels": []}
        mock_response.content = [mock_tool_use]
        
        mock_client.messages.create.return_value = mock_response
        
        # Create a test example
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        
        # Call the function
        result, metadata = generate_response_anthropic(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema,
            model="claude-3-5-sonnet-20241022",
            metadata=self.test_metadata
        )
        
        # Verify the result
        self.assertEqual(result, {"name": "test", "panels": []})
        self.assertIn("response_id", metadata)
        self.assertIn("model", metadata)
        self.assertIn("usage", metadata)
        self.assertEqual(metadata["response_id"], "test-response-id")
        self.assertEqual(metadata["model"], "claude-3-5-sonnet-20241022")
        self.assertEqual(metadata["usage"]["input_tokens"], 100)
        
        # Verify the API was called correctly
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args
        self.assertEqual(call_args[1]["model"], "claude-3-5-sonnet-20241022")
        self.assertIn("tools", call_args[1])
        self.assertIn("tool_choice", call_args[1])

    @patch.dict(os.environ, {'API_PROVIDER': 'anthropic'})
    @patch('anthropic.Anthropic')
    def test_generate_response_anthropic_no_content(self, mock_anthropic):
        """Test handling of response with no content."""
        # Mock Anthropic client and response
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        
        # Mock response with no content
        mock_response = MagicMock()
        mock_response.content = []
        mock_client.messages.create.return_value = mock_response
        
        # Create a test example
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        
        # Call the function and expect it to raise an exception
        with self.assertRaises(ValueError):
            generate_response_anthropic(
                example=example,
                prompt=self.test_prompt,
                schema=self.test_schema,
                model="claude-3-5-sonnet-20241022",
                metadata=self.test_metadata
            )

    @patch.dict(os.environ, {'API_PROVIDER': 'anthropic'})
    @patch('anthropic.Anthropic')
    def test_generate_response_anthropic_no_tool_use(self, mock_anthropic):
        """Test handling of response with no tool use block."""
        # Mock Anthropic client and response
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        
        # Mock response with content but no tool use
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_response.content = [mock_text_block]
        mock_client.messages.create.return_value = mock_response
        
        # Create a test example
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        
        # Call the function and expect it to raise an exception
        with self.assertRaises(ValueError):
            generate_response_anthropic(
                example=example,
                prompt=self.test_prompt,
                schema=self.test_schema,
                model="claude-3-5-sonnet-20241022",
                metadata=self.test_metadata
            )

    # Tests for provider switching
    @patch('soda_mmqc.lib.api.API_PROVIDER', 'openai')
    @patch('soda_mmqc.lib.api.generate_response_openai')
    def test_generate_response_routes_to_openai(self, mock_generate_openai):
        """Test that generate_response routes to OpenAI when API_PROVIDER is 'openai'."""
        # Mock the underlying function
        mock_generate_openai.return_value = ({"test": "result"}, {"test": "metadata"})
        
        # Create a test example and ModelInput
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        model_input = ModelInput(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema
        )
        
        # Call the function
        result, metadata = generate_response(
            model_input=model_input,
            model="gpt-4o-2024-08-06",
            metadata=self.test_metadata
        )
        
        # Verify routing
        self.assertEqual(result, {"test": "result"})
        self.assertEqual(metadata, {"test": "metadata"})
        mock_generate_openai.assert_called_once_with(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema,
            model="gpt-4o-2024-08-06",
            metadata=self.test_metadata,
            model_config=None,
            prompt_obj=None
        )

    @patch('soda_mmqc.lib.api.API_PROVIDER', 'anthropic')
    @patch('soda_mmqc.lib.api.generate_response_anthropic')
    def test_generate_response_routes_to_anthropic(self, mock_generate_anthropic):
        """Test that generate_response routes to Anthropic when API_PROVIDER is 'anthropic'."""
        # Mock the underlying function
        mock_generate_anthropic.return_value = ({"test": "result"}, {"test": "metadata"})
        
        # Create a test example and ModelInput
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        model_input = ModelInput(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema
        )
        
        # Call the function
        result, metadata = generate_response(
            model_input=model_input,
            model="claude-3-5-sonnet-20241022",
            metadata=self.test_metadata
        )
        
        # Verify routing
        self.assertEqual(result, {"test": "result"})
        self.assertEqual(metadata, {"test": "metadata"})
        mock_generate_anthropic.assert_called_once_with(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema,
            model="claude-3-5-sonnet-20241022",
            metadata=self.test_metadata,
            model_config=None,
            prompt_obj=None
        )

    @patch('soda_mmqc.lib.api.API_PROVIDER', 'openai')
    @patch('soda_mmqc.lib.api.DEFAULT_MODEL', 'gpt-4o-2024-08-06')
    @patch('soda_mmqc.lib.api.generate_response_openai')
    def test_generate_response_default_model_openai(self, mock_generate_openai):
        """Test default model selection for OpenAI."""
        # Mock the underlying function
        mock_generate_openai.return_value = ({"test": "result"}, {"test": "metadata"})
        
        # Create a test example and ModelInput
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        model_input = ModelInput(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema
        )
        
        # Call the function without specifying a model
        result, metadata = generate_response(
            model_input=model_input,
            metadata=self.test_metadata
        )
        
        # Verify default model was used
        mock_generate_openai.assert_called_once()
        call_args = mock_generate_openai.call_args
        self.assertEqual(call_args[1]["model"], "gpt-4o-2024-08-06")

    @patch('soda_mmqc.lib.api.API_PROVIDER', 'anthropic')
    @patch('soda_mmqc.lib.api.DEFAULT_MODEL', 'claude-3-5-sonnet-20241022')
    @patch('soda_mmqc.lib.api.generate_response_anthropic')
    def test_generate_response_default_model_anthropic(self, mock_generate_anthropic):
        """Test default model selection for Anthropic."""
        # Mock the underlying function
        mock_generate_anthropic.return_value = ({"test": "result"}, {"test": "metadata"})
        
        # Create a test example and ModelInput
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        model_input = ModelInput(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema
        )
        
        # Call the function without specifying a model
        result, metadata = generate_response(
            model_input=model_input,
            metadata=self.test_metadata
        )
        
        # Verify default model was used
        mock_generate_anthropic.assert_called_once()
        call_args = mock_generate_anthropic.call_args
        self.assertEqual(call_args[1]["model"], "claude-3-5-sonnet-20241022")

    @patch('soda_mmqc.lib.api.API_PROVIDER', 'openai')
    @patch('soda_mmqc.lib.api.generate_response_openai')
    def test_generate_response_none_metadata(self, mock_generate_openai):
        """Test handling of None metadata parameter."""
        # Mock the underlying function
        mock_generate_openai.return_value = ({"test": "result"}, {"test": "metadata"})
        
        # Create a test example and ModelInput
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        model_input = ModelInput(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema
        )
        
        # Call the function with None metadata
        result, metadata = generate_response(
            model_input=model_input,
            model="gpt-4o-2024-08-06",
            metadata=None  # type: ignore
        )
        
        # Verify it was converted to empty dict
        mock_generate_openai.assert_called_once()
        call_args = mock_generate_openai.call_args
        self.assertEqual(call_args[1]["metadata"], {})

    @patch('soda_mmqc.lib.api.API_PROVIDER', 'openai')
    @patch('soda_mmqc.lib.api.generate_response_openai')
    def test_generate_response_passes_model_config(self, mock_generate_openai):
        """Test that generate_response passes model_config to OpenAI."""
        mock_generate_openai.return_value = ({"x": 1}, {})
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        model_input = ModelInput(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema
        )
        model_config = {"tools": [{"type": "web_search_preview"}], "tool_choice": "auto"}

        generate_response(
            model_input=model_input,
            model="gpt-4o",
            metadata=self.test_metadata,
            model_config=model_config
        )

        mock_generate_openai.assert_called_once_with(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema,
            model="gpt-4o",
            metadata=self.test_metadata,
            model_config=model_config,
            prompt_obj=None
        )

    def test_cache_key_includes_model_config(self):
        """Test that cache key changes when model_config differs."""
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        model_input = ModelInput(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema
        )
        cache = ModelCache(Path(self.test_dir) / "cache")
        key_no_config = cache.generate_cache_key(
            model_input, "check1", "gpt-4o", model_config=None
        )
        key_with_tools = cache.generate_cache_key(
            model_input, "check1", "gpt-4o",
            model_config={"tools": [{"type": "web_search_preview"}], "tool_choice": "auto"}
        )
        key_no_config_2 = cache.generate_cache_key(
            model_input, "check1", "gpt-4o", model_config=None
        )
        self.assertEqual(key_no_config, key_no_config_2)
        self.assertNotEqual(key_no_config, key_with_tools)

    @patch.dict(os.environ, {'API_PROVIDER': 'anthropic'})
    @patch('anthropic.Anthropic')
    def test_generate_response_anthropic_with_retry(self, mock_anthropic):
        """Test that the Anthropic function retries on errors."""
        # Mock Anthropic client
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        
        # First two calls raise ValueError, third succeeds
        def create_success_response():
            mock_response = MagicMock()
            mock_response.id = "test-response-id"
            mock_response.model = "claude-3-5-sonnet-20241022"
            mock_response.stop_reason = "tool_use"
            mock_response.usage = MagicMock()
            mock_response.usage.input_tokens = 100
            mock_response.usage.output_tokens = 50
            mock_tool_use = MagicMock()
            mock_tool_use.type = "tool_use"
            mock_tool_use.input = {"name": "test", "panels": []}
            mock_response.content = [mock_tool_use]
            return mock_response
        
        # Mock to fail twice then succeed
        mock_client.messages.create.side_effect = [
            ValueError("First error"),
            ValueError("Second error"),
            create_success_response()
        ]
        
        # Create a test example
        example = FigureExample(str(self.test_dir))
        example.load_from_source()
        
        # Call the function - it should retry and eventually succeed
        result, metadata = generate_response_anthropic(
            example=example,
            prompt=self.test_prompt,
            schema=self.test_schema,
            model="claude-3-5-sonnet-20241022",
            metadata=self.test_metadata
        )
        
        # Verify the result
        self.assertEqual(result, {"name": "test", "panels": []})
        self.assertEqual(metadata["response_id"], "test-response-id")
        
        # Verify the API was called 3 times (2 failures + 1 success)
        self.assertEqual(mock_client.messages.create.call_count, 3)


if __name__ == "__main__":
    unittest.main()
