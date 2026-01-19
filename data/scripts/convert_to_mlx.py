#!/usr/bin/env python3
"""
Convert Stage 1/Stage 2 training data to mlx-lm chat format.

Takes JSONL files from the data generation pipeline and converts them to
the format expected by mlx-lm for LoRA fine-tuning.

Usage:
    # Convert Stage 1 data
    uv run python -m data.scripts.convert_to_mlx --stage 1 \
        --input data/training/stage1.jsonl \
        --output data/training/stage1_mlx/

    # Convert Stage 2 data
    uv run python -m data.scripts.convert_to_mlx --stage 2 \
        --input data/training/stage2.jsonl \
        --output data/training/stage2_mlx/

    # With custom train/val split
    uv run python -m data.scripts.convert_to_mlx --stage 1 --val-ratio 0.15
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Optional

import yaml


def load_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def format_context_for_prompt(context: list[dict]) -> str:
    """
    Format conversation context for the prompt.

    Args:
        context: List of message dicts with role and content.

    Returns:
        Formatted context string.
    """
    if not context:
        return "(No prior context)"

    lines = []
    for msg in context:
        role = msg["role"].capitalize()
        content = msg["content"]
        lines.append(f"{role}: {content}")

    return "\n".join(lines)


def convert_stage1_example(example: dict, system_prompt: str) -> dict:
    """
    Convert a Stage 1 example to mlx-lm chat format.

    Stage 1 input format:
    {
        "context": [{"role": "...", "content": "..."}],
        "buffer": "current text",
        "label": "SAFE" or "FAIL",
        "category": "...",
        ...
    }

    mlx-lm output format:
    {
        "messages": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "Context:\n...\n\nBuffer:\n..."},
            {"role": "assistant", "content": "SAFE" or "FAIL"}
        ]
    }
    """
    context = example.get("context", [])
    buffer = example.get("buffer", "")
    label = example.get("label", "SAFE")

    # Format context
    context_str = format_context_for_prompt(context)

    # Build user content matching the prompt template format
    user_content = f"Context:\n{context_str}\n\nBuffer:\n{buffer}"

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": label},
        ]
    }


def convert_stage2_example(example: dict, system_prompt: str) -> dict:
    """
    Convert a Stage 2 example to mlx-lm chat format.

    Stage 2 input format:
    {
        "context": [{"role": "...", "content": "..."}],
        "window_text": "text to extract entities from",
        "target_output": "PASS" or "MASK ..."
    }

    mlx-lm output format:
    {
        "messages": [
            {"role": "system", "content": "..."},
            {"role": "user", "content": "Context:\n...\n\nWindow text:\n..."},
            {"role": "assistant", "content": "PASS" or "MASK ..."}
        ]
    }
    """
    context = example.get("context", [])
    window_text = example.get("window_text", "")
    target_output = example.get("target_output", "PASS")

    # Format context
    context_str = format_context_for_prompt(context)

    # Build user content matching the prompt template format
    user_content = f"Context:\n{context_str}\n\nWindow text:\n{window_text}"

    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": target_output},
        ]
    }


def extract_system_prompt(config: dict, stage: int) -> str:
    """
    Extract the system prompt from config, stripping the example/classification parts.

    For training, we want just the instructions without the {context}/{buffer} placeholders.
    """
    stage_key = f"stage{stage}"
    prompt_template = config.get(stage_key, {}).get("prompt_template", "")

    if not prompt_template:
        raise ValueError(f"No prompt_template found for {stage_key} in config")

    # For Stage 1, extract everything before "# Now classify"
    # For Stage 2, extract everything before "# Now extract" or similar
    if stage == 1:
        # Find where the actual classification section starts
        markers = ["# Now classify", "Context:\n{context}"]
        for marker in markers:
            if marker in prompt_template:
                prompt_template = prompt_template.split(marker)[0]
                break
    else:
        # Stage 2 - find where examples end and actual task starts
        markers = ["# Now extract", "Context:\n{context}"]
        for marker in markers:
            if marker in prompt_template:
                prompt_template = prompt_template.split(marker)[0]
                break

    return prompt_template.strip()


def load_examples(input_path: Path) -> list[dict]:
    """Load examples from JSONL file."""
    examples = []
    with open(input_path, "r") as f:
        for line in f:
            if line.strip():
                examples.append(json.loads(line))
    return examples


def write_examples(examples: list[dict], output_path: Path):
    """Write examples to JSONL file."""
    with open(output_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")


def split_train_val_test(
    examples: list[dict],
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    seed: int = 42,
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Split examples into train, validation, and test sets.

    Args:
        examples: List of examples.
        val_ratio: Fraction for validation (default 0.1 = 10%).
        test_ratio: Fraction for test (default 0.1 = 10%).
        seed: Random seed for reproducibility.

    Returns:
        (train_examples, val_examples, test_examples)
    """
    random.seed(seed)
    shuffled = examples.copy()
    random.shuffle(shuffled)

    test_size = int(len(shuffled) * test_ratio)
    val_size = int(len(shuffled) * val_ratio)

    test_examples = shuffled[:test_size]
    val_examples = shuffled[test_size:test_size + val_size]
    train_examples = shuffled[test_size + val_size:]

    return train_examples, val_examples, test_examples


def main():
    parser = argparse.ArgumentParser(
        description="Convert training data to mlx-lm format"
    )
    parser.add_argument(
        "--stage",
        type=int,
        choices=[1, 2],
        required=True,
        help="Stage to convert (1=classification, 2=extraction)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input JSONL file (default: data/training/stage{N}.jsonl)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory (default: data/training/stage{N}_mlx/)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/default.yaml"),
        help="Config file for prompt templates",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.1,
        help="Validation split ratio (default: 0.1 = 10%%)",
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.1,
        help="Test split ratio (default: 0.1 = 10%%)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        help="Maximum number of examples to convert (for testing)",
    )
    parser.add_argument(
        "--skip-full-only",
        action="store_true",
        help="For Stage 1: only include full buffers (skip prefixes)",
    )

    args = parser.parse_args()

    # Set defaults based on stage
    if args.input is None:
        args.input = Path(f"data/training/stage{args.stage}.jsonl")
    if args.output is None:
        args.output = Path(f"data/training/stage{args.stage}_mlx")

    print("=" * 60)
    print(f"Converting Stage {args.stage} Training Data to mlx-lm Format")
    print("=" * 60)

    # Load config
    print(f"\n1. Loading config from: {args.config}")
    if not args.config.exists():
        print(f"   ERROR: Config file not found: {args.config}")
        sys.exit(1)

    config = load_config(args.config)
    system_prompt = extract_system_prompt(config, args.stage)
    print(f"   System prompt length: {len(system_prompt)} chars")

    # Load input examples
    print(f"\n2. Loading examples from: {args.input}")
    if not args.input.exists():
        print(f"   ERROR: Input file not found: {args.input}")
        print(f"   Run the data generation pipeline first:")
        print(f"   uv run python -m data.scripts.main all --count 1000")
        sys.exit(1)

    examples = load_examples(args.input)
    print(f"   Loaded {len(examples)} examples")

    # Filter if needed
    if args.stage == 1 and args.skip_full_only:
        examples = [ex for ex in examples if ex.get("is_full", True)]
        print(f"   After filtering to full buffers: {len(examples)} examples")

    if args.max_examples:
        examples = examples[: args.max_examples]
        print(f"   Limited to {len(examples)} examples")

    # Convert examples
    print(f"\n3. Converting to mlx-lm format")
    converted = []
    for ex in examples:
        if args.stage == 1:
            converted.append(convert_stage1_example(ex, system_prompt))
        else:
            converted.append(convert_stage2_example(ex, system_prompt))
    print(f"   Converted {len(converted)} examples")

    # Split into train/val/test
    train_ratio = 1 - args.val_ratio - args.test_ratio
    print(f"\n4. Splitting train/val/test ({train_ratio:.0%}/{args.val_ratio:.0%}/{args.test_ratio:.0%})")
    train_examples, val_examples, test_examples = split_train_val_test(
        converted, args.val_ratio, args.test_ratio, args.seed
    )
    print(f"   Train: {len(train_examples)}, Val: {len(val_examples)}, Test: {len(test_examples)}")

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Write output files
    train_path = args.output / "train.jsonl"
    val_path = args.output / "valid.jsonl"
    test_path = args.output / "test.jsonl"

    print(f"\n5. Writing output files")
    write_examples(train_examples, train_path)
    print(f"   Train: {train_path}")
    write_examples(val_examples, val_path)
    print(f"   Val: {val_path}")
    write_examples(test_examples, test_path)
    print(f"   Test: {test_path}")

    # Show sample
    print(f"\n6. Sample converted example:")
    sample = converted[0]
    print(f"   System: {sample['messages'][0]['content'][:60]}...")
    print(f"   User: {sample['messages'][1]['content'][:60]}...")
    print(f"   Assistant: {sample['messages'][2]['content']}")

    # Summary
    print("\n" + "=" * 60)
    print("Conversion Complete")
    print("=" * 60)
    print(f"Stage: {args.stage}")
    print(f"Train examples: {len(train_examples)}")
    print(f"Val examples: {len(val_examples)}")
    print(f"Test examples: {len(test_examples)}")
    print(f"Output directory: {args.output}")
    print(f"\nTo train with mlx-lm:")
    print(f"  uv run python -m mlx_lm.lora \\")
    print(f"    --model {'mlx-community/Qwen3-0.6B-4bit' if args.stage == 1 else 'Qwen/Qwen3-1.7B-MLX-8bit'} \\")
    print(f"    --train \\")
    print(f"    --data {args.output} \\")
    print(f"    --iters {1000 if args.stage == 1 else 1500}")


if __name__ == "__main__":
    main()
