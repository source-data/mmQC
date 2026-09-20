from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, Type, List, Tuple
import hashlib
import io
import json
import logging
import base64
import mimetypes
from soda_mmqc.config import EXAMPLES_DIR
from mmqc_utils import convert_to_bounded_jpeg, document_to_html
from mmqc_utils.exceptions import DocumentConversionError
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

logger = logging.getLogger(__name__)

# Image MIME types supported by OpenAI Responses API (TIFF is not supported)
_API_SUPPORTED_IMAGE_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/gif", "image/webp"}
)


# Class mapping for factory pattern - will be populated after class definitions
EXAMPLE_TYPES: Dict[str, Type['Example']] = {}


class Example(ABC):
    """Base class for all examples.
    
    This abstract class defines the interface for all example types.
    Each example type should know how to:
    1. Load its content from a source directory
    2. Generate a cache key
    3. Prepare its content for model input
    """
    
    _example_type: Optional[str] = None
    
    def __init__(self, relative_source_path: str):
        """Initialize an example from a dictionary.
        
        Args:
            source_path: Path to the example source directory
            
        Raises:
            ValueError: If required data is missing
        """
        self.relative_source_path = relative_source_path
        self.source_path = EXAMPLES_DIR / Path(self.relative_source_path)
        self.doc_id: Optional[str] = None
        self._content_hash: Optional[str] = None
        self.expected_output = None

    @abstractmethod
    def load_from_source(self) -> None:
        """Load the example's content from the provided path.
        
        Raises:
            FileNotFoundError: If required files are missing
            ValueError: If required data is missing
        """
        pass

    @property
    def example_class_name(self) -> str:
        """Get the example type identifier (read-only)."""
        if self._example_type is None:
            raise ValueError(
                "Example type not set. This should be set by the factory."
            )
        return self._example_type
    
    @example_class_name.setter
    def example_class_name(self, value: str) -> None:
        """Set the example type identifier (factory use only)."""
        if not isinstance(value, str):
            raise ValueError("Example type must be a string")
        if not value.strip():
            raise ValueError("Example type cannot be empty")
        self._example_type = value.strip()
    
    def get_expected_output(self, check_name: str) -> Dict[str, Any]:
        """Set the expected output for this example.
        
        Args:
            check_name: Name of the check
            
        Returns:
            Path to the expected output file 
        """

        expected_output_path = (
            self.source_path / "checks" / check_name /
            "expected_output.json"
        )
        if expected_output_path.exists():     
            with open(expected_output_path, "r", encoding="utf-8") as f:
                expected_output_json = json.load(f)
        else:
            logger.warning(
                f"Expected output file not found: {expected_output_path}"
            )
            expected_output_json = {}
        return expected_output_json

    @abstractmethod
    def get_content_hash(self) -> str:
        """Get a hash of the example's content for caching.
        
        Returns:
            A string hash of the content
        """
        pass

    def _ensure_loaded(self) -> None:
        """Ensure content is loaded. Call this before accessing 
        content-dependent methods."""
        if self.doc_id is None:
            self.load_from_source()
    
    @abstractmethod
    def prepare_model_input(
        self, prompt: str, model_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare the example's content for model input.
        
        Args:
            prompt: The prompt to use for the model
            model_config: Optional check-level config (e.g. source_data_files.enabled)
            
        Returns:
            Dictionary containing:
            - content: List of content items for the model
            - metadata: Dictionary with tracing information
        """
        pass

    @abstractmethod
    def input_parts(self) -> List[Dict[str, Any]]:
        """This example's content, in order, as provider-neutral parts.

        What an example *is* -- a caption and a figure, or a manuscript -- is
        a fact about the example class, and stating it in one place is what
        keeps format assumptions from settling in machinery that is supposed
        to be example-class neutral.

        The vocabulary is deliberately tiny and names no provider:

        ``{"kind": "text", "text": str}``
            Literal text. It may be derived -- ``WordExample`` puts its HTML
            conversion here -- because a part is a message, not a file, and
            nothing derived is ever written into a runtime.
        ``{"kind": "image", "path": str}``
            An image file, named by a path relative to this example's
            ``content/`` directory. Reading and encoding it belongs to
            whichever driver is rendering, so that base64 and media types
            stay out of this module.

        This is not :meth:`prepare_model_input`. That method builds one
        provider's payload, embeds a prompt in it, and may upload files to
        that provider; this one only says what the content is.
        """
        pass

    @abstractmethod
    def supporting_files(self) -> Dict[str, Any]:
        """Files that accompany the content without being part of it.

        A consumer that can stage files makes these available to be opened on
        demand rather than sending them up front: a figure example may carry
        several spreadsheets, and a check usually needs none of them.

        Returns:
            Role name to a content-relative path, ``None``, or a list of
            content-relative paths.
        """
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert the example to a dictionary.

        Returns:
            Dictionary representation of the example
        """
        return {
            "source_path": str(self.source_path),
            "content_hash": self.get_content_hash(),
            "model_input": self.prepare_model_input("")
        }

    def save_expected_output(
        self,
        output: Dict[str, Any],
        check_name: str,
        overwrite: bool = False
    ) -> Path:
        """Save an expected output for this example.

        Args:
            output: The output to save
            check_name: Name of the check
            overwrite: Whether to overwrite existing files (default: False)
            
        Returns:
            Path to the saved expected output file
        """
        # Create expected output directory
        expected_output_dir = self.source_path / "checks" / check_name
        expected_output_dir.mkdir(parents=True, exist_ok=True)
        expected_output_path = expected_output_dir / "expected_output.json"

        # Check if expected output already exists
        if expected_output_path.exists() and not overwrite:
            logger.info(
                f"Expected output already exists and overwrite=False: "
                f"{expected_output_path}"
            )
            return expected_output_path

        # Write expected output
        with open(expected_output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)

        # Write HTML version for easier viewing
        try:
            from soda_mmqc.lib.expected_output_html import output_to_html
            html_path = expected_output_dir / "expected_output.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(output_to_html(output, title=f"Expected output — {check_name}"))
        except Exception as e:
            logger.debug("Could not write expected_output.html: %s", e)

        logger.info(
            f"Saved expected output: {expected_output_path}"
        )
        return expected_output_path


class FigureExample(Example):
    """Example containing a figure with caption."""
    
    def __init__(self, relative_source_path: str):
        super().__init__(relative_source_path)
        self.caption: Optional[str] = None
        self.caption_path: Optional[Path] = None
        self.image_path: Optional[Path] = None
        self.figure_id: Optional[str] = None
        # Table handling: include CSV/TSV and spreadsheet files alongside images
        # If enabled, these will be included in hashing and model input preview.
        self.include_tables: bool = True
        # How many lines of table text preview to include for text tables
        self.table_preview_lines: int = 10

    def load_from_source(self) -> None:
        """Load the example's content from the provided path.

        Raises:
            FileNotFoundError: If required files are missing
            ValueError: If required data is missing
        """
        # Convert string to Path immediately
        path_obj = self.source_path
        # Pattern: doc_id/content/figure_id/content/caption.txt
        # So source_path points to figure_id, need to go up 2 levels to get 
        # doc_id
        self.doc_id = path_obj.parent.parent.name
        self.figure_id = path_obj.name

        if not self.source_path.exists():
            raise FileNotFoundError(
                f"Content directory not found: {self.source_path}"
            )

        # Load caption
        caption_path = self.source_path / "content" / "caption.txt"
        if not caption_path.exists():
            raise FileNotFoundError(
                f"Caption file not found: {caption_path}"
            )
        self.caption_path = caption_path
        with open(caption_path, "r", encoding="utf-8") as f:
            self.caption = f.read().strip()

        # Find image
        self.image_path = None
        for ext in [".png", ".jpg", ".jpeg", ".tiff", ".webp"]:
            for image_path in self.source_path.glob(f"content/*{ext}"):
                self.image_path = image_path
                break
            if self.image_path:
                break

        if not self.image_path:
            raise ValueError(
                f"No image found in {self.source_path}"
            )

    def get_content_hash(self) -> str:
        """Get a hash of the example's content for caching.
        
        Includes caption, main figure image, and any images in content/source_data/
        so cache invalidates when source data is added or changed.
        """
        self._ensure_loaded()
        if self._content_hash is None:
            hasher = hashlib.sha256()
            if self.caption is not None:
                hasher.update(self.caption.encode('utf-8'))
            if self.image_path and self.image_path.exists():
                with open(self.image_path, "rb") as f:
                    hasher.update(f.read())
            for path in self._get_all_source_data_paths():
                with open(path, "rb") as f:
                    hasher.update(f.read())
            self._content_hash = hasher.hexdigest()
        return self._content_hash

    def _encode_image(self) -> tuple[str, str]:
        """Encode image to base64 string."""
        if not self.image_path or not self.image_path.exists():
            raise ValueError("Image file not found")
        return self._encode_image_from_path(self.image_path)

    def _encode_image_from_path(self, image_path: Path) -> tuple[str, str]:
        """Encode an image file to base64 and return (mime_type, base64_string)."""
        if not image_path.exists():
            raise ValueError(f"Image file not found: {image_path}")

        mime_type, _ = mimetypes.guess_type(str(image_path))
        if not mime_type or not mime_type.startswith("image/"):
            raise ValueError(f"Not an image: {image_path}")

        with open(image_path, "rb") as f:
            image_bytes = f.read()
        
        if mime_type not in _API_SUPPORTED_IMAGE_TYPES:
            image_bytes = convert_to_bounded_jpeg(io.BytesIO(image_bytes))
            mime_type = "image/jpeg"
        return mime_type, base64.b64encode(image_bytes).decode("utf-8")

    _SOURCE_DATA_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".tiff", ".tif")
    _SOURCE_DATA_TABLE_EXTS = (".csv", ".tsv", ".xlsx", ".xls")

    def _get_source_data_items(
        self,
    ) -> List[Tuple[Optional[str], List[Path]]]:
        """Return source data as (panel_label, image_paths) items.
        
        If content/source_data/ has subdirectories, each subfolder name is
        treated as a panel label (e.g. A, B, 1G) and images inside are
        grouped under that panel. If there are no subdirectories, all images
        in source_data/ are returned as one item with panel_label None.
        """
        source_data_dir = self.source_path / "content" / "source_data"
        if not source_data_dir.is_dir():
            return []
        exts = list(self._SOURCE_DATA_IMAGE_EXTS)
        # include nested subdirectories as panels as well
        subdirs = [d for d in source_data_dir.rglob("*") if d.is_dir()]
        if subdirs:
            items: List[Tuple[Optional[str], List[Path]]] = []
            for d in sorted(subdirs):
                paths = []
                for ext in exts:
                    paths.extend(d.glob(f"*{ext}"))
                paths = sorted(paths)
                if paths:
                    items.append((d.name, paths))
            return items
        paths = []
        for ext in exts:
            paths.extend(source_data_dir.glob(f"*{ext}"))
        paths = sorted(paths)
        return [(None, paths)] if paths else []

    def _get_source_table_items(self) -> List[Tuple[Optional[str], List[Path]]]:
        """Return table files (csv/tsv/xlsx/xls) grouped the same way as images.

        Subfolders of `content/source_data/` are treated as panels. If there are
        no subfolders, any table files directly under `source_data/` are returned
        as a single group with panel_label None.
        """
        if not self.include_tables:
            return []
        # source_data_dir = self.source_path / "content" / "source_data"
        source_data_dir = self.source_path / "content"
        if not source_data_dir.is_dir():
            return []
        exts = list(self._SOURCE_DATA_TABLE_EXTS)
        # include nested subdirectories as panels as well
        subdirs = [d for d in source_data_dir.rglob("*") if d.is_dir()]
        if subdirs:
            items: List[Tuple[Optional[str], List[Path]]] = []
            for d in sorted(subdirs):
                paths: List[Path] = []
                for ext in exts:
                    paths.extend(d.glob(f"*{ext}"))
                paths = sorted(paths)
                if paths:
                    items.append((d.name, paths))
            return items
        paths: List[Path] = []
        for ext in exts:
            paths.extend(source_data_dir.glob(f"*{ext}"))
        paths = sorted(paths)
        return [(None, paths)] if paths else []

    def _upload_table_and_get_file_id(self, tpath: Path, purpose: str = "user_data") -> Optional[str]:
        """Attempt to upload a table file to the OpenAI Files API and return the file id.

        Args:
            tpath: Path to the file to upload.
            purpose: Purpose string for the Files API. Allowed values are:
                'fine-tune', 'assistants', 'batch', 'user_data', 'vision', 'evals'.

        Returns:
            file id string on success, or None on failure.
        """
        allowed = ("fine-tune", "assistants", "batch", "user_data", "vision", "evals")
        if purpose not in allowed:
            logger.warning(
                "Requested file purpose '%s' is not valid. Falling back to 'user_data'. Allowed: %s",
                purpose,
                allowed,
            )
            purpose = "user_data"

        if OpenAI is None:
            logger.debug("OpenAI client not available; skipping upload for %s", tpath)
            return None
        try:
            client = OpenAI()
            res = client.files.create(file=Path(tpath), purpose=purpose)
            # SDK may return an object with attribute `id` or a dict with key 'id'
            file_id = getattr(res, "id", None) or (res.get("id") if isinstance(res, dict) else None)
            logger.info("Uploaded file %s to OpenAI with purpose '%s', id=%s", tpath, purpose, file_id)
            return file_id
        except Exception as e:
            logger.warning("Failed to upload file %s to OpenAI (purpose=%s): %s", tpath, purpose, e)
            return None

    def _get_all_source_data_paths(self) -> List[Path]:
        """Flat list of all source data image paths (for hashing)."""
        out: List[Path] = []
        for _panel, paths in self._get_source_data_items():
            out.extend(paths)
        # include table files in the hash as well
        for _panel, tpaths in self._get_source_table_items():
            out.extend(tpaths)
        return sorted(out)

    def _get_source_data_file_list(self) -> List[str]:
        """List of all file names (and relative paths) in source_data folder.
        Recursively includes every file so the model can see e.g. .xlsx, .csv
        without opening them. Returns paths relative to source_data dir.
        """
        source_data_dir = self.source_path / "content" / "source_data"
        if not source_data_dir.is_dir():
            return []
        out: List[str] = []
        for f in sorted(source_data_dir.rglob("*")):
            if f.is_file():
                try:
                    rel = f.relative_to(source_data_dir)
                    out.append(rel.as_posix())
                except ValueError:
                    out.append(f.name)
        return sorted(out)

    def input_parts(self) -> List[Dict[str, Any]]:
        """A figure is its caption and its image, in that order."""
        self._ensure_loaded()
        content = self.source_path / "content"
        return [
            {"kind": "text", "text": f"Figure caption:\n{self.caption}"},
            {
                "kind": "image",
                "path": self.image_path.relative_to(content).as_posix(),
            },
        ]

    def supporting_files(self) -> Dict[str, Any]:
        """Source data: available on request, not sent up front.

        Seven spreadsheets on a single figure is normal here, and a check
        usually needs none of them.
        """
        self._ensure_loaded()
        return {
            "source_data": [
                f"source_data/{name}"
                for name in self._get_source_data_file_list()
            ]
        }

    def prepare_model_input(
        self, prompt: str, model_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare the example's content for model input.
        
        When model_config has source_data_files.enabled, also includes any
        images from content/source_data/ so the model can compare them to the figure.
        """
        self._ensure_loaded()
        fig_mime, fig_b64 = self._encode_image()
        content: List[Dict[str, Any]] = [
            {
                "type": "input_text",
                "text": f"{prompt}\n\nFigure Caption:\n{self.caption}"
            },
            {
                "type": "input_image",
                "image_url": f"data:{fig_mime};base64,{fig_b64}"
            }
        ]
        # Include source data files if this check requests them
        if model_config:
            source_config = model_config.get("source_data_files") or {}
            if source_config.get("enabled"):
                # First add image source data as before
                for panel_label, paths in self._get_source_data_items():
                    group_header = (
                        f"Source data for panel {panel_label}:"
                        if panel_label is not None
                        else "Source data files:"
                    )
                    for path in paths:
                        try:
                            mime_type, b64 = self._encode_image_from_path(path)
                            logger.info("Including source image in model input: %s", path)
                            content.append({
                                "type": "input_text",
                                "text": f"{group_header} {path.name}".strip()
                            })
                            content.append({
                                "type": "input_image",
                                "image_url": f"data:{mime_type};base64,{b64}"
                            })
                            group_header = ""  # subsequent images: filename only in next text
                        except Exception as e:
                            logger.warning(
                                "Skipping source data file %s: %s", path, e
                            )

                # Then add any table-like source data — strictly upload files
                # and reference them as `input_file`. If upload fails, log a
                # warning and do not include any inline text preview or
                # filename notes.
                upload_purpose = None
                if model_config:
                    upload_purpose = model_config.get("openai_file_purpose")
                # default to 'user_data' when not provided
                if not upload_purpose:
                    upload_purpose = "user_data"

                for panel_label, tpaths in self._get_source_table_items():
                    for tpath in tpaths:
                        try:
                            file_id = self._upload_table_and_get_file_id(tpath, purpose=upload_purpose)
                            if file_id:
                                content.append({
                                    "type": "input_file",
                                    "file_id": file_id,
                                })
                            else:
                                logger.warning(
                                    "Could not upload source table %s; skipping it."
                                    " Ensure OpenAI client is configured and reachable.",
                                    tpath,
                                )
                        except Exception as e:
                            logger.warning("Skipping source table file %s: %s", tpath, e)
        return {"content": content}

    def to_dict(self) -> Dict[str, Any]:
        """Convert the example to a dictionary.
        
        Returns:
            Dictionary representation of the example
        """
        base_dict = super().to_dict()
        base_dict["figure_id"] = self.figure_id
        return base_dict


class WordExample(Example):
    """Example containing a manuscript converted to HTML for model input."""

    def __init__(self, relative_source_path: str):
        super().__init__(relative_source_path)
        self.content: Optional[str] = None
        self.word_file_path: Optional[Path] = None

    def load_from_source(self) -> None:
        """Load manuscript HTML from exactly one .docx in content/.

        Raises:
            FileNotFoundError: If source, content directory, or .docx is missing
            ValueError: If multiple .docx files are present or conversion fails
        """
        if not self.source_path.exists():
            raise FileNotFoundError(
                f"Content directory not found: {self.source_path}"
            )

        content_path = self.source_path / "content"
        if not content_path.exists():
            raise FileNotFoundError(
                f"Content directory not found: {content_path}"
            )

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

        word_file_path = word_files[0]
        self.word_file_path = word_file_path

        try:
            self.content = document_to_html(word_file_path)
        except DocumentConversionError as e:
            raise ValueError(
                f"Error converting Word file {word_file_path}: {e}"
            ) from e
        except Exception as e:
            raise ValueError(
                f"Error reading Word file {word_file_path}: {e}"
            ) from e

        self.doc_id = self.source_path.name

    def get_content_hash(self) -> str:
        """Get a hash of the example's content for caching.
        
        Returns:
            A string hash of the content
        """
        self._ensure_loaded()
        if self._content_hash is None:
            hasher = hashlib.sha256()
            if self.content is not None:
                hasher.update(self.content.encode('utf-8'))
            self._content_hash = hasher.hexdigest()
        return self._content_hash

    def prepare_model_input(
        self, prompt: str, model_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Prepare the example's content for model input."""
        self._ensure_loaded()
        return {
            "content": [
                {
                    "type": "input_text",
                    "text": f"{prompt}\n\nContent:\n{self.content}"
                }
            ]
        }

    def input_parts(self) -> List[Dict[str, Any]]:
        """A manuscript is its text.

        ``load_from_source`` already converted the document to HTML; that
        conversion is a rendering of this example's content, not a file the
        example is made of, so it travels as a part and is never written
        anywhere.
        """
        self._ensure_loaded()
        return [{"kind": "text", "text": self.content}]

    def supporting_files(self) -> Dict[str, Any]:
        """Nothing: a manuscript's content is the manuscript.

        The document is staged like every other file of the example, but it
        is not listed as something to fetch -- its content was already sent
        as a part. Listing it would invite a session to open a `.docx` it
        cannot read in order to obtain text it already has.
        """
        self._ensure_loaded()
        return {}


# Register example types
EXAMPLE_TYPES["figure"] = FigureExample
EXAMPLE_TYPES["word"] = WordExample


class ExampleFactory:
    """Factory for creating Example instances.
    
    Simple factory that maps example types to their classes.
    """

    def __init__(self):
        self._example_types = EXAMPLE_TYPES.copy()

    def create(self, relative_source_path: str, example_type: str, **kwargs) -> Example:
        """Create an example from a source path.
        
        Args:
            source_path: Path to the example source directory
            example_type: Type of example to create ("figure" or "word")
            
        Returns:
            Example instance
            
        Raises:
            ValueError: If example_type is not supported
        """
        if example_type not in self._example_types:
            raise ValueError(
                f"Unsupported example type: {example_type}. "
                f"Supported types: {list(self._example_types.keys())}"
            )

        example_class = self._example_types[example_type]
        example = example_class(relative_source_path, **kwargs)
        
        # Set the example type identifier
        example.example_class_name = example_type
        
        # Explicitly load the content after initialization
        example.load_from_source()
        
        if example.doc_id is None:
            raise ValueError(
                f"Example at {relative_source_path} has no doc_id!"
            )
        return example


# Create a default factory instance
EXAMPLE_FACTORY = ExampleFactory()
