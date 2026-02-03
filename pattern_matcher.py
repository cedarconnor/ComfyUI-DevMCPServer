"""
Pattern Matcher - Match errors against known patterns with actionable suggestions.
"""

import json
import os
from typing import Optional, Dict, Any, List

# Built-in error patterns
BUILTIN_PATTERNS = [
    {
        "id": "cuda_oom",
        "pattern": r"CUDA out of memory",
        "title": "CUDA Out of Memory",
        "suggestion": "Try reducing batch size, image resolution, or enable CPU offloading. You can also try `--lowvram` or `--cpu` flags when starting ComfyUI."
    },
    {
        "id": "mps_oom",
        "pattern": r"MPS backend out of memory",
        "title": "MPS Out of Memory (Apple Silicon)",
        "suggestion": "Reduce image resolution or batch size. Consider using `--force-fp16` to reduce memory usage."
    },
    {
        "id": "module_not_found",
        "pattern": r"ModuleNotFoundError: No module named '(\w+)'",
        "title": "Missing Python Module",
        "suggestion": "Install the missing module with: `pip install {match}`"
    },
    {
        "id": "type_mismatch_fp16",
        "pattern": r"expected .*(Float|Half).*got.*(Half|Float)",
        "title": "Float Type Mismatch (fp16/fp32)",
        "suggestion": "There's a data type conflict between nodes. Try adding a 'Convert' node or check model compatibility. Some models require fp16 while others need fp32."
    },
    {
        "id": "dimension_mismatch",
        "pattern": r"size mismatch|shape mismatch|dimension",
        "title": "Tensor Dimension Mismatch",
        "suggestion": "The tensor shapes don't match between connected nodes. Check that image resolutions and batch sizes are compatible throughout your workflow."
    },
    {
        "id": "safetensors_error",
        "pattern": r"safetensors.*error|Error loading.*\.safetensors",
        "title": "SafeTensors Loading Error",
        "suggestion": "The model file may be corrupted or incompatible. Try re-downloading the model or check if it's the correct format for this node."
    },
    {
        "id": "file_not_found",
        "pattern": r"FileNotFoundError|No such file or directory",
        "title": "File Not Found",
        "suggestion": "Check that the file path is correct and the file exists. For models, ensure they're in the correct ComfyUI models subdirectory."
    },
    {
        "id": "key_error",
        "pattern": r"KeyError: '(\w+)'",
        "title": "Missing Key Error",
        "suggestion": "The workflow expects a key '{match}' that doesn't exist. This often happens with incompatible model versions or missing workflow components."
    },
    {
        "id": "attribute_error",
        "pattern": r"AttributeError: '(\w+)' object has no attribute '(\w+)'",
        "title": "Attribute Error",
        "suggestion": "An object doesn't have the expected attribute. This may indicate version incompatibility between custom nodes or outdated code."
    },
    {
        "id": "cudnn_error",
        "pattern": r"cuDNN error|CUDNN_STATUS",
        "title": "cuDNN Error",
        "suggestion": "CUDA/cuDNN configuration issue. Try updating your NVIDIA drivers or reinstalling PyTorch with the correct CUDA version."
    },
    {
        "id": "insightface_missing",
        "pattern": r"insightface|buffalo_l",
        "title": "InsightFace Not Installed",
        "suggestion": "Install InsightFace with: `pip install insightface`. For face-related nodes, you may also need to download the 'buffalo_l' model."
    },
    {
        "id": "controlnet_mismatch",
        "pattern": r"ControlNet.*mismatch|control.*dimension",
        "title": "ControlNet Model Mismatch",
        "suggestion": "The ControlNet model doesn't match the base model. Ensure you're using a ControlNet trained for your specific base model (SD1.5, SDXL, etc.)."
    },
    {
        "id": "lora_incompatible",
        "pattern": r"LoRA.*incompatible|lora.*key.*missing",
        "title": "LoRA Incompatibility",
        "suggestion": "The LoRA was trained for a different base model. Check that the LoRA matches your checkpoint (SD1.5 LoRA for SD1.5 model, etc.)."
    },
    {
        "id": "vae_decode_error",
        "pattern": r"VAE.*decode|vae.*error",
        "title": "VAE Decode Error",
        "suggestion": "Try using a different VAE or the built-in VAE. Some models require specific VAE files for proper decoding."
    },
    {
        "id": "invalid_prompt",
        "pattern": r"invalid prompt|prompt.*json.*error",
        "title": "Invalid Prompt Format",
        "suggestion": "The workflow JSON is malformed. Check for missing connections or invalid node configurations."
    },
    {
        "id": "connection_refused",
        "pattern": r"Connection refused|ConnectionRefusedError",
        "title": "Connection Refused",
        "suggestion": "A network connection failed. If using external APIs, check your internet connection and API endpoint."
    },
    {
        "id": "permission_denied",
        "pattern": r"PermissionError|Permission denied",
        "title": "Permission Denied",
        "suggestion": "ComfyUI doesn't have permission to access this file or directory. Check file permissions or run ComfyUI with appropriate privileges."
    },
    {
        "id": "torch_no_grad",
        "pattern": r"element 0 of tensors does not require grad",
        "title": "Gradient Computation Error",
        "suggestion": "A node is trying to compute gradients on a tensor that doesn't require them. This is usually a node implementation issue."
    },
    {
        "id": "animatediff_error",
        "pattern": r"AnimateDiff|motion.*module",
        "title": "AnimateDiff Error",
        "suggestion": "Check that you have the correct motion module installed and it's compatible with your base model."
    },
    {
        "id": "ipadapter_error",
        "pattern": r"IPAdapter|ip.*adapter",
        "title": "IPAdapter Error",
        "suggestion": "Ensure IPAdapter models are in the correct directory and match your base model version."
    }
]


def load_patterns() -> List[Dict[str, str]]:
    """Load all error patterns (builtin + custom)."""
    patterns = BUILTIN_PATTERNS.copy()
    
    # Try to load custom patterns from patterns/ directory
    patterns_dir = os.path.join(os.path.dirname(__file__), "patterns")
    if os.path.exists(patterns_dir):
        for filename in os.listdir(patterns_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(patterns_dir, filename), 'r') as f:
                        custom_patterns = json.load(f)
                        if isinstance(custom_patterns, list):
                            patterns.extend(custom_patterns)
                except Exception:
                    pass  # Silently skip invalid pattern files
    
    return patterns


def match_error(error_text: str) -> Optional[Dict[str, Any]]:
    """
    Match an error against known patterns.
    
    Returns the first matching pattern with its suggestion, or None if no match.
    """
    import re
    
    if not error_text:
        return None
    
    patterns = load_patterns()
    
    for pattern_def in patterns:
        pattern = pattern_def.get("pattern", "")
        try:
            match = re.search(pattern, error_text, re.IGNORECASE)
            if match:
                # Replace {match} placeholder with actual matched group
                suggestion = pattern_def.get("suggestion", "")
                if match.groups():
                    suggestion = suggestion.replace("{match}", match.group(1))
                
                return {
                    "pattern_id": pattern_def.get("id", "unknown"),
                    "title": pattern_def.get("title", "Unknown Error"),
                    "suggestion": suggestion,
                    "matched_text": match.group(0)
                }
        except re.error:
            continue  # Skip invalid regex patterns
    
    return None


def get_pattern_count() -> int:
    """Get the total number of loaded patterns."""
    return len(load_patterns())
