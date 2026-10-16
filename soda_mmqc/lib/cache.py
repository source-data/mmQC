import json
import hashlib
import math
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class ModelCache:
    """Manages caching of model outputs with metadata."""
    
    def __init__(self, cache_dir: Path):
        """Initialize the cache manager.
        
        Args:
            cache_dir: Directory to store cached outputs
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _generate_cache_key(self, data: Dict[str, Any]) -> str:
        """Generate a unique cache key for the given inputs.
        
        Args:
            inputs: Dictionary containing model inputs
            
        Returns:
            String hash of the inputs
        """
        # Recursively sanitize data to ensure JSON-compliance (remove NaN/Inf
        # and convert numpy scalars) before hashing.
        def _sanitize(obj):
            # None, bool, int
            if obj is None or isinstance(obj, bool) or isinstance(obj, int):
                return obj
            # Floats: reject NaN/Inf
            if isinstance(obj, float):
                if not math.isfinite(obj):
                    return None
                return obj
            # Lists/tuples
            if isinstance(obj, (list, tuple)):
                return [_sanitize(v) for v in obj]
            # Dicts
            if isinstance(obj, dict):
                return {k: _sanitize(v) for k, v in obj.items()}
            # numpy scalars and other objects with .item() or .tolist()
            try:
                if hasattr(obj, "item"):
                    return _sanitize(obj.item())
                if hasattr(obj, "tolist"):
                    return _sanitize(obj.tolist())
            except Exception:
                pass
            # Fallback to string
            return str(obj)

        sanitized = _sanitize(data)
        sorted_data = json.dumps(sanitized, sort_keys=True)
        return hashlib.sha256(sorted_data.encode()).hexdigest()

    def generate_cache_key(
        self,
        model_input,
        check_name: str,
        model: str,
        model_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a cache key for model input.
        
        Args:
            model_input: The ModelInput object containing example, prompt, and
                schema
            check_name: Name of the check being processed
            model: The model being used for generation
            model_config: Optional API options (e.g. tools). Included so
                cache differs when config differs.
            
        Returns:
            String hash of the cache key data
        """
        cache_key_data = {
            "content_hash": model_input.example.get_content_hash(),
            "prompt": model_input.prompt,
            "schema": model_input.schema,
            "check_name": check_name,
            "model": model,
        }
        # If a prompt_name (full prompt path/key) is available on the
        # model_input, include it so different prompts with the same text
        # but different origins do not collide in cache.
        prompt_name = getattr(model_input, "prompt_name", None)
        if prompt_name:
            cache_key_data["prompt_name"] = prompt_name
        if model_config is not None:
            cache_key_data["model_config"] = model_config
        return self._generate_cache_key(cache_key_data)

    def get_cached_output(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached output for given cache key if it exists.
        
        Args:
            cache_key: String hash of the cache key data
            
        Returns:
            Cached output if found, None otherwise
        """
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def cache_output(
        self,
        cache_key: str,
        data: Dict[str, Any],
        metadata: Dict[str, Any] = {}
    ) -> None:
        """Cache model output with metadata.

        Args:
            cache_key: String hash of the cache key data
            data: Model output to cache
            metadata: Additional metadata about the model call
        """
        cache_file = self.cache_dir / f"{cache_key}.json"

        cache_entry = {
            "data": data,
            "metadata": {
                **metadata,
                "cached_at": datetime.now().isoformat()
            }
        }
        # Sanitize before writing to disk to avoid JSON errors from NaN/Inf
        try:
            def _sanitize_for_dump(obj):
                if obj is None or isinstance(obj, bool) or isinstance(obj, int):
                    return obj
                if isinstance(obj, float):
                    if not math.isfinite(obj):
                        return None
                    return obj
                if isinstance(obj, (list, tuple)):
                    return [_sanitize_for_dump(v) for v in obj]
                if isinstance(obj, dict):
                    return {k: _sanitize_for_dump(v) for k, v in obj.items()}
                try:
                    if hasattr(obj, "item"):
                        return _sanitize_for_dump(obj.item())
                    if hasattr(obj, "tolist"):
                        return _sanitize_for_dump(obj.tolist())
                except Exception:
                    pass
                return obj

            safe_entry = _sanitize_for_dump(cache_entry)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(safe_entry, f, indent=2, ensure_ascii=False)
        except Exception:
            # Last resort: stringify problematic parts
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"data": str(data), "metadata": str(metadata)}, f, indent=2, ensure_ascii=False)