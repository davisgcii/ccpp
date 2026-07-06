"""Tests for configuration management."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from ccpp.config import (
    Config,
    load_config,
    get_stage1_config,
    get_stage2_config,
    get_masking_config,
    load_default_config,
    _deep_merge,
    _apply_env_overrides,
)
from ccpp.types import ApprovedModel, MaskingConfig, PIICategory, MaskSpan


class TestConfig:
    """Tests for Config class."""

    def test_config_dot_access(self):
        """Test dot-notation access."""
        config = Config({"stage1": {"backend": "ollama", "model": "qwen3:1.7b"}})
        assert config.stage1.backend == "ollama"
        assert config.stage1.model == "qwen3:1.7b"

    def test_config_dict_access(self):
        """Test dict-style access."""
        config = Config({"stage1": {"backend": "ollama"}})
        assert config["stage1"]["backend"] == "ollama"

    def test_config_nested(self):
        """Test nested config access."""
        data = {
            "level1": {
                "level2": {
                    "level3": "value"
                }
            }
        }
        config = Config(data)
        assert config.level1.level2.level3 == "value"

    def test_config_to_dict(self):
        """Test converting back to dict."""
        data = {"stage1": {"backend": "ollama"}}
        config = Config(data)
        assert config.to_dict() == data


class TestDeepMerge:
    """Tests for deep merge functionality."""

    def test_deep_merge_simple(self):
        """Test merging simple dicts."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested(self):
        """Test merging nested dicts."""
        base = {"stage1": {"backend": "ollama", "timeout": 60}}
        override = {"stage1": {"timeout": 30}}
        result = _deep_merge(base, override)
        assert result == {"stage1": {"backend": "ollama", "timeout": 30}}

    def test_deep_merge_preserves_base(self):
        """Test that base dict is not modified."""
        base = {"a": 1}
        override = {"b": 2}
        result = _deep_merge(base, override)
        assert base == {"a": 1}  # Unchanged
        assert result == {"a": 1, "b": 2}


class TestEnvOverrides:
    """Tests for environment variable overrides."""

    def test_env_override_simple(self):
        """Test simple env var override."""
        config = {"stage1": {"backend": "ollama"}}
        with patch.dict(os.environ, {"CCPP_STAGE1__BACKEND": "anthropic"}):
            result = _apply_env_overrides(config)
            assert result["stage1"]["backend"] == "anthropic"

    def test_env_override_int(self):
        """Test int parsing from env var."""
        config = {"streaming": {"timeout_ms": 500}}
        with patch.dict(os.environ, {"CCPP_STREAMING__TIMEOUT_MS": "300"}):
            result = _apply_env_overrides(config)
            assert result["streaming"]["timeout_ms"] == 300
            assert isinstance(result["streaming"]["timeout_ms"], int)

    def test_env_override_float(self):
        """Test float parsing from env var."""
        config = {"streaming": {"ema_beta": 0.85}}
        with patch.dict(os.environ, {"CCPP_STREAMING__EMA_BETA": "0.9"}):
            result = _apply_env_overrides(config)
            assert result["streaming"]["ema_beta"] == 0.9
            assert isinstance(result["streaming"]["ema_beta"], float)

    def test_env_override_bool(self):
        """Test bool parsing from env var."""
        config = {"heuristics": {"enabled": True}}
        with patch.dict(os.environ, {"CCPP_HEURISTICS__ENABLED": "false"}):
            result = _apply_env_overrides(config)
            assert result["heuristics"]["enabled"] is False

    def test_env_override_ignores_non_ccpp(self):
        """Test that non-CCPP env vars are ignored."""
        config = {"stage1": {"backend": "ollama"}}
        with patch.dict(os.environ, {"OTHER_VAR": "value"}):
            result = _apply_env_overrides(config)
            assert result == config


class TestLoadConfig:
    """Tests for config loading."""

    def test_load_default_config(self):
        """Test loading default config."""
        config = load_config()
        assert hasattr(config, "stage1")
        assert hasattr(config, "stage2")
        assert hasattr(config, "streaming")
        assert hasattr(config, "heuristics")

    def test_load_with_overrides(self):
        """Test loading with runtime overrides."""
        config = load_config(
            overrides={"stage1": {"model_name": ApprovedModel.CLAUDE_HAIKU_4_5.value}}
        )
        assert config.stage1.model_name == ApprovedModel.CLAUDE_HAIKU_4_5.value

    def test_load_with_invalid_model(self):
        """Test that unapproved models are rejected."""
        with pytest.raises(ValueError, match="not approved"):
            load_config(
                overrides={"stage1": {"model_name": "invalid:model"}}
            )

    def test_load_nonexistent_environment(self):
        """Test loading non-existent environment falls back to default."""
        config = load_config(environment="nonexistent")
        # Should not raise, just use default
        assert hasattr(config, "stage1")


class TestConfigExtractors:
    """Tests for config extraction helpers."""

    def test_get_stage1_config(self):
        """Test extracting Stage 1 config."""
        config = load_config()
        stage1 = get_stage1_config(config)

        assert "backend" in stage1
        assert "model_name" in stage1
        assert "timeout" in stage1
        assert "temperature" in stage1
        assert "max_tokens" in stage1

    def test_get_stage2_config(self):
        """Test extracting Stage 2 config."""
        config = load_config()
        stage2 = get_stage2_config(config)

        assert "backend" in stage2
        assert "model_name" in stage2
        assert "timeout" in stage2
        assert "temperature" in stage2
        assert "max_tokens" in stage2

    def test_stage_configs_are_dicts(self):
        """Test that stage configs can be passed to backend factory."""
        config = load_config()
        stage1 = get_stage1_config(config)
        stage2 = get_stage2_config(config)

        # Should be plain dicts suitable for create_backend_from_config
        assert isinstance(stage1, dict)
        assert isinstance(stage2, dict)

    def test_get_masking_config_from_default(self):
        """Default config maps to a usable MaskingConfig."""
        config = load_config()
        masking = get_masking_config(config)
        assert isinstance(masking, MaskingConfig)
        assert masking.case_sensitive is True
        assert masking.category_formats.get("person") == "[PERSON]"

    def test_masking_config_honors_overrides(self):
        """Config overrides flow into masking behavior."""
        config = load_config(
            overrides={"masking": {"case_sensitive": False}}
        )
        masking = get_masking_config(config)
        assert masking.case_sensitive is False
        # Case-insensitive masking now catches a case-mismatched name.
        spans = [MaskSpan(entity_text="john", category=PIICategory.PERSON)]
        assert masking.apply("John here", spans) == "[PERSON] here"


class TestStreamingConfigWiring:
    """Regression tests for streaming config -> guard wiring (PR1)."""

    def test_default_config_exposes_risk_threshold(self):
        """Default config must expose streaming.risk_threshold."""
        config = load_config()
        assert hasattr(config.streaming, "risk_threshold")
        assert 0.0 <= config.streaming.risk_threshold <= 1.0

    def test_risk_threshold_reaches_guard(self):
        """A custom risk_threshold must flow into the guard, not be dropped.

        Regression: gui/state.py previously omitted risk_threshold_immediate,
        so the guard silently kept its 0.7 default and config changes had no
        effect. This mirrors how state.py constructs the guard.
        """
        from ccpp.infer.guard import ExchangePIIGuard

        config = load_config(overrides={"streaming": {"risk_threshold": 0.42}})
        guard = ExchangePIIGuard(
            risk_threshold_immediate=config.streaming.get("risk_threshold", 0.7),
        )
        assert guard.risk_threshold_immediate == 0.42

    def test_diagnostic_prompt_mode_is_full_by_default(self):
        """Default must be 'full' to avoid a redundant Stage 1 forward pass.

        'both'/'minimal' run an extra full forward pass per classification for
        diagnostics only; that should never be the shipped default.
        """
        config = load_config()
        assert config.stage1.diagnostic_prompt_mode == "full"
