"""Dataset preparation pipeline for PII detection fine-tuning.

Following the Constitutional Classifiers methodology:
1. Define constitution (PII and NOT-PII categories)
2. Generate synthetic conversations using topic × modifier × language × pii_category
3. Convert to voice-like transcripts
4. Apply data augmentation
5. Format for speculative streaming classification
"""

from .topics import (
    Topic,
    Domain,
    PIICategory,
    ALL_TOPICS,
    TOPICS_BY_DOMAIN,
    TOPICS_BY_PII,
    get_random_topic,
    get_topic_for_pii_category,
    get_topic_without_pii,
)

from .modifiers import (
    Modifier,
    ModifierCategory,
    ALL_MODIFIERS,
    MODIFIERS_BY_CATEGORY,
    get_random_modifier,
    get_random_modifiers,
    get_compatible_modifiers,
)

from .constitution import (
    Constitution,
    ConstitutionCategory,
    Example,
    load_constitution,
    get_pii_category_description,
    get_redaction_placeholder,
)

__all__ = [
    # Topics
    "Topic",
    "Domain",
    "PIICategory",
    "ALL_TOPICS",
    "TOPICS_BY_DOMAIN",
    "TOPICS_BY_PII",
    "get_random_topic",
    "get_topic_for_pii_category",
    "get_topic_without_pii",
    # Modifiers
    "Modifier",
    "ModifierCategory",
    "ALL_MODIFIERS",
    "MODIFIERS_BY_CATEGORY",
    "get_random_modifier",
    "get_random_modifiers",
    "get_compatible_modifiers",
    # Constitution
    "Constitution",
    "ConstitutionCategory",
    "Example",
    "load_constitution",
    "get_pii_category_description",
    "get_redaction_placeholder",
]

# Lazy imports for generator (requires anthropic)
def get_generator():
    """Get ConversationGenerator (lazy import to avoid anthropic dependency)."""
    from .generator import ConversationGenerator
    return ConversationGenerator

# Lazy imports for formatters
def get_stage1_formatter():
    """Get Stage 1 formatting functions."""
    from .formatter import format_conversation_for_stage1, format_batch, Stage1Example
    return format_conversation_for_stage1, format_batch, Stage1Example

def get_stage2_formatter():
    """Get Stage 2 formatting functions."""
    from .stage2_formatter import format_conversation_for_stage2, format_batch, Stage2Example
    return format_conversation_for_stage2, format_batch, Stage2Example
