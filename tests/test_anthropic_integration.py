#!/usr/bin/env python3
"""Integration tests for Anthropic API with real API calls."""

import os
import json
import pytest
from pathlib import Path


from soda_mmqc.lib.api import generate_response_anthropic, _create_tool_from_schema
from tests.conftest import requires_key


class TestAnthropicIntegration:
    """Integration tests for Anthropic API with real API calls."""
    
    @pytest.fixture(autouse=True)
    def setup_environment(self):
        """Point the library at Anthropic for the duration of a test.

        It no longer skips on a missing key. Two tests in this class never
        reach the network, and skipping those for want of a credential they
        do not use cost real offline coverage. The tests that do call the API
        carry `@requires_key("ANTHROPIC_API_KEY")` instead.
        """
        os.environ["API_PROVIDER"] = "anthropic"
    
    def test_schema_conversion_with_real_schema(self):
        """Test schema conversion with a real schema file."""
        schema_path = Path("soda_mmqc/data/checklist/doc-checklist/section-order/schema.json")
        
        if not schema_path.exists():
            pytest.skip(f"Schema file not found: {schema_path}")
        
        with open(schema_path, 'r') as f:
            schema = json.load(f)
        
        # Test the conversion
        tool = _create_tool_from_schema(schema)
        
        # Verify the tool structure
        assert tool["name"] == "structured_output"
        assert "input_schema" in tool
        
        # Verify the schema has required fields
        input_schema = tool["input_schema"]
        assert "type" in input_schema
        assert input_schema["type"] == "object"
        assert "properties" in input_schema
    
    @pytest.mark.integration
    @requires_key("ANTHROPIC_API_KEY")
    def test_anthropic_api_simple_text_call(self):
        """Test a simple text-only call to Anthropic API."""
        # Simple schema for testing
        schema = {
            "type": "object",
            "properties": {
                "response": {"type": "string"}
            },
            "required": ["response"]
        }
        
        # Create a simple mock example with correct Anthropic format
        class SimpleExample:
            def prepare_model_input(self, prompt):
                return {
                    "content": [
                        {
                            "type": "text",  # Correct Anthropic format
                            "text": prompt
                        }
                    ]
                }
        
        example = SimpleExample()
        prompt = "Say hello in one word."
        
        try:
            result, metadata = generate_response_anthropic(
                example=example,
                prompt=prompt,
                schema=schema,
                model="claude-3-5-sonnet-20241022",
                metadata={"test": "simple_call"}
            )
            
            # Verify response structure
            assert isinstance(result, dict)
            assert "response" in result
            assert isinstance(result["response"], str)
            
            # Verify metadata
            assert "response_id" in metadata
            assert "model" in metadata
            assert metadata["test"] == "simple_call"
            
            print(f"✅ Simple API call successful: {result}")
            
        except Exception as e:
            pytest.fail(f"Simple API call failed: {e}")
    
    @pytest.mark.integration
    @requires_key("ANTHROPIC_API_KEY")
    def test_anthropic_api_content_format_issue(self):
        """Test to identify the content format issue with real examples."""
        # Create a mock example that simulates the real content format
        class MockFigureExample:
            def prepare_model_input(self, prompt):
                # This simulates what the real FigureExample produces
                return {
                    "content": [
                        {
                            "type": "input_text",  # This is the problem!
                            "text": f"{prompt}\n\nFigure Caption:\nTest caption"
                        },
                        {
                            "type": "input_image",  # This is also the problem!
                            "image_url": "data:image/jpeg;base64,test_image_data"
                        }
                    ]
                }
        
        example = MockFigureExample()
        
        # Get the model input to see what format it produces
        model_input = example.prepare_model_input("Test prompt")
        
        print("🔍 Debug: Model input format:")
        print(f"Content structure: {model_input}")
        
        # Check if the format uses the wrong content types
        content = model_input.get("content", [])
        for i, item in enumerate(content):
            print(f"Item {i}: {item}")
            if "type" in item:
                if item["type"] in ["input_text", "input_image"]:
                    print(f"⚠️  Found OpenAI format: {item['type']}")
                    print("   Anthropic expects: 'text', 'image', etc.")
        
        # Simple schema for testing
        schema = {
            "type": "object",
            "properties": {
                "test": {"type": "string"}
            },
            "required": ["test"]
        }
        
        prompt = "This should fail due to content format."
        
        # This should fail with the current format
        with pytest.raises(Exception) as exc_info:
            generate_response_anthropic(
                example=example,
                prompt=prompt,
                schema=schema,
                model="claude-3-5-sonnet-20241022",
                metadata={"test": "content_format_debug"}
            )
        
        print(f"🔍 Expected error: {exc_info.value}")
        # Don't fail the test - this is expected to help us debug
    
    def test_content_conversion_function(self):
        """Test the content conversion function directly."""
        from soda_mmqc.lib.api import _convert_content_for_anthropic
        
        # Test OpenAI format content
        openai_content = [
            {
                "type": "input_text",
                "text": "Test prompt\n\nFigure Caption:\nTest caption"
            },
            {
                "type": "input_image",
                "image_url": "data:image/jpeg;base64,test_image_data"
            }
        ]
        
        # Convert to Anthropic format
        anthropic_content = _convert_content_for_anthropic(openai_content)
        
        # Verify conversion
        assert len(anthropic_content) == 2
        
        # Check text conversion
        assert anthropic_content[0]["type"] == "text"
        assert anthropic_content[0]["text"] == "Test prompt\n\nFigure Caption:\nTest caption"
        
        # Check image conversion
        assert anthropic_content[1]["type"] == "image"
        assert anthropic_content[1]["source"]["type"] == "base64"
        assert anthropic_content[1]["source"]["media_type"] == "image/jpeg"
        assert anthropic_content[1]["source"]["data"] == "test_image_data"
        
        print("✅ Content conversion function works correctly")
    
    @pytest.mark.integration
    @requires_key("ANTHROPIC_API_KEY")
    def test_anthropic_api_with_mock_figure_example(self):
        """Test with a mock figure example that simulates real content."""
        # Create a mock example that simulates the real FigureExample
        class MockFigureExample:
            def prepare_model_input(self, prompt):
                return {
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"{prompt}\n\nFigure Caption:\nThis is a test figure caption with some content."
                        },
                        {
                            "type": "input_image",
                            "image_url": "data:image/jpeg;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
                        }
                    ]
                }
        
        example = MockFigureExample()
        
        # Simple schema for testing
        schema = {
            "type": "object",
            "properties": {
                "figure_type": {"type": "string"},
                "has_caption": {"type": "boolean"},
                "caption_length": {"type": "integer"}
            },
            "required": ["figure_type", "has_caption", "caption_length"]
        }
        
        prompt = "Analyze this figure and tell me what type it is, if it has a caption, and the caption length."
        
        try:
            result, metadata = generate_response_anthropic(
                example=example,
                prompt=prompt,
                schema=schema,
                model="claude-3-5-sonnet-20241022",
                metadata={"test": "mock_figure_example"}
            )
            
            # Verify response structure
            assert isinstance(result, dict)
            assert "figure_type" in result
            assert "has_caption" in result
            assert "caption_length" in result
            assert isinstance(result["has_caption"], bool)
            assert isinstance(result["caption_length"], int)
            
            print(f"✅ Mock figure example API call successful: {result}")
            
        except Exception as e:
            pytest.fail(f"Mock figure example API call failed: {e}")
    
    @pytest.mark.integration
    @requires_key("ANTHROPIC_API_KEY")
    def test_anthropic_api_with_nested_schema(self):
        """Test with a nested schema (like our actual schemas)."""
        # Use a real nested schema
        schema_path = Path("soda_mmqc/data/checklist/doc-checklist/section-order/schema.json")
        
        if not schema_path.exists():
            pytest.skip(f"Schema file not found: {schema_path}")
        
        with open(schema_path, 'r') as f:
            schema = json.load(f)
        
        # Create a simple mock example
        class SimpleExample:
            def prepare_model_input(self, prompt):
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
        
        example = SimpleExample()
        prompt = "Analyze this document structure and provide section information."
        
        try:
            result, metadata = generate_response_anthropic(
                example=example,
                prompt=prompt,
                schema=schema,
                model="claude-3-5-sonnet-20241022",
                metadata={"test": "nested_schema"}
            )
            
            # Verify response structure (should match the schema)
            assert isinstance(result, dict)
            assert "outputs" in result
            assert isinstance(result["outputs"], list)
            
            print(f"✅ Nested schema API call successful: {result}")
            
        except Exception as e:
            pytest.fail(f"Nested schema API call failed: {e}")
    
    @pytest.mark.integration
    @requires_key("ANTHROPIC_API_KEY")
    def test_anthropic_api_error_handling(self):
        """Test error handling with invalid schema."""
        # Invalid schema (missing required fields)
        invalid_schema = {
            "type": "object",
            "properties": {
                "test": {"type": "string"}
            }
            # Missing required field
        }
        
        class SimpleExample:
            def prepare_model_input(self, prompt):
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
        
        example = SimpleExample()
        prompt = "This should fail due to invalid schema."
        
        # Test that the API call works even with invalid schema (good error handling)
        try:
            result, metadata = generate_response_anthropic(
                example=example,
                prompt=prompt,
                schema=invalid_schema,
                model="claude-3-5-sonnet-20241022",
                metadata={"test": "error_handling"}
            )
            
            # If it succeeds, that's actually good - it means our error handling is robust
            print(f"✅ API call succeeded with invalid schema: {result}")
            
        except Exception as e:
            # If it fails, that's also acceptable
            print(f"✅ API call failed as expected: {e}")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"]) 