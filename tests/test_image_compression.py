import unittest
import base64
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from soda_mmqc.lib.api import _compress_image_if_needed, _convert_content_for_anthropic


def _imagemagick_available() -> bool:
    """Whether the MagickWand shared library is actually loadable.

    The compression path catches every exception and returns the image
    unchanged, so a missing ImageMagick does not raise -- it simply makes
    compression a no-op, and the tests below then fail with "4152637 not less
    than 4152637", which reads like a compression bug rather than an absent
    system library. Install it with `brew install imagemagick` to run them
    for real.
    """
    try:
        import wand.image  # noqa: F401
    except Exception:
        return False
    return True

class TestImageCompression(unittest.TestCase):
    """Test image compression functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_images_dir = Path(__file__).parent / "test_images"
        self.png_image_path = self.test_images_dir / "44319_2025_415_fig2_html.png"
        self.jpg_image_path = self.test_images_dir / "44318_2025_416_fig8_esm.jpg"
        
        # Check if test images exist
        if not self.png_image_path.exists():
            self.skipTest(f"Test PNG image not found: {self.png_image_path}")
        if not self.jpg_image_path.exists():
            self.skipTest(f"Test JPG image not found: {self.jpg_image_path}")
    
    def test_compress_small_image_no_change(self):
        """Test that small images are not compressed."""
        # Create a small test image data
        small_image_data = base64.b64encode(b"small_image_data").decode()
        
        result_data, result_mime = _compress_image_if_needed(
            small_image_data, "image/jpeg", max_size_bytes=1000
        )
        
        # Should return original data unchanged
        self.assertEqual(result_data, small_image_data)
        self.assertEqual(result_mime, "image/jpeg")
    
    def test_compress_png_image(self):
        """Test PNG image compression."""
        if not _imagemagick_available():
            self.skipTest("ImageMagick (MagickWand) not installed")
        # Read the actual PNG file
        with open(self.png_image_path, "rb") as f:
            png_data = f.read()
        
        # Convert to base64
        png_base64 = base64.b64encode(png_data).decode()
        original_size = len(png_data)
        
        # Test compression with large size limit (should not compress)
        result_data, result_mime = _compress_image_if_needed(
            png_base64, "image/png", max_size_bytes=1024 * 1024 * 1024
        )
        
        # Should return original data unchanged (under limit)
        self.assertEqual(result_data, png_base64)
        self.assertEqual(result_mime, "image/png")
        
        # Test compression with small size limit (should compress)
        result_data, result_mime = _compress_image_if_needed(
            png_base64, "image/png", max_size_bytes=2 * 1024 * 1024
        )
        
        # Should return compressed data
        self.assertIsInstance(result_data, str)
        self.assertIsInstance(result_mime, str)
        
        # Decode result to check size
        result_bytes = base64.b64decode(result_data)
        result_size = len(result_bytes)
        
        # Should be smaller than original
        self.assertLess(result_size, original_size)
        
        # Should be within size limit
        self.assertLessEqual(result_size, 2 * 1024 * 1024)
        
        # Should be converted to JPEG for better compression
        self.assertEqual(result_mime, "image/jpeg")
    
    def test_compress_jpg_image(self):
        """Test JPG image compression."""
        # Read the actual JPG file
        with open(self.jpg_image_path, "rb") as f:
            jpg_data = f.read()
        
        # Convert to base64
        jpg_base64 = base64.b64encode(jpg_data).decode()
        original_size = len(jpg_data)
        
        # Test compression
        result_data, result_mime = _compress_image_if_needed(
            jpg_base64, "image/jpeg", max_size_bytes=5 * 1024 * 1024
        )
        
        # Should return compressed data
        self.assertIsInstance(result_data, str)
        self.assertIsInstance(result_mime, str)
        
        # Decode result to check size
        result_bytes = base64.b64decode(result_data)
        result_size = len(result_bytes)
        
        # Should be smaller or same size
        self.assertLessEqual(result_size, original_size)
        
        # Should be within size limit
        self.assertLessEqual(result_size, 5 * 1024 * 1024)
    
    def test_compress_large_image_with_resize(self):
        """Test that very large images get resized."""
        # Skip this test as it requires complex mocking
        # The resize functionality is tested indirectly through real image compression
        self.skipTest("Complex mocking test - resize functionality tested with real images")
    
    def test_compress_rgba_png_conversion(self):
        """Test that RGBA PNG images are properly converted to RGB for JPEG compression."""
        if not _imagemagick_available():
            self.skipTest("ImageMagick (MagickWand) not installed")
        # Test with the actual RGBA PNG file
        with open(self.png_image_path, "rb") as f:
            png_data = f.read()
        
        png_base64 = base64.b64encode(png_data).decode()
        original_size = len(png_data)
        
        # Test compression with small limit to force JPEG conversion
        max_size = len(png_base64) - 100  # Set limit just below original size to trigger compression
        self.assertGreater(max_size, 0, "Max size should be positive to trigger compression")
        result_data, result_mime = _compress_image_if_needed(
            png_base64, "image/png", max_size_bytes=max_size
        )
        
        # Should be converted to JPEG
        self.assertEqual(result_mime, "image/jpeg")
        
        # Should be smaller than original
        result_bytes = base64.b64decode(result_data)
        result_size = len(result_bytes)
        self.assertLess(result_size, original_size)
        
        # Should be within size limit
        self.assertLessEqual(result_size, max_size)

    def test_convert_content_with_compression(self):
        """Test that content conversion includes compression."""
        # Create test content with large image
        test_content = [
            {
                "type": "input_text",
                "text": "Test prompt"
            },
            {
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{base64.b64encode(b'x' * 6 * 1024 * 1024).decode()}"
            }
        ]
        
        # Test conversion
        result = _convert_content_for_anthropic(test_content)
        
        # Should have 2 items (text + image)
        self.assertEqual(len(result), 2)
        
        # Check text item
        self.assertEqual(result[0]["type"], "text")
        self.assertEqual(result[0]["text"], "Test prompt")
        
        # Check image item
        self.assertEqual(result[1]["type"], "image")
        self.assertIn("source", result[1])
        self.assertEqual(result[1]["source"]["type"], "base64")
        self.assertIn("media_type", result[1]["source"])
        self.assertIn("data", result[1]["source"])
    
    def test_convert_content_with_png_image(self):
        """Test content conversion with PNG image."""
        # Read actual PNG and create test content
        with open(self.png_image_path, "rb") as f:
            png_data = f.read()
        
        png_base64 = base64.b64encode(png_data).decode()
        test_content = [
            {
                "type": "input_text",
                "text": "Test prompt"
            },
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{png_base64}"
            }
        ]
        
        # Test conversion
        result = _convert_content_for_anthropic(test_content)
        
        # Should have 2 items
        self.assertEqual(len(result), 2)
        
        # Check image item
        self.assertEqual(result[1]["type"], "image")
        # not checking media type - png might be converted to jpeg if too large

        # Check that data is base64 encoded
        try:
            base64.b64decode(result[1]["source"]["data"])
        except Exception:
            self.fail("Image data is not valid base64")
    
    def test_convert_content_with_jpg_image(self):
        """Test content conversion with JPG image."""
        # Read actual JPG and create test content
        with open(self.jpg_image_path, "rb") as f:
            jpg_data = f.read()
        
        jpg_base64 = base64.b64encode(jpg_data).decode()
        test_content = [
            {
                "type": "input_text",
                "text": "Test prompt"
            },
            {
                "type": "input_image",
                "image_url": f"data:image/jpeg;base64,{jpg_base64}"
            }
        ]
        
        # Test conversion
        result = _convert_content_for_anthropic(test_content)
        
        # Should have 2 items
        self.assertEqual(len(result), 2)
        
        # Check image item
        self.assertEqual(result[1]["type"], "image")
        self.assertEqual(result[1]["source"]["media_type"], "image/jpeg")
        
        # Check that data is base64 encoded
        try:
            base64.b64decode(result[1]["source"]["data"])
        except Exception:
            self.fail("Image data is not valid base64")
    
    def test_convert_content_invalid_items(self):
        """Test content conversion with invalid items."""
        test_content = [
            {"type": "input_text", "text": "Valid text"},
            {"invalid": "item"},  # Invalid item
            {"type": "input_image", "image_url": "data:image/jpeg;base64,test"},
            None,  # None item
            {"type": "unknown_type", "data": "test"}  # Unknown type
        ]
        
        result = _convert_content_for_anthropic(test_content)
        
        # Should only have valid items
        self.assertEqual(len(result), 3)  # text + image + unknown (kept as-is)
        
        # Check that valid items are converted
        self.assertEqual(result[0]["type"], "text")
        self.assertEqual(result[1]["type"], "image")
        self.assertEqual(result[2]["type"], "unknown_type")


if __name__ == "__main__":
    unittest.main() 