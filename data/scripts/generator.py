"""
Conversation generator for PII detection training data.

Uses Claude Haiku for fast, cost-effective synthetic conversation generation.
Generates realistic customer support conversations with labeled PII entities.

Key features:
- Structured output schema with PII entity labels
- Support for multiple languages (90% English, 10% other)
- Configurable PII density and category distribution
- Voice-like conversation patterns
"""

import json
import logging
import random
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

# Set up logging
logger = logging.getLogger(__name__)

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from .topics import Topic, PIICategory, get_topic_for_pii_category, get_topic_without_pii
from .modifiers import Modifier, get_random_modifiers
from .constitution import load_constitution, get_pii_category_description


# =============================================================================
# Configuration
# =============================================================================

# Default model for generation
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# Generation parameters
DEFAULT_TEMPERATURE = 0.8
MIN_TURNS = 6
MAX_TURNS = 15

# Distribution settings
PII_CONVERSATION_RATIO = 0.80  # 80% of conversations have PII
NO_PII_RATIO = 0.20  # 20% have no PII

# PII density within conversations that have PII
PII_DENSITY_1_MESSAGE = 0.70   # 70% have PII in 1 user message
PII_DENSITY_2_3_MESSAGES = 0.20  # 20% have PII in 2-3 user messages
PII_DENSITY_4_PLUS = 0.10  # 10% have PII in 4+ user messages

# PII category distribution (balanced)
PII_CATEGORY_WEIGHTS = {
    PIICategory.IDENTIFIER: 0.15,
    PIICategory.CONTACT: 0.15,
    PIICategory.PERSON: 0.15,
    PIICategory.LOCATION: 0.13,
    PIICategory.FINANCIAL: 0.13,
    PIICategory.CREDENTIALS: 0.10,
    PIICategory.GOV_ID: 0.10,
    PIICategory.MEDICAL: 0.09,
}

# Language distribution
LANGUAGE_WEIGHTS = {
    "en": 0.90,
    "es": 0.02,
    "fr": 0.01,
    "de": 0.01,
    "pt": 0.01,
    "zh": 0.01,
    "ja": 0.005,
    "ko": 0.005,
    "hi": 0.005,
    "ar": 0.005,
    "other": 0.02,
}


# =============================================================================
# Data structures
# =============================================================================

@dataclass
class PIIEntity:
    """A PII entity found in a message."""
    text: str
    category: str  # PIICategory value

    def to_dict(self) -> dict:
        return {"text": self.text, "category": self.category}


@dataclass
class Message:
    """A single conversation message."""
    role: str  # "user" or "assistant"
    content: str
    content_redacted: str
    pii_entities: list[PIIEntity] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "content_redacted": self.content_redacted,
            "pii_entities": [e.to_dict() for e in self.pii_entities],
        }


@dataclass
class Conversation:
    """A complete conversation with metadata."""
    conversation_id: str
    topic: str
    modifier: str
    language: str
    messages: list[Message] = field(default_factory=list)
    has_pii: bool = False
    pii_categories_present: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "conversation_id": self.conversation_id,
            "topic": self.topic,
            "modifier": self.modifier,
            "language": self.language,
            "messages": [m.to_dict() for m in self.messages],
            "has_pii": self.has_pii,
            "pii_categories_present": self.pii_categories_present,
        }

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict())


# =============================================================================
# Sampling functions
# =============================================================================

def sample_pii_category() -> PIICategory:
    """Sample a PII category based on the configured weights."""
    categories = list(PII_CATEGORY_WEIGHTS.keys())
    weights = list(PII_CATEGORY_WEIGHTS.values())
    return random.choices(categories, weights=weights, k=1)[0]


def sample_language() -> str:
    """Sample a language based on the configured weights."""
    languages = list(LANGUAGE_WEIGHTS.keys())
    weights = list(LANGUAGE_WEIGHTS.values())
    return random.choices(languages, weights=weights, k=1)[0]


def sample_pii_density() -> int:
    """
    Sample how many user messages should contain PII.

    Returns:
        Number of user messages that should have PII (1, 2, 3, or 4+)
    """
    r = random.random()
    if r < PII_DENSITY_1_MESSAGE:
        return 1
    elif r < PII_DENSITY_1_MESSAGE + PII_DENSITY_2_3_MESSAGES:
        return random.randint(2, 3)
    else:
        return random.randint(4, 6)


def should_include_pii() -> bool:
    """Determine if this conversation should include PII."""
    return random.random() < PII_CONVERSATION_RATIO

def get_num_turns() -> int:
    """Randomly choose a number between {min_turns} and {max_turns}."""
    return random.randint(MIN_TURNS, MAX_TURNS)


# =============================================================================
# Prompt templates
# =============================================================================

GENERATION_SYSTEM_PROMPT = """You are generating training data for a PII classifier. Generate a realistic voice/phone customer support conversation.

CRITICAL REQUIREMENTS:
1. Generate a natural-sounding PHONE conversation (not chat!) between a customer (user) and support agent (assistant)
2. The conversation MUST be entirely in {language}
3. Apply the modifier to shape the conversation tone/dynamics
4. If PII is required, include REALISTIC synthetic PII values (not placeholders!)
5. PII should appear naturally - typically once or twice, NOT in every message
6. Agent messages typically should NOT contain PII (except for read-back confirmation ~5% of cases)

VOICE/PHONE CHARACTERISTICS - Make it sound like a real phone call transcription:
1. Natural hesitations: "um", "uh", "let me see", "hold on a sec"
2. Self-corrections: "my email is, actually wait, it's", "no wait, I meant"
3. Filler words: "so", "okay so", "right so", "and um"
4. Numbers spoken digit-by-digit: "four one five, five five five, zero one two three"
5. Emails spoken naturally: "john dot smith at gmail dot com"
6. Agent read-back confirmations: "So that's four one five"
7. Incomplete thoughts due to interruption: "I was going to say", "if you could just"
8. Casual speech: "Hi I'm calling about", "Yeah um let me check"

NOTE: Do NOT use ellipses (...) anywhere - speech-to-text transcription does not produce them.

PII LABELING - CRITICAL:
- Tag ALL instances of PII, including paraphrases and restatements
- If someone says "zero six twenty six" then clarifies "the sixth month of 2026", BOTH are PII
- If someone spells out a number then restates it differently, tag BOTH versions
- Example: "my expiration is zero six slash twenty six, so June 2026" -> tag both "zero six slash twenty six" AND "June 2026"
- Tag partial references to earlier PII: "the last four digits" when SSN was given, "that email" when referring back
- If the agent reads back or confirms PII (e.g., "so that's 4152?"), tag the agent's message too
- When in doubt, tag it - false positives are better than missed PII

CONTENT_REDACTED FIELD - REQUIRED:
- Every message MUST have a content_redacted field, even if identical to content
- For messages with no PII, content_redacted should be an exact copy of content
- Never omit this field - it is required for training data

OUTPUT FORMAT:
Return a valid JSON object with this exact structure:
{{
  "messages": [
    {{
      "role": "user" or "assistant",
      "content": "The actual message text",
      "content_redacted": "Message with PII replaced by placeholders like [PERSON], [EMAIL], [PHONE], etc.",
      "pii_entities": [
        {{"text": "the actual PII value", "category": "person|contact|gov_id|financial|credentials|medical|location|identifier"}}
      ]
    }}
  ]
}}

PLACEHOLDERS TO USE:
- [PERSON] - Full names
- [EMAIL] - Email addresses
- [PHONE] - Phone numbers
- [ADDRESS] - Physical addresses
- [SSN] - Social security numbers
- [CREDIT_CARD] - Credit card numbers
- [BANK_ACCOUNT] - Bank account/routing numbers
- [PASSWORD] - Passwords
- [API_KEY] - API keys/tokens
- [ORDER_ID] - Order numbers
- [ACCOUNT_ID] - Account IDs
- [TRACKING] - Tracking numbers
- [DL_NUMBER] - Driver's license numbers
- [PASSPORT] - Passport numbers
- [MRN] - Medical record numbers
- [DOB] - Dates of birth

REALISTIC PII EXAMPLES (use diverse, realistic-sounding synthetic values, NOT these exact examples):
- Names: "Marcus Chen", "Priya Venkatesh", "Dmitri Volkov", "Aisha Johnson-Williams", "Tomás Herrera Ruiz"
- Emails: "mchen847@outlook.com", "priya.v.consulting@gmail.com", "d_volkov_nyc@yahoo.com"
- US Phones (written): "(628) 447-8291", "312-892-5547", "917.403.6628"
- US Phones (spoken): "six two eight, four four seven, eight two nine one"
- Addresses: "4817 Wilshire Boulevard Unit 302 Los Angeles CA 90010", "89 Brookfield Drive Apt 2B Cambridge MA 02139"
- SSN: "847-29-6153", "five one two, eight three, four seven zero nine"
- Credit cards: "4916 2847 5519 3842", "four nine one six, two eight four seven, five five one nine, three eight four two"
- Bank routing/account: "routing zero two one zero zero zero zero eight nine, account four eight two seven three nine one zero"
- Order numbers: "WMT-29847531", "AZ-8847291-3829471", "confirmation number bravo romeo seven four two"
- Tracking: "one zee nine four seven eight two nine three four seven two eight"
- API keys: "sk-proj-Tm8vK2xR4nP7qW9yH3jL"
- Medical record: "MRN two nine four seven eight three"

For voice, numbers are spoken digit-by-digit or in groups:
- "my zip is nine four one zero three"
- "the last four of my card are three eight four two"
- "account ending in seven two nine one"
"""

GENERATION_USER_PROMPT = """Generate a customer support conversation with these parameters:

**Language**: {language}
**Topic**: {topic_description}
**Modifier**: {modifier_name} - {modifier_description}
**Generation notes**: {modifier_notes}

**PII Requirements**: {pii_instructions}

Generate a conversation with exactly {num_turns} turns, where each turn is one user message followed by one assistant message (two messages per turn). Alternate between user and assistant, starting with the assistant greeting.

Remember:
- Make it sound like a real phone call (hesitations, natural speech)
- PII appears naturally, not forced
- Agent typically doesn't reveal PII (except confirming back)
- Use realistic synthetic values, not placeholders like "XXX"

Return ONLY the JSON object, no other text."""


NO_PII_INSTRUCTION = """This conversation should contain NO PII at all.
This is a general inquiry or question that doesn't require the customer to provide any personal information.
The content_redacted should be identical to content for all messages.
The pii_entities array should be empty for all messages."""

PII_INSTRUCTION_TEMPLATE = """This conversation should include the following PII category: **{category}**
Description: {category_description}

The customer should naturally provide this type of PII during the conversation.
- Include PII in approximately {density} user message(s)
- Make the PII disclosure natural and contextually appropriate
- Use realistic synthetic values

Examples of {category} PII:
{examples}"""


# =============================================================================
# Generator class
# =============================================================================

class ConversationGenerator:
    """Generates synthetic conversations for PII classifier training."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        on_api_call: Callable[[dict], None] | None = None,
    ):
        """
        Initialize the generator.

        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
            model: Model to use for generation.
            temperature: Temperature for generation (higher = more diverse).
            on_api_call: Optional callback called with API call details (for debugging/testing).
        """
        if not HAS_ANTHROPIC:
            raise ImportError("anthropic package not installed. Run: uv add anthropic")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.constitution = load_constitution()
        self.on_api_call = on_api_call

        logger.info(f"Initialized ConversationGenerator with model={model}, temperature={temperature}")

    def _get_pii_examples(self, category: PIICategory, limit: int = 5) -> str:
        """Get example PII values from the constitution for a category."""
        examples = self.constitution.get_harmful_examples(category)
        if not examples:
            return "Use realistic synthetic values appropriate for this category."

        # Get diverse examples from different subcategories
        by_subcat: dict[str, list] = {}
        for ex in examples:
            if ex.subcategory not in by_subcat:
                by_subcat[ex.subcategory] = []
            by_subcat[ex.subcategory].append(ex)

        selected = []
        for exs in by_subcat.values():
            if len(selected) >= limit:
                break
            selected.append(f"- {random.choice(exs).text}")

        return "\n".join(selected[:limit])

    def _build_pii_instructions(
        self,
        include_pii: bool,
        pii_category: PIICategory | None,
        pii_density: int,
    ) -> str:
        """Build PII instructions for the prompt."""
        if not include_pii:
            return NO_PII_INSTRUCTION

        if pii_category is None:
            pii_category = sample_pii_category()

        examples = self._get_pii_examples(pii_category)
        return PII_INSTRUCTION_TEMPLATE.format(
            category=pii_category.value,
            category_description=get_pii_category_description(pii_category),
            density=pii_density,
            examples=examples,
        )

    def generate_conversation(
        self,
        topic: Topic | None = None,
        modifier: Modifier | None = None,
        language: str | None = None,
        include_pii: bool | None = None,
        pii_category: PIICategory | None = None,
    ) -> Conversation:
        """
        Generate a single conversation.

        Args:
            topic: Topic for the conversation. If None, sampled randomly.
            modifier: Modifier for conversation style. If None, sampled randomly.
            language: Language code. If None, sampled based on distribution.
            include_pii: Whether to include PII. If None, sampled based on distribution.
            pii_category: PII category to include. If None, sampled based on distribution.

        Returns:
            Generated Conversation object.
        """
        # Sample parameters if not provided
        if language is None:
            language = sample_language()

        if include_pii is None:
            include_pii = should_include_pii()

        if include_pii:
            if pii_category is None:
                pii_category = sample_pii_category()
            if topic is None:
                topic = get_topic_for_pii_category(pii_category)
            pii_density = sample_pii_density()
        else:
            if topic is None:
                topic = get_topic_without_pii()
            pii_density = 0

        if modifier is None:
            modifier = get_random_modifiers(1)[0]

        # Build prompts
        pii_instructions = self._build_pii_instructions(include_pii, pii_category, pii_density)

        language_name = {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "pt": "Portuguese",
            "zh": "Mandarin Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "hi": "Hindi",
            "ar": "Arabic",
        }.get(language, "English")

        system_prompt = GENERATION_SYSTEM_PROMPT.format(language=language_name)

        num_turns = get_num_turns()
        user_prompt = GENERATION_USER_PROMPT.format(
            language=language_name,
            topic_description=topic.description,
            modifier_name=modifier.name,
            modifier_description=modifier.description,
            modifier_notes=modifier.generation_notes,
            pii_instructions=pii_instructions,
            num_turns=num_turns,
        )

        logger.debug(f"Generating conversation: topic={topic.id}, modifier={modifier.id}, "
                     f"language={language}, include_pii={include_pii}, pii_category={pii_category}")
        logger.debug(f"System prompt length: {len(system_prompt)} chars")
        logger.debug(f"User prompt length: {len(user_prompt)} chars")

        # Call the API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Parse response
        response_text = response.content[0].text

        logger.debug(f"Response length: {len(response_text)} chars")

        # Call the callback if provided (for testing/debugging)
        if self.on_api_call:
            self.on_api_call({
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "response_text": response_text,
                "model": self.model,
                "temperature": self.temperature,
                "topic": topic.id,
                "modifier": modifier.id,
                "language": language,
                "include_pii": include_pii,
                "pii_category": pii_category.value if pii_category else None,
            })

        # Extract JSON from response (handle potential markdown wrapping)
        json_text = response_text
        if "```json" in response_text:
            json_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            json_text = response_text.split("```")[1].split("```")[0]

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text (first 500 chars): {response_text[:500]}")
            raise ValueError(f"Failed to parse response as JSON: {e}\nResponse: {response_text[:500]}")

        # Build Conversation object
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        logger.debug(f"Creating conversation {conversation_id}")
        messages = []
        pii_categories_found = set()

        for msg_data in data.get("messages", []):
            pii_entities = []
            for entity_data in msg_data.get("pii_entities", []):
                entity = PIIEntity(
                    text=entity_data.get("text", ""),
                    category=entity_data.get("category", ""),
                )
                pii_entities.append(entity)
                if entity.category:
                    pii_categories_found.add(entity.category)

            message = Message(
                role=msg_data.get("role", "user"),
                content=msg_data.get("content", ""),
                content_redacted=msg_data.get("content_redacted", msg_data.get("content", "")),
                pii_entities=pii_entities,
            )
            messages.append(message)

        conversation = Conversation(
            conversation_id=conversation_id,
            topic=topic.id,
            modifier=modifier.id,
            language=language,
            messages=messages,
            has_pii=len(pii_categories_found) > 0,
            pii_categories_present=list(pii_categories_found),
        )

        logger.info(f"Generated {conversation_id}: {len(messages)} messages, "
                    f"has_pii={conversation.has_pii}, categories={conversation.pii_categories_present}")

        return conversation

    def generate_batch(
        self,
        count: int,
        output_file: Path | str | None = None,
    ) -> list[Conversation]:
        """
        Generate a batch of conversations.

        Args:
            count: Number of conversations to generate.
            output_file: Optional path to write JSONL output.

        Returns:
            List of generated Conversation objects.
        """
        conversations = []

        logger.info(f"Starting batch generation of {count} conversations")
        if output_file:
            logger.info(f"Output file: {output_file}")

        for i in range(count):
            try:
                conv = self.generate_conversation()
                conversations.append(conv)

                if output_file:
                    with open(output_file, 'a') as f:
                        f.write(conv.to_jsonl() + '\n')

                logger.info(f"Generated {i+1}/{count}: {conv.conversation_id} "
                            f"(PII: {conv.has_pii}, categories: {conv.pii_categories_present})")

            except Exception as e:
                logger.error(f"Error generating conversation {i+1}: {e}")
                continue

        logger.info(f"Batch complete: {len(conversations)}/{count} conversations generated")
        return conversations


# =============================================================================
# CLI
# =============================================================================

def main():
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate synthetic PII conversations")
    parser.add_argument("--count", type=int, default=5, help="Number of conversations to generate")
    parser.add_argument("--output", type=str, help="Output JSONL file path")
    parser.add_argument("--pii", action="store_true", help="Force include PII")
    parser.add_argument("--no-pii", action="store_true", help="Force no PII")
    parser.add_argument("--category", type=str, help="Force specific PII category")
    parser.add_argument("--verbose", action="store_true", help="Print full conversations")

    args = parser.parse_args()

    generator = ConversationGenerator()

    # Determine PII settings
    include_pii = None
    if args.pii:
        include_pii = True
    elif args.no_pii:
        include_pii = False

    pii_category = None
    if args.category:
        try:
            pii_category = PIICategory(args.category)
        except ValueError:
            print(f"Invalid category: {args.category}")
            print(f"Valid categories: {[c.value for c in PIICategory]}")
            return

    # Generate
    for i in range(args.count):
        print(f"\n{'='*60}")
        print(f"Generating conversation {i+1}/{args.count}")
        print('='*60)

        conv = generator.generate_conversation(
            include_pii=include_pii,
            pii_category=pii_category,
        )

        print(f"ID: {conv.conversation_id}")
        print(f"Topic: {conv.topic}")
        print(f"Modifier: {conv.modifier}")
        print(f"Language: {conv.language}")
        print(f"Has PII: {conv.has_pii}")
        print(f"PII Categories: {conv.pii_categories_present}")

        if args.verbose:
            print("\nMessages:")
            for msg in conv.messages:
                print(f"\n[{msg.role.upper()}]")
                print(f"  Content: {msg.content}")
                print(f"  Redacted: {msg.content_redacted}")
                if msg.pii_entities:
                    print(f"  PII: {[e.to_dict() for e in msg.pii_entities]}")

        if args.output:
            with open(args.output, 'a') as f:
                f.write(conv.to_jsonl() + '\n')


if __name__ == "__main__":
    main()
