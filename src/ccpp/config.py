"""Configuration management for CC++ PII masking system.

This module provides utilities for loading and managing configuration from YAML files.
Supports environment-specific configs with inheritance.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    raise ImportError(
        "PyYAML required for config loading. Install with: uv pip install pyyaml"
    )

from ccpp.types import ApprovedModel
import logging

logger = logging.getLogger(__name__)


def _validate_model_names(config_data: Dict[str, Any]) -> None:
    """Validate that model names in config are approved models.

    Args:
        config_data: Configuration dictionary

    Raises:
        ValueError: If an unapproved model is found
    """
    # Check Stage 1 model
    if "stage1" in config_data and "model_name" in config_data["stage1"]:
        model = config_data["stage1"]["model_name"]
        if not ApprovedModel.is_valid(model):
            raise ValueError(
                f"Stage 1 model '{model}' is not approved. "
                f"Approved models: {[m.value for m in ApprovedModel]}"
            )

    # Check Stage 2 model
    if "stage2" in config_data and "model_name" in config_data["stage2"]:
        model = config_data["stage2"]["model_name"]
        if not ApprovedModel.is_valid(model):
            raise ValueError(
                f"Stage 2 model '{model}' is not approved. "
                f"Approved models: {[m.value for m in ApprovedModel]}"
            )


class Config:
    """Configuration container with dot-notation access.

    Example:
        config = Config({"stage1": {"backend": "ollama"}})
        print(config.stage1.backend)  # "ollama"
    """

    def __init__(self, data: Dict[str, Any]):
        """Initialize config from dict."""
        self._data = data
        for key, value in data.items():
            if isinstance(value, dict):
                setattr(self, key, Config(value))
            else:
                setattr(self, key, value)

    def __getitem__(self, key: str) -> Any:
        """Dict-style access."""
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Get with default value."""
        return self._data.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert back to plain dict."""
        result = {}
        for key, value in self._data.items():
            if isinstance(value, Config):
                result[key] = value.to_dict()
            else:
                result[key] = value
        return result

    def __repr__(self) -> str:
        return f"Config({self._data})"


def load_config(
    config_path: Optional[str] = None,
    environment: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
) -> Config:
    """Load configuration from YAML files with environment support.

    Args:
        config_path: Path to config file. If not provided, loads from configs/ dir
        environment: Environment name (e.g., "dev", "prod"). Merges env-specific config
        overrides: Dict of values to override in final config

    Returns:
        Config object with loaded settings

    Example:
        # Load default config
        config = load_config()

        # Load dev config (merges default.yaml + dev.yaml)
        config = load_config(environment="dev")

        # Load with custom path
        config = load_config(config_path="custom.yaml")

        # Load with overrides
        config = load_config(
            environment="dev",
            overrides={"stage1": {"model_name": "qwen3:1.7b"}}
        )
    """
    # Determine config directory
    if config_path:
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        with open(config_file, "r") as f:
            config_data = yaml.safe_load(f) or {}
    else:
        # Load from configs/ directory
        repo_root = Path(__file__).parent.parent.parent
        configs_dir = repo_root / "configs"

        # Load default config
        default_path = configs_dir / "default.yaml"
        if not default_path.exists():
            raise FileNotFoundError(
                f"Default config not found: {default_path}. "
                "Ensure configs/default.yaml exists."
            )

        with open(default_path, "r") as f:
            config_data = yaml.safe_load(f) or {}

        # Merge environment-specific config if provided
        if environment:
            env_path = configs_dir / f"{environment}.yaml"
            if env_path.exists():
                with open(env_path, "r") as f:
                    env_data = yaml.safe_load(f) or {}
                config_data = _deep_merge(config_data, env_data)
            else:
                # Environment not found, but that's okay - use default
                pass

    # Apply overrides if provided
    if overrides:
        config_data = _deep_merge(config_data, overrides)

    # Check for environment variable overrides
    config_data = _apply_env_overrides(config_data)

    # Validate model names are approved
    _validate_model_names(config_data)

    return Config(config_data)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dicts, with override taking precedence.

    Args:
        base: Base dict
        override: Dict with overriding values

    Returns:
        Merged dict
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to config.

    Environment variables are prefixed with CCPP_ and use double underscores
    for nesting. For example:
        CCPP_STAGE1__BACKEND=anthropic
        CCPP_STAGE1__MODEL_NAME=claude-haiku-4-5-20251001
        CCPP_STREAMING__STREAM_BREAK_TIMEOUT_MS=300

    Args:
        config: Config dict

    Returns:
        Config dict with environment overrides applied
    """
    prefix = "CCPP_"
    for env_var, value in os.environ.items():
        if not env_var.startswith(prefix):
            continue

        # Parse env var path (e.g., CCPP_STAGE1__BACKEND -> ["stage1", "backend"])
        path = env_var[len(prefix):].lower().split("__")

        # Navigate to the right place in config
        current = config
        for i, key in enumerate(path[:-1]):
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set the value (try to parse as int/float/bool if possible)
        final_key = path[-1]
        try:
            # Try int
            current[final_key] = int(value)
        except ValueError:
            try:
                # Try float
                current[final_key] = float(value)
            except ValueError:
                # Try bool
                if value.lower() in ("true", "false"):
                    current[final_key] = value.lower() == "true"
                else:
                    # Keep as string
                    current[final_key] = value

    return config


def get_stage1_config(config: Config) -> Dict[str, Any]:
    """Extract Stage 1 backend configuration.

    Args:
        config: Main config object

    Returns:
        Dict suitable for passing to create_backend_from_config() and Stage1Router
    """
    result = {
        "backend": config.stage1.backend,
        "model_name": config.stage1.model_name,
        "timeout": config.stage1.timeout,
        "temperature": config.stage1.temperature,
        "max_tokens": config.stage1.max_tokens,
    }

    # Add optional fields if present
    if hasattr(config.stage1, "few_shot"):
        result["few_shot"] = config.stage1.few_shot.to_dict() if isinstance(config.stage1.few_shot, Config) else config.stage1.few_shot

    if hasattr(config.stage1, "system_prompt"):
        result["system_prompt"] = config.stage1.system_prompt

    if hasattr(config.stage1, "logit_extraction"):
        result["logit_extraction"] = config.stage1.logit_extraction.to_dict() if isinstance(config.stage1.logit_extraction, Config) else config.stage1.logit_extraction
    elif hasattr(config.stage1, "token_a") and hasattr(config.stage1, "token_b"):
        # Fallback: extract token_a and token_b directly
        result["logit_extraction"] = {
            "token_a": config.stage1.token_a,
            "token_b": config.stage1.token_b,
        }

    return result


def get_stage2_config(config: Config) -> Dict[str, Any]:
    """Extract Stage 2 backend configuration.

    Args:
        config: Main config object

    Returns:
        Dict suitable for passing to create_backend_from_config() and Stage2Redactor
    """
    result = {
        "backend": config.stage2.backend,
        "model_name": config.stage2.model_name,
        "timeout": config.stage2.timeout,
        "temperature": config.stage2.temperature,
        "max_tokens": config.stage2.max_tokens,
    }

    # Add optional fields if present
    if hasattr(config.stage2, "few_shot"):
        result["few_shot"] = config.stage2.few_shot.to_dict() if isinstance(config.stage2.few_shot, Config) else config.stage2.few_shot

    if hasattr(config.stage2, "system_prompt"):
        result["system_prompt"] = config.stage2.system_prompt

    return result


# Convenience function for loading default config
def load_default_config() -> Config:
    """Load default configuration.

    Checks for CCPP_ENV environment variable to determine environment.
    Falls back to default.yaml if not set.

    Returns:
        Config object
    """
    environment = os.environ.get("CCPP_ENV")
    return load_config(environment=environment)
