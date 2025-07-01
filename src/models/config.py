from typing import List
from fastapi import HTTPException

# Supported Claude model names (verified with Claude CLI)
SUPPORTED_MODELS: List[str] = [
    # Claude model aliases (tested and working)
    "sonnet",
    "opus", 
    
    # Full Claude model names (theoretical - need testing)
    "claude-sonnet-4-20250514",
    "claude-opus-3-20240229",
]

DEFAULT_MODEL = "sonnet"

def validate_model(requested_model: str) -> str:
    """Validate Claude model name and return it, or raise error for unknown models."""
    if requested_model in SUPPORTED_MODELS:
        return requested_model
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{requested_model}' is not supported. Supported models: {', '.join(SUPPORTED_MODELS)}"
        )

def get_supported_models() -> List[str]:
    """Get list of all supported model names."""
    return SUPPORTED_MODELS.copy()