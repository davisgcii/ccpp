"""Pytest configuration and fixtures for CC++ tests."""

import pytest
from unittest.mock import Mock, MagicMock
from typing import List, Dict

from ccpp.types import (
    PIICategory,
    RiskScore,
    MaskSpan,
    RedactorOutput,
    HoldbackBuffer,
    RiskState,
    ApprovedModel,
)
from ccpp.llm.base import LLMBackend, GenerationConfig, LogitExtractionConfig


@pytest.fixture
def sample_messages() -> List[Dict[str, str]]:
    """Sample conversation messages."""
    return [
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "I'm doing well, thanks!"},
    ]


@pytest.fixture
def sample_pii_text() -> str:
    """Sample text containing PII."""
    return "My email is john.doe@company.com and my phone is 555-123-4567."


@pytest.fixture
def sample_safe_text() -> str:
    """Sample safe text without PII."""
    return "Hello, how are you doing today?"


@pytest.fixture
def mock_llm_backend() -> Mock:
    """Mock LLM backend for testing."""
    backend = Mock(spec=LLMBackend)

    # Default behavior: return "SAFE" for classification
    backend.generate.return_value = "SAFE"
    backend.extract_logit_probs.return_value = (0.9, 0.1)  # (prob_safe, prob_risk)
    backend.stream_generate.return_value = iter(["Hello", " ", "there", "!"])

    return backend


@pytest.fixture
def stage1_config() -> Dict:
    """Stage 1 configuration for testing."""
    return {
        "backend": "ollama",
        "model_name": ApprovedModel.QWEN3_1_7B.value,
        "generation": {
            "max_tokens": 5,
            "temperature": 0.0,
            "do_sample": False,
            "stop_sequences": ["\n"],
        },
        "logit_extraction": {
            "token_a": "SAFE",
            "token_b": "FAIL",
        },
        "few_shot": {
            "enabled": True,
            "num_examples": 2,
            "examples": [
                {
                    "messages": [],
                    "current_buffer": "Hello there",
                    "label": "SAFE",
                },
                {
                    "messages": [],
                    "current_buffer": "My email is test@example.com",
                    "label": "FAIL",
                },
            ],
        },
        "system_prompt": "You are a PII classifier. Respond SAFE or FAIL.",
    }


@pytest.fixture
def stage2_config() -> Dict:
    """Stage 2 configuration for testing."""
    return {
        "backend": "ollama",
        "model_name": ApprovedModel.QWEN3_1_7B.value,
        "generation": {
            "max_tokens": 150,
            "temperature": 0.0,
            "do_sample": False,
        },
        "few_shot": {
            "enabled": True,
            "num_examples": 2,
            "examples": [
                {
                    "messages": [],
                    "window_text": "Contact me at alice@company.com",
                    "output": 'MASK "alice@company.com" contact',
                },
                {
                    "messages": [],
                    "window_text": "Hello there",
                    "output": "PASS",
                },
            ],
        },
        "system_prompt": "You are a PII entity extractor. Output PASS or MASK \"entity\" category.",
    }


@pytest.fixture
def sample_mask_spans() -> List[MaskSpan]:
    """Sample mask spans for testing."""
    return [
        MaskSpan(entity_text="john.doe@company.com", category=PIICategory.CONTACT),
        MaskSpan(entity_text="555-123-4567", category=PIICategory.CONTACT),
    ]


@pytest.fixture
def generation_config() -> GenerationConfig:
    """Sample generation config."""
    return GenerationConfig(
        max_tokens=100,
        temperature=0.0,
        top_p=1.0,
        do_sample=False,
    )


@pytest.fixture
def logit_extraction_config() -> LogitExtractionConfig:
    """Sample logit extraction config."""
    return LogitExtractionConfig(token_a="SAFE", token_b="FAIL")
