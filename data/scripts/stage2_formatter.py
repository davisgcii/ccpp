"""
Stage 2 training data formatter for PII entity extraction.

Stage 2 takes text flagged as risky by Stage 1 and extracts exact PII entities.
The model learns to output:
- "PASS" if no PII found
- "MASK \"entity\" category; MASK \"entity2\" category2" for each PII entity

Output format (JSONL):
{
    "context": [{"role": "assistant", "content": "..."}],
    "window_text": "It's john.doe@gmail.com and my phone is 555-123-4567",
    "target_output": "MASK \"john.doe@gmail.com\" contact; MASK \"555-123-4567\" contact"
}
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Stage2Example:
    """A single Stage 2 training example."""
    context: list[dict]  # Prior conversation turns
    window_text: str  # Text to extract entities from
    target_output: str  # Expected model output

    def to_dict(self) -> dict:
        return {
            "context": self.context,
            "window_text": self.window_text,
            "target_output": self.target_output,
        }

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict())


def format_entity_output(entities: list[dict]) -> str:
    """
    Format PII entities into Stage 2 output string.

    Args:
        entities: List of entity dicts with "text" and "category" keys.

    Returns:
        Formatted output like 'MASK "entity" category; MASK "entity2" cat2'
        or "PASS" if no entities.
    """
    if not entities:
        return "PASS"

    parts = []
    for entity in entities:
        text = entity.get("text", "")
        category = entity.get("category", "unknown")
        parts.append(f'MASK "{text}" {category}')

    return "; ".join(parts)


def format_conversation_for_stage2(
    conversation: dict,
) -> list[Stage2Example]:
    """
    Format a conversation into Stage 2 training examples.

    Creates one example per user message that was classified by Stage 1.
    For messages with PII, the target is MASK commands.
    For messages without PII, the target is PASS.

    Args:
        conversation: Conversation dict with messages array.

    Returns:
        List of Stage2Example objects.
    """
    examples = []
    messages = conversation.get("messages", [])

    for i, msg in enumerate(messages):
        if msg.get("role") != "user":
            continue

        # Build context from prior messages
        context = []
        for j in range(i):
            context.append({
                "role": messages[j]["role"],
                "content": messages[j]["content"],
            })

        # Get PII entities
        pii_entities = msg.get("pii_entities", [])
        window_text = msg.get("content", "")
        target_output = format_entity_output(pii_entities)

        examples.append(Stage2Example(
            context=context,
            window_text=window_text,
            target_output=target_output,
        ))

    return examples


def format_batch(
    input_file: Path | str,
    output_file: Path | str,
    limit: int | None = None,
) -> dict:
    """
    Format a batch of conversations into Stage 2 training data.

    Args:
        input_file: Path to input JSONL with conversations.
        output_file: Path to output JSONL for Stage 2 training.
        limit: Optional limit on conversations to process.

    Returns:
        Dict with formatting statistics.
    """
    input_path = Path(input_file)
    output_path = Path(output_file)

    stats = {
        "conversations": 0,
        "examples": 0,
        "pass_examples": 0,
        "mask_examples": 0,
        "total_entities": 0,
    }

    with open(input_path, 'r') as f_in, open(output_path, 'w') as f_out:
        for i, line in enumerate(f_in):
            if limit and i >= limit:
                break

            try:
                conversation = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            stats["conversations"] += 1

            examples = format_conversation_for_stage2(conversation)

            for ex in examples:
                f_out.write(ex.to_jsonl() + '\n')
                stats["examples"] += 1

                if ex.target_output == "PASS":
                    stats["pass_examples"] += 1
                else:
                    stats["mask_examples"] += 1
                    # Count entities in output
                    stats["total_entities"] += ex.target_output.count("MASK")

            if (i + 1) % 100 == 0:
                print(f"Processed {i+1} conversations, {stats['examples']} examples...")

    return stats


def create_train_val_split(
    input_file: Path | str,
    train_file: Path | str,
    val_file: Path | str,
    val_ratio: float = 0.1,
    seed: int = 42,
) -> dict:
    """
    Create train/val split from formatted Stage 2 data.

    Args:
        input_file: Path to formatted Stage 2 JSONL.
        train_file: Path for training output.
        val_file: Path for validation output.
        val_ratio: Fraction for validation (default 10%).
        seed: Random seed.

    Returns:
        Dict with split statistics.
    """
    import random
    random.seed(seed)

    input_path = Path(input_file)

    # Read all examples
    examples = []
    with open(input_path, 'r') as f:
        for line in f:
            examples.append(line)

    # Shuffle and split
    random.shuffle(examples)
    split_idx = int(len(examples) * (1 - val_ratio))

    train_examples = examples[:split_idx]
    val_examples = examples[split_idx:]

    # Write splits
    with open(train_file, 'w') as f:
        f.writelines(train_examples)

    with open(val_file, 'w') as f:
        f.writelines(val_examples)

    return {
        "total_examples": len(examples),
        "train_examples": len(train_examples),
        "val_examples": len(val_examples),
    }


# =============================================================================
# Prompt formatting for inference
# =============================================================================

STAGE2_SYSTEM_PROMPT = """You are a PII entity extractor. Given a text window from a voice conversation, identify any PII entities and their categories.

Categories:
- person: Full names
- contact: Email addresses, phone numbers
- gov_id: SSN, driver's license, passport numbers
- financial: Credit cards, bank accounts
- credentials: Passwords, API keys
- medical: Medical record numbers, diagnoses
- location: Physical addresses
- identifier: Order numbers, account IDs, tracking numbers

Output format:
- If NO PII found: output exactly "PASS"
- If PII found: output "MASK \"entity_text\" category" for each entity
- Multiple entities: separate with "; "

Example outputs:
PASS
MASK "john.doe@gmail.com" contact
MASK "John Smith" person; MASK "555-123-4567" contact
MASK "123-45-6789" gov_id; MASK "4532 1234 5678 9012" financial"""


def format_for_inference(
    context: list[dict],
    window_text: str,
) -> str:
    """
    Format context + window for Stage 2 inference.

    Args:
        context: Prior conversation messages.
        window_text: Text to extract entities from.

    Returns:
        Formatted prompt string.
    """
    # Build context summary
    context_parts = []
    for msg in context[-3:]:  # Last 3 messages for context
        role = msg.get("role", "user")
        content = msg.get("content", "")
        context_parts.append(f"[{role.upper()}]: {content}")

    context_str = "\n".join(context_parts) if context_parts else "(conversation start)"

    prompt = f"""<context>
{context_str}
</context>

<window>
{window_text}
</window>

Extract PII entities:"""

    return prompt


# =============================================================================
# CLI
# =============================================================================

def main():
    """CLI entry point for Stage 2 formatting."""
    import argparse

    parser = argparse.ArgumentParser(description="Format conversations for Stage 2 training")
    parser.add_argument("input", type=str, help="Input JSONL file with conversations")
    parser.add_argument("output", type=str, help="Output JSONL file for Stage 2")
    parser.add_argument("--limit", type=int, help="Limit number of conversations")
    parser.add_argument("--split", action="store_true", help="Create train/val split")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Validation ratio")

    args = parser.parse_args()

    print(f"Formatting {args.input} -> {args.output}")
    stats = format_batch(args.input, args.output, limit=args.limit)

    print(f"\nFormatting complete:")
    print(f"  Conversations: {stats['conversations']}")
    print(f"  Total examples: {stats['examples']}")
    print(f"  PASS examples: {stats['pass_examples']}")
    print(f"  MASK examples: {stats['mask_examples']}")
    print(f"  Total entities: {stats['total_entities']}")

    if args.split:
        output_path = Path(args.output)
        train_file = output_path.with_suffix('.train.jsonl')
        val_file = output_path.with_suffix('.val.jsonl')

        print(f"\nCreating train/val split...")
        split_stats = create_train_val_split(
            args.output,
            train_file,
            val_file,
            val_ratio=args.val_ratio,
        )

        print(f"  Train: {split_stats['train_examples']} examples")
        print(f"  Val: {split_stats['val_examples']} examples")


if __name__ == "__main__":
    main()
