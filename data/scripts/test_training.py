#!/usr/bin/env python3
"""
Test script for verifying the training data format and model forward pass.

This script:
1. Creates sample training examples (or uses existing ones)
2. Converts them to mlx-lm chat format
3. Runs a forward pass with the base model
4. Verifies the model produces SAFE/FAIL (Stage 1) or PASS/MASK (Stage 2) output

Usage:
    uv run python -m data.scripts.test_training --samples 5
    uv run python -m data.scripts.test_training --use-existing data/test_output/stage1_examples_*.jsonl
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Default prompt template (simplified for testing)
STAGE1_SYSTEM_PROMPT = """You are a PII classifier for streaming text.

Classify the CURRENT BUFFER as SAFE or FAIL.
- FAIL: Buffer contains actual PII (names+context, emails, phones, SSNs, etc.)
- SAFE: Buffer contains requests for PII, mentions without data, or placeholders

Output exactly one word: SAFE or FAIL"""

STAGE2_SYSTEM_PROMPT = """Extract PII entities from the text for masking.

Output format:
- PASS if no PII to mask
- MASK "entity" category for each PII entity

Categories: person, contact, gov_id, financial, credentials, medical, location, identifier"""


def create_sample_stage1_examples() -> list[dict]:
    """Create sample Stage 1 training examples for testing."""
    return [
        # FAIL examples (contain PII)
        {
            "context": [
                {"role": "assistant", "content": "How can I help you today?"},
                {"role": "user", "content": "I need to update my account."},
                {"role": "assistant", "content": "Sure, can I get your email address?"},
            ],
            "buffer": "It's john.smith@gmail.com",
            "label": "FAIL",
            "category": "contact",
        },
        {
            "context": [
                {"role": "assistant", "content": "I can help with that verification."},
            ],
            "buffer": "My social is one two three, four five, six seven eight nine",
            "label": "FAIL",
            "category": "gov_id",
        },
        {
            "context": [],
            "buffer": "My name is John Michael Smith and I live at 123 Main Street",
            "label": "FAIL",
            "category": "person",
        },
        # SAFE examples (no PII)
        {
            "context": [
                {"role": "assistant", "content": "How can I help you today?"},
            ],
            "buffer": "I forgot my password and need to reset it",
            "label": "SAFE",
            "category": "none",
        },
        {
            "context": [],
            "buffer": "What's the status of my order?",
            "label": "SAFE",
            "category": "none",
        },
        {
            "context": [
                {"role": "assistant", "content": "I can look that up for you."},
            ],
            "buffer": "Use user@example.com for the test",
            "label": "SAFE",
            "category": "none",
        },
    ]


def create_sample_stage2_examples() -> list[dict]:
    """Create sample Stage 2 training examples for testing."""
    return [
        # Examples with PII to mask
        {
            "context": [
                {"role": "assistant", "content": "What's your email?"},
            ],
            "window_text": "It's john.smith@gmail.com",
            "target_output": 'MASK "john.smith@gmail.com" contact',
        },
        {
            "context": [],
            "window_text": "My SSN is 123-45-6789 and my phone is 415-555-0123",
            "target_output": 'MASK "123-45-6789" gov_id; MASK "415-555-0123" contact',
        },
        # Examples without PII
        {
            "context": [],
            "window_text": "I need help with my account",
            "target_output": "PASS",
        },
        {
            "context": [],
            "window_text": "Use user@example.com for testing",
            "target_output": "PASS",
        },
    ]


def convert_stage1_to_mlx_format(examples: list[dict]) -> list[dict]:
    """
    Convert Stage 1 examples to mlx-lm chat format.

    mlx-lm expects:
    {"messages": [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "SAFE or FAIL"}
    ]}
    """
    mlx_examples = []

    for ex in examples:
        # Format context as readable text
        context_str = ""
        for msg in ex.get("context", []):
            role = msg["role"].capitalize()
            context_str += f"{role}: {msg['content']}\n"

        # Build user prompt
        user_content = f"Context:\n{context_str}\nBuffer:\n{ex['buffer']}"

        mlx_example = {
            "messages": [
                {"role": "system", "content": STAGE1_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": ex["label"]},
            ]
        }
        mlx_examples.append(mlx_example)

    return mlx_examples


def convert_stage2_to_mlx_format(examples: list[dict]) -> list[dict]:
    """
    Convert Stage 2 examples to mlx-lm chat format.
    """
    mlx_examples = []

    for ex in examples:
        # Format context
        context_str = ""
        for msg in ex.get("context", []):
            role = msg["role"].capitalize()
            context_str += f"{role}: {msg['content']}\n"

        # Build user prompt
        if context_str:
            user_content = f"Context:\n{context_str}\nText to analyze:\n{ex['window_text']}"
        else:
            user_content = f"Text to analyze:\n{ex['window_text']}"

        mlx_example = {
            "messages": [
                {"role": "system", "content": STAGE2_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": ex["target_output"]},
            ]
        }
        mlx_examples.append(mlx_example)

    return mlx_examples


def write_mlx_format(examples: list[dict], output_path: Path):
    """Write examples in mlx-lm JSONL format."""
    with open(output_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")


def run_forward_pass(
    model_name: str,
    examples: list[dict],
    stage: int,
) -> list[dict]:
    """
    Run forward pass with base model to verify format.

    Args:
        model_name: HuggingFace model name
        examples: List of mlx-lm format examples
        stage: 1 for classification, 2 for generation

    Returns:
        List of results with expected vs actual output
    """
    try:
        from mlx_lm import load, generate
    except ImportError:
        print("ERROR: mlx_lm not installed. Install with: uv add mlx-lm")
        print("Skipping forward pass verification.")
        return []

    print(f"\nLoading model: {model_name}")
    model, tokenizer = load(model_name)
    print(f"✓ Model loaded")

    results = []

    for i, ex in enumerate(examples[:3]):  # Only test first 3 to keep it fast
        messages = ex["messages"]
        expected = messages[-1]["content"]  # The assistant response we're training on

        # Build prompt from system + user (exclude assistant for generation)
        prompt_messages = messages[:-1]

        # Apply chat template
        prompt = tokenizer.apply_chat_template(
            prompt_messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        # Generate (short for Stage 1, longer for Stage 2)
        max_tokens = 5 if stage == 1 else 50

        print(f"\n--- Example {i+1} ---")
        print(f"Buffer/Text: {messages[1]['content'][:80]}...")
        print(f"Expected: {expected}")

        # Generate response
        response = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=max_tokens,
            verbose=False,
        )

        # Clean response (remove thinking tokens if present)
        actual = response.strip()
        if "<think>" in actual:
            # Extract just the answer after thinking
            parts = actual.split("</think>")
            actual = parts[-1].strip() if len(parts) > 1 else actual

        print(f"Actual: {actual[:100]}")

        # Check if output is valid
        if stage == 1:
            is_valid = actual.upper().startswith("SAFE") or actual.upper().startswith("FAIL")
        else:
            is_valid = actual.upper().startswith("PASS") or actual.upper().startswith("MASK")

        print(f"Valid format: {'✓' if is_valid else '✗'}")

        results.append({
            "expected": expected,
            "actual": actual,
            "is_valid": is_valid,
        })

    return results


def load_existing_examples(path: str, stage: int) -> list[dict]:
    """Load existing examples from JSONL file."""
    examples = []
    with open(path, "r") as f:
        for line in f:
            if line.strip():
                examples.append(json.loads(line))
    return examples


def main():
    parser = argparse.ArgumentParser(
        description="Test training data format and model forward pass"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Number of sample examples to create (default: 5)",
    )
    parser.add_argument(
        "--stage",
        type=int,
        choices=[1, 2],
        default=1,
        help="Stage to test (1=classification, 2=generation)",
    )
    parser.add_argument(
        "--use-existing",
        type=str,
        help="Path to existing examples JSONL file",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="mlx-community/Qwen3-0.6B-4bit",
        help="Model to use for forward pass",
    )
    parser.add_argument(
        "--skip-forward-pass",
        action="store_true",
        help="Skip the forward pass verification",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory to save converted examples",
    )

    args = parser.parse_args()

    print("=" * 60)
    print(f"Testing Stage {args.stage} Training Pipeline")
    print("=" * 60)

    # Step 1: Get or create examples
    if args.use_existing:
        print(f"\n1. Loading existing examples from: {args.use_existing}")
        examples = load_existing_examples(args.use_existing, args.stage)
        print(f"   Loaded {len(examples)} examples")
    else:
        print(f"\n1. Creating {args.samples} sample examples")
        if args.stage == 1:
            examples = create_sample_stage1_examples()[:args.samples]
        else:
            examples = create_sample_stage2_examples()[:args.samples]
        print(f"   Created {len(examples)} examples")

    # Step 2: Convert to mlx-lm format
    print(f"\n2. Converting to mlx-lm chat format")
    if args.stage == 1:
        mlx_examples = convert_stage1_to_mlx_format(examples)
    else:
        mlx_examples = convert_stage2_to_mlx_format(examples)
    print(f"   Converted {len(mlx_examples)} examples")

    # Show a sample
    print(f"\n   Sample converted example:")
    sample = mlx_examples[0]
    print(f"   System: {sample['messages'][0]['content'][:60]}...")
    print(f"   User: {sample['messages'][1]['content'][:60]}...")
    print(f"   Assistant: {sample['messages'][2]['content']}")

    # Step 3: Write to temp file (or output dir)
    if args.output_dir:
        output_dir = args.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"stage{args.stage}_mlx_test.jsonl"
    else:
        output_file = Path(tempfile.mktemp(suffix=".jsonl"))

    print(f"\n3. Writing mlx-lm format to: {output_file}")
    write_mlx_format(mlx_examples, output_file)
    print(f"   Written {len(mlx_examples)} examples")

    # Step 4: Run forward pass
    if not args.skip_forward_pass:
        print(f"\n4. Running forward pass with {args.model}")
        results = run_forward_pass(args.model, mlx_examples, args.stage)

        if results:
            valid_count = sum(1 for r in results if r["is_valid"])
            print(f"\n   Results: {valid_count}/{len(results)} produced valid format")
    else:
        print(f"\n4. Skipping forward pass (--skip-forward-pass)")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Stage: {args.stage}")
    print(f"Examples: {len(mlx_examples)}")
    print(f"Output: {output_file}")

    if not args.skip_forward_pass:
        print(f"\nTo train with mlx-lm:")
        print(f"  uv run python -m mlx_lm.lora \\")
        print(f"    --model {args.model} \\")
        print(f"    --train \\")
        print(f"    --data {output_file.parent} \\")
        print(f"    --iters 100 \\")
        print(f"    --batch-size 2")


if __name__ == "__main__":
    main()
