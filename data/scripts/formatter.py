"""
Stage 1 training data formatter for speculative PII classification.

Following the Constitutional Classifiers paper methodology:
- Train model to predict p(y=1|t_{1:T'}) - probability that FULL sequence
  contains PII, from any PREFIX t_{1:T'}
- All prefixes of a sequence share the same full-sequence label
- This enables streaming classification where we predict from partial input

Output format (JSONL):
{
    "context": [{"role": "assistant", "content": "..."}],  # Prior conversation
    "buffer": "My email is john@gmail.com",  # Current buffer being classified
    "label": "FAIL",  # SAFE or FAIL for full buffer
    "category": "contact",  # PII category if FAIL
    "prefix_end": 5,  # Character position of this prefix (for prefix training)
    "is_full": true  # Whether this is the full buffer or a prefix
}
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass
class Stage1Example:
    """A single Stage 1 training example."""
    context: list[dict]  # Prior conversation turns
    buffer: str  # Text being classified (may be prefix)
    label: str  # "SAFE" or "FAIL"
    category: str  # PII category or "none"
    prefix_end: int  # Character position where prefix ends
    is_full: bool  # Whether this is the full buffer

    def to_dict(self) -> dict:
        return {
            "context": self.context,
            "buffer": self.buffer,
            "label": self.label,
            "category": self.category,
            "prefix_end": self.prefix_end,
            "is_full": self.is_full,
        }

    def to_jsonl(self) -> str:
        return json.dumps(self.to_dict())


def generate_prefixes(
    text: str,
    min_prefix_chars: int = 3,
) -> Iterator[tuple[str, int]]:
    """
    Generate prefixes of text for speculative training.

    Args:
        text: Full text to generate prefixes from.
        min_prefix_chars: Minimum prefix length.

    Yields:
        (prefix_text, end_position) tuples.
    """
    # Word boundaries are better for natural prefixes
    words = text.split()
    current = ""

    for word in words:
        if current:
            current += " " + word
        else:
            current = word

        # Yield at word boundaries, respecting min length
        if len(current) >= min_prefix_chars:
            yield current, len(current)

    # Always yield the full text
    if len(text) >= min_prefix_chars:
        yield text, len(text)


def format_conversation_for_stage1(
    conversation: dict,
    include_prefixes: bool = True,
    min_prefix_chars: int = 3,
) -> list[Stage1Example]:
    """
    Format a conversation into Stage 1 training examples.

    For each user message:
    - If it contains PII: label = FAIL for ALL prefixes
    - If no PII: label = SAFE for ALL prefixes

    Args:
        conversation: Conversation dict with messages array.
        include_prefixes: Whether to include prefix examples.
        min_prefix_chars: Minimum prefix length.

    Returns:
        List of Stage1Example objects.
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

        # Determine label from PII entities
        pii_entities = msg.get("pii_entities", [])
        has_pii = len(pii_entities) > 0
        label = "FAIL" if has_pii else "SAFE"

        # Get primary PII category
        category = "none"
        if pii_entities:
            category = pii_entities[0].get("category", "none")

        buffer_text = msg.get("content", "")

        if include_prefixes:
            # Generate examples for all prefixes
            seen_prefixes = set()
            for prefix, end_pos in generate_prefixes(buffer_text, min_prefix_chars):
                if prefix in seen_prefixes:
                    continue
                seen_prefixes.add(prefix)

                is_full = (prefix == buffer_text)
                examples.append(Stage1Example(
                    context=context,
                    buffer=prefix,
                    label=label,
                    category=category,
                    prefix_end=end_pos,
                    is_full=is_full,
                ))
        else:
            # Only include full buffer
            examples.append(Stage1Example(
                context=context,
                buffer=buffer_text,
                label=label,
                category=category,
                prefix_end=len(buffer_text),
                is_full=True,
            ))

    return examples


def format_batch(
    input_file: Path | str,
    output_file: Path | str,
    include_prefixes: bool = True,
    limit: int | None = None,
) -> dict:
    """
    Format a batch of conversations into Stage 1 training data.

    Args:
        input_file: Path to input JSONL with conversations.
        output_file: Path to output JSONL for Stage 1 training.
        include_prefixes: Whether to include prefix examples.
        limit: Optional limit on conversations to process.

    Returns:
        Dict with formatting statistics.
    """
    input_path = Path(input_file)
    output_path = Path(output_file)

    stats = {
        "conversations": 0,
        "examples": 0,
        "fail_examples": 0,
        "safe_examples": 0,
        "prefix_examples": 0,
        "full_examples": 0,
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

            examples = format_conversation_for_stage1(
                conversation,
                include_prefixes=include_prefixes,
            )

            for ex in examples:
                f_out.write(ex.to_jsonl() + '\n')
                stats["examples"] += 1

                if ex.label == "FAIL":
                    stats["fail_examples"] += 1
                else:
                    stats["safe_examples"] += 1

                if ex.is_full:
                    stats["full_examples"] += 1
                else:
                    stats["prefix_examples"] += 1

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
    Create train/val split from formatted Stage 1 data.

    Splits at the conversation level to avoid data leakage.

    Args:
        input_file: Path to formatted Stage 1 JSONL.
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

    # Read all examples and group by conversation
    conv_examples: dict[str, list[str]] = {}

    with open(input_path, 'r') as f:
        for line in f:
            try:
                ex = json.loads(line.strip())
                # Use context hash as conversation ID
                ctx_key = json.dumps(ex.get("context", []))
                if ctx_key not in conv_examples:
                    conv_examples[ctx_key] = []
                conv_examples[ctx_key].append(line)
            except json.JSONDecodeError:
                continue

    # Split conversations
    conv_keys = list(conv_examples.keys())
    random.shuffle(conv_keys)

    split_idx = int(len(conv_keys) * (1 - val_ratio))
    train_keys = set(conv_keys[:split_idx])
    val_keys = set(conv_keys[split_idx:])

    # Write splits
    train_count = 0
    val_count = 0

    with open(train_file, 'w') as f_train, open(val_file, 'w') as f_val:
        for key in train_keys:
            for line in conv_examples[key]:
                f_train.write(line)
                train_count += 1

        for key in val_keys:
            for line in conv_examples[key]:
                f_val.write(line)
                val_count += 1

    return {
        "total_conversations": len(conv_keys),
        "train_conversations": len(train_keys),
        "val_conversations": len(val_keys),
        "train_examples": train_count,
        "val_examples": val_count,
    }


# =============================================================================
# Prompt formatting for inference
# =============================================================================

def format_for_inference(
    context: list[dict],
    buffer: str,
    system_prompt: str,
) -> str:
    """
    Format a context + buffer for Stage 1 inference.

    Args:
        context: Prior conversation messages.
        buffer: Current text being classified.
        system_prompt: The classifier system prompt.

    Returns:
        Formatted prompt string.
    """
    # Build dialog section
    dialog_parts = []
    for msg in context:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        dialog_parts.append(f"[{role.upper()}]: {content}")

    # Add current buffer as user turn
    dialog_parts.append(f"[USER]: {buffer}")

    dialog = "\n".join(dialog_parts)

    # Build full prompt
    prompt = f"""<system>
{system_prompt}
</system>

<dialog>
{dialog}
</dialog>

Classification:"""

    return prompt


# =============================================================================
# CLI
# =============================================================================

def main():
    """CLI entry point for Stage 1 formatting."""
    import argparse

    parser = argparse.ArgumentParser(description="Format conversations for Stage 1 training")
    parser.add_argument("input", type=str, help="Input JSONL file with conversations")
    parser.add_argument("output", type=str, help="Output JSONL file for Stage 1")
    parser.add_argument("--no-prefixes", action="store_true", help="Don't include prefix examples")
    parser.add_argument("--limit", type=int, help="Limit number of conversations")
    parser.add_argument("--split", action="store_true", help="Create train/val split")
    parser.add_argument("--val-ratio", type=float, default=0.1, help="Validation ratio")

    args = parser.parse_args()

    print(f"Formatting {args.input} -> {args.output}")
    stats = format_batch(
        args.input,
        args.output,
        include_prefixes=not args.no_prefixes,
        limit=args.limit,
    )

    print(f"\nFormatting complete:")
    print(f"  Conversations: {stats['conversations']}")
    print(f"  Total examples: {stats['examples']}")
    print(f"  FAIL examples: {stats['fail_examples']}")
    print(f"  SAFE examples: {stats['safe_examples']}")
    print(f"  Full examples: {stats['full_examples']}")
    print(f"  Prefix examples: {stats['prefix_examples']}")

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

        print(f"  Train: {split_stats['train_examples']} examples ({split_stats['train_conversations']} conversations)")
        print(f"  Val: {split_stats['val_examples']} examples ({split_stats['val_conversations']} conversations)")


if __name__ == "__main__":
    main()
