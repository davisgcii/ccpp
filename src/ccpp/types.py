"""Common types and data structures for CC++ PII streaming masking classifier."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Approved Models
# -----------------------------------------------------------------------------


class ApprovedModel(Enum):
    """Approved models for CC++ PII masking system.

    Only these models should be used in configurations to ensure
    compatibility and expected behavior.

    Usage:
        config = {
            "backend": "ollama",
            "model_name": ApprovedModel.QWEN3_1_7B.value
        }
    """

    # Local models (via Ollama)
    # Note: Use think=False with Qwen3 to disable thinking mode for classification
    QWEN3_0_6B = "qwen3:0.6b"  # Fast Qwen3 model for Stage 1 (522MB)
    QWEN3_1_7B = "qwen3:1.7b"  # Larger Qwen3 model for Stage 2 (1.4GB)
    GEMMA3_1B = "gemma3:1b"  # Alternative: Gemma3 (815MB, no thinking mode)
    GEMMA3_4B = "gemma3:4b"  # Alternative: Gemma3 (3.3GB, no thinking mode)

    # Local models (via MLX - Apple Silicon with true logit extraction)
    QWEN3_1_7B_MLX = "Qwen/Qwen3-1.7B-MLX-8bit"  # Quantized MLX model for M-series
    QWEN3_0_6B_MLX_4BIT = "mlx-community/Qwen3-0.6B-4bit"  # Smallest/fastest for Stage 1
    QWEN3_0_6B_MLX_8BIT = "mlx-community/Qwen3-0.6B-8bit"  # Faster Stage 1, better accuracy

    # Cloud models (via APIs)
    CLAUDE_HAIKU_4_5 = "claude-haiku-4-5-20251001"  # Fast, cost-effective (Anthropic)
    GPT_5_MINI = "gpt-5-mini"  # Alternative cloud option (OpenAI)

    def __str__(self) -> str:
        return self.value

    @classmethod
    def is_valid(cls, model_name: str) -> bool:
        """Check if model name is approved.

        Args:
            model_name: Model name to check

        Returns:
            True if model is in approved list
        """
        return model_name in [m.value for m in cls]


# -----------------------------------------------------------------------------
# PII Categories
# -----------------------------------------------------------------------------


class PIICategory(Enum):
    """PII/sensitive information categories for classification and masking."""

    SAFE = "safe"
    PII_DIRECT = "pii/direct"  # email, phone, SSN, name+DOB combos
    PII_INDIRECT = "pii/indirect"  # quasi-identifiers (job+employer+city)
    CREDENTIALS = "credentials"  # API keys, passwords, tokens, private keys
    FINANCIAL = "financial"  # account/card numbers, tax IDs
    MEDICAL = "medical"  # diagnoses, prescriptions, record numbers
    LOCATION_PRECISE = "location/precise"  # exact addresses, coordinates

    def is_sensitive(self) -> bool:
        """Check if category indicates sensitive content requiring masking."""
        return self != PIICategory.SAFE

    @classmethod
    def from_string(cls, s: str) -> "PIICategory":
        """Parse category from string."""
        s = s.strip().lower()
        for category in cls:
            if category.value.lower() == s:
                return category
        raise ValueError(f"Unknown PII category: {s}")


# -----------------------------------------------------------------------------
# Stage 1 Output: Risk Score
# -----------------------------------------------------------------------------


@dataclass
class RiskScore:
    """Output from Stage 1 risk router.

    Stage 1 uses logit-based classification: we extract P(FAIL) from the
    softmax over SAFE/FAIL token logits. This is much faster than generating
    tokens (single forward pass vs 3-6 passes).

    The score is a calibrated probability indicating likelihood of PII/sensitive
    info in the current exchange window.
    """

    score: float  # 0.0 = safe, 1.0 = definitely contains PII (P(FAIL) from logits)
    top_category: Optional[PIICategory] = None  # Not used in logit-based approach

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Risk score must be in [0, 1], got {self.score}")



# -----------------------------------------------------------------------------
# Stage 2 Output: Mask Spans
# -----------------------------------------------------------------------------


@dataclass
class MaskSpan:
    """A span of text to mask in the redaction window.

    Instead of character offsets (which LLMs are bad at), we store the actual
    entity text to mask. The masking engine finds and replaces all occurrences.
    """

    entity_text: str  # The actual text to mask (e.g., "john@gmail.com")
    category: PIICategory

    def __post_init__(self) -> None:
        if not self.entity_text:
            raise ValueError("entity_text cannot be empty")
        if not isinstance(self.entity_text, str):
            raise ValueError(f"entity_text must be str, got {type(self.entity_text)}")

    def to_string(self) -> str:
        """Serialize to plain text format.

        Format: MASK "entity text" category
        Entity is quoted to handle spaces and special characters.
        """
        # Escape internal quotes by doubling them
        escaped = self.entity_text.replace('"', '""')
        return f'MASK "{escaped}" {self.category.value}'

    @classmethod
    def from_string(cls, s: str) -> "MaskSpan":
        """Parse from plain text output.

        Expected format: MASK "entity text" category
        """
        s = s.strip()
        if not s.upper().startswith("MASK"):
            raise ValueError(f"Expected 'MASK ...' format, got: {s}")

        # Find the quoted entity
        first_quote = s.find('"')
        if first_quote == -1:
            raise ValueError(f"Expected quoted entity in: {s}")

        # Find the closing quote, handling escaped quotes ("")
        entity_start = first_quote + 1
        i = entity_start
        while i < len(s):
            if s[i] == '"':
                # Check if it's escaped (followed by another quote)
                if i + 1 < len(s) and s[i + 1] == '"':
                    i += 2  # Skip the escaped quote
                else:
                    # Found the closing quote
                    entity_end = i
                    break
            else:
                i += 1
        else:
            raise ValueError(f"No closing quote found in: {s}")

        entity_text = s[entity_start:entity_end].replace('""', '"')  # Unescape quotes

        # Parse category from remaining text
        remainder = s[entity_end + 1 :].strip()
        if not remainder:
            raise ValueError(f"No category found in: {s}")

        category = PIICategory.from_string(remainder)
        return cls(entity_text=entity_text, category=category)


@dataclass
class RedactorOutput:
    """Output from Stage 2 span redactor.

    Contains zero or more mask spans to apply to the redaction window.
    """

    spans: list[MaskSpan] = field(default_factory=list)

    def to_string(self) -> str:
        """Serialize to plain text format."""
        if not self.spans:
            return "PASS"
        return "; ".join(span.to_string() for span in self.spans)

    @classmethod
    def from_string(cls, s: str) -> "RedactorOutput":
        """Parse from plain text output.

        Expected formats:
            PASS
            MASK "entity" pii/direct
            MASK "entity1" pii/direct; MASK "entity2" credentials
        """
        s = s.strip()
        if s.upper() == "PASS":
            return cls(spans=[])

        span_strs = [part.strip() for part in s.split(";")]
        spans = [MaskSpan.from_string(span_str) for span_str in span_strs if span_str]
        return cls(spans=spans)

    def apply_masks(self, text: str, mask_format: str = "[{type}]") -> str:
        """Apply mask spans to text, replacing sensitive content.

        Uses exact string matching to find and replace all occurrences of each
        entity in the text. If an entity is not found, a warning is logged.

        Args:
            text: The original text (should match window_text used for detection)
            mask_format: Format string for replacement, e.g. "[{type}]" or "[REDACTED]"

        Returns:
            Text with sensitive entities replaced
        """
        if not self.spans:
            return text

        result = text
        spans = sorted(self.spans, key=lambda s: len(s.entity_text), reverse=True)
        seen = set()
        for span in spans:
            if span.entity_text in seen:
                continue
            seen.add(span.entity_text)
            replacement = mask_format.format(type=span.category.value.upper())

            # Check if entity exists in text
            if span.entity_text in result:
                # Replace all occurrences (exact string match)
                result = result.replace(span.entity_text, replacement)
            else:
                logger.warning(
                    f"Entity not found in text: {span.entity_text!r} "
                    f"(category: {span.category.value})"
                )

        return result


# -----------------------------------------------------------------------------
# Streaming State
# -----------------------------------------------------------------------------


@dataclass
class HoldbackBuffer:
    """Buffer for holding raw streamed text before emission.

    Raw text is accumulated here. Masking decisions are made on the buffer,
    and only masked/approved text is emitted. Once emitted, text cannot be
    "unmasked" (irreversible).
    """

    raw_text: str = ""
    overlap_tail: str = ""  # Last N chars retained for cross-chunk entity detection
    max_overlap: int = 64  # Characters to retain for overlap

    def append(self, text: str) -> None:
        """Add new text to the buffer."""
        self.raw_text += text

    def flush(self, keep_overlap: bool = True) -> str:
        """Return and clear buffer contents.

        Args:
            keep_overlap: If True, retain last max_overlap chars in overlap_tail

        Returns:
            The flushed text
        """
        flushed = self.raw_text
        if keep_overlap and len(flushed) > self.max_overlap:
            self.overlap_tail = flushed[-self.max_overlap :]
        else:
            self.overlap_tail = flushed if keep_overlap else ""
        self.raw_text = ""
        return flushed

    def get_window_with_overlap(self) -> str:
        """Get the full window including overlap tail for entity detection."""
        return self.overlap_tail + self.raw_text

    def __len__(self) -> int:
        return len(self.raw_text)


@dataclass
class RiskState:
    """Streaming risk state with EMA smoothing and hysteresis.

    Maintains smoothed risk score and tracks escalation state to avoid
    jitter in routing decisions.
    """

    ema_risk: float = 0.0
    beta: float = 0.85  # EMA smoothing factor (higher = more smoothing)
    t_high: float = 0.6  # Escalate when ema_risk >= t_high
    t_low: float = 0.3  # De-escalate when ema_risk <= t_low
    is_escalated: bool = False
    consecutive_high: int = 0  # Count of consecutive high-risk observations
    min_consecutive_for_escalate: int = 1  # Require N consecutive high before escalate

    def update(self, new_risk: float) -> bool:
        """Update risk state with new observation.

        Args:
            new_risk: Raw risk score from Stage 1 (0.0-1.0)

        Returns:
            True if should escalate to Stage 2, False otherwise
        """
        # EMA update
        self.ema_risk = self.beta * self.ema_risk + (1 - self.beta) * new_risk

        # Hysteresis logic
        if self.ema_risk >= self.t_high:
            self.consecutive_high += 1
            if self.consecutive_high >= self.min_consecutive_for_escalate:
                self.is_escalated = True
        elif self.ema_risk <= self.t_low:
            self.consecutive_high = 0
            self.is_escalated = False
        # Between t_low and t_high: maintain current state

        return self.is_escalated


# -----------------------------------------------------------------------------
# Training Data Types
# -----------------------------------------------------------------------------


@dataclass
class PIIExchange:
    """Training example for PII masking classifiers.

    Represents a conversation exchange with labeled PII spans.
    """

    messages: list[dict]  # [{"role": "user", "content": ...}, {"role": "assistant", ...}]
    window_text: str  # Exact text presented to Stage 2 for span detection
    spans: list[MaskSpan]  # Ground truth spans relative to window_text
    label: PIICategory  # Derived from spans (SAFE if empty, else most severe)
    meta: dict = field(default_factory=dict)  # Provenance info

    def __post_init__(self) -> None:
        # Derive label from spans if not explicitly set
        if self.spans and self.label == PIICategory.SAFE:
            # Use first span's category as primary label
            self.label = self.spans[0].category

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSONL output."""
        return {
            "messages": self.messages,
            "window_text": self.window_text,
            "spans": [{"entity_text": s.entity_text, "category": s.category.value} for s in self.spans],
            "label": self.label.value,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PIIExchange":
        """Create from dictionary."""
        spans = [
            MaskSpan(entity_text=s["entity_text"], category=PIICategory.from_string(s["category"]))
            for s in d.get("spans", [])
        ]
        return cls(
            messages=d["messages"],
            window_text=d["window_text"],
            spans=spans,
            label=PIICategory.from_string(d.get("label", "safe")),
            meta=d.get("meta", {}),
        )


# -----------------------------------------------------------------------------
# Heuristic Detection Results
# -----------------------------------------------------------------------------


@dataclass
class HeuristicMatch:
    """Result from fast regex/rule-based heuristic detection."""

    pattern_name: str  # e.g., "email", "credit_card", "api_key"
    matched_text: str  # The actual text that matched
    start: int  # Char offset (for reference/debugging)
    end: int  # Char offset (for reference/debugging)
    confidence: float = 1.0  # How confident the heuristic is (1.0 = regex match)
    suggested_category: PIICategory = PIICategory.PII_DIRECT

    def to_mask_span(self) -> MaskSpan:
        """Convert to MaskSpan for redaction."""
        return MaskSpan(entity_text=self.matched_text, category=self.suggested_category)


# -----------------------------------------------------------------------------
# GUI Debugging Metadata
# -----------------------------------------------------------------------------


@dataclass
class CharClassification:
    """Per-character classification metadata for interactive debugging.

    Stores full prompts and responses for each character to enable
    hover tooltips in the GUI.
    """

    char: str  # The character
    idx: int  # Character index in buffer
    risk_score: float  # P(RISK) from Stage 1
    ema: float  # EMA value after this character
    classifier_prompt: list[dict]  # Full formatted messages sent to Stage 1
    classifier_response: dict  # {p_safe, p_risk, raw_output}
    timestamp: float  # Unix timestamp

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "char": self.char,
            "idx": self.idx,
            "risk_score": self.risk_score,
            "ema": self.ema,
            "classifier_prompt": self.classifier_prompt,
            "classifier_response": self.classifier_response,
            "timestamp": self.timestamp,
        }


@dataclass
class BufferMetadata:
    """Per-buffer metadata for masking operations.

    Stores full masker prompts/responses and aggregated character data
    for tooltip display.
    """

    original_text: str  # Unmasked buffer
    masked_text: str  # After redaction
    char_data: list[CharClassification]  # Per-character classifications
    masker_prompt: Optional[list[dict]]  # Full formatted messages to Stage 2
    masker_response: Optional[dict]  # {raw_output, entities}
    risk_history: list[dict]  # Copy of risk_history for mini-chart
    heuristic_matches: list[HeuristicMatch]  # Fast heuristic detections
    was_masked: bool  # Whether masking was triggered
    timestamp: float  # Unix timestamp

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "original_text": self.original_text,
            "masked_text": self.masked_text,
            "char_data": [c.to_dict() for c in self.char_data],
            "masker_prompt": self.masker_prompt,
            "masker_response": self.masker_response,
            "risk_history": self.risk_history,
            "heuristic_matches": [
                {
                    "pattern_name": m.pattern_name,
                    "matched_text": m.matched_text,
                    "start": m.start,
                    "end": m.end,
                    "confidence": m.confidence,
                    "category": m.suggested_category.value,
                }
                for m in self.heuristic_matches
            ],
            "was_masked": self.was_masked,
            "timestamp": self.timestamp,
        }
