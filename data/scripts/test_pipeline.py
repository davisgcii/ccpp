#!/usr/bin/env python3
"""
End-to-end test for the entire fine-tuning pipeline.

This script tests the complete pipeline:
1. Generate synthetic conversations using the actual generator
2. Format for Stage 1 (classification) and Stage 2 (entity extraction)
3. Convert to mlx-lm chat format
4. Run forward passes with base models
5. Verify output format correctness

Usage:
    # Quick test (1 conversation, skip forward pass)
    uv run python -m data.scripts.test_pipeline --quick

    # Full test with forward pass (requires MLX)
    uv run python -m data.scripts.test_pipeline

    # Test with more conversations
    uv run python -m data.scripts.test_pipeline --count 5

    # Save outputs to inspect
    uv run python -m data.scripts.test_pipeline --output-dir data/test_output
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure we can import from data.scripts
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def step_print(step: int, total: int, message: str):
    """Print a step progress message."""
    print(f"\n[{step}/{total}] {message}")
    print("-" * 60)


def run_pipeline(
    count: int = 1,
    output_dir: Optional[Path] = None,
    skip_forward_pass: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Run the complete fine-tuning pipeline end-to-end.

    Args:
        count: Number of conversations to generate.
        output_dir: Directory to save intermediate files (for inspection).
        skip_forward_pass: Skip the MLX forward pass verification.
        verbose: Print detailed output.

    Returns:
        Dict with test results and statistics.
    """
    import yaml

    results = {
        "success": True,
        "steps_completed": [],
        "steps_failed": [],
        "stats": {},
        "errors": [],
    }

    total_steps = 6 if not skip_forward_pass else 5

    # Use temp dir if no output_dir specified
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="ccpp_test_"))
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("End-to-End Pipeline Test")
    print("=" * 60)
    print(f"Conversations: {count}")
    print(f"Output directory: {output_dir}")
    print(f"Forward pass: {'enabled' if not skip_forward_pass else 'disabled'}")

    # =========================================================================
    # Step 1: Generate conversations
    # =========================================================================
    step_print(1, total_steps, "Generating synthetic conversations")

    try:
        from data.scripts.generator import ConversationGenerator

        generator = ConversationGenerator()
        conversations = []

        for i in range(count):
            conv = generator.generate_conversation()
            conversations.append(conv)

            if verbose:
                print(f"  [{i+1}/{count}] {conv.conversation_id}")
                print(f"    Topic: {conv.topic}")
                print(f"    Has PII: {conv.has_pii}")
                print(f"    Categories: {conv.pii_categories_present}")
                print(f"    Messages: {len(conv.messages)}")

        # Write raw conversations
        raw_file = output_dir / "raw_conversations.jsonl"
        with open(raw_file, "w") as f:
            for conv in conversations:
                f.write(conv.to_jsonl() + "\n")

        results["stats"]["conversations"] = len(conversations)
        results["stats"]["with_pii"] = sum(1 for c in conversations if c.has_pii)
        results["stats"]["without_pii"] = sum(1 for c in conversations if not c.has_pii)
        results["steps_completed"].append("generate")

        print(f"Generated {len(conversations)} conversations")
        print(f"  With PII: {results['stats']['with_pii']}")
        print(f"  Without PII: {results['stats']['without_pii']}")
        print(f"  Written to: {raw_file}")

    except Exception as e:
        results["success"] = False
        results["steps_failed"].append("generate")
        results["errors"].append(f"Generation failed: {e}")
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return results

    # =========================================================================
    # Step 2: Format for Stage 1 (classification)
    # =========================================================================
    step_print(2, total_steps, "Formatting for Stage 1 (SAFE/FAIL classification)")

    try:
        from data.scripts.formatter import format_batch

        stage1_file = output_dir / "stage1.jsonl"
        stage1_stats = format_batch(raw_file, stage1_file, include_prefixes=True)

        results["stats"]["stage1_examples"] = stage1_stats["examples"]
        results["stats"]["stage1_fail"] = stage1_stats["fail_examples"]
        results["stats"]["stage1_safe"] = stage1_stats["safe_examples"]
        results["steps_completed"].append("format_stage1")

        print(f"Created {stage1_stats['examples']} Stage 1 examples")
        print(f"  FAIL: {stage1_stats['fail_examples']}")
        print(f"  SAFE: {stage1_stats['safe_examples']}")
        print(f"  Prefix examples: {stage1_stats['prefix_examples']}")
        print(f"  Written to: {stage1_file}")

        # Show a sample
        if verbose:
            with open(stage1_file, "r") as f:
                sample = json.loads(f.readline())
                print(f"\n  Sample Stage 1 example:")
                print(f"    Buffer: {sample['buffer'][:50]}...")
                print(f"    Label: {sample['label']}")

    except Exception as e:
        results["success"] = False
        results["steps_failed"].append("format_stage1")
        results["errors"].append(f"Stage 1 formatting failed: {e}")
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return results

    # =========================================================================
    # Step 3: Format for Stage 2 (entity extraction)
    # =========================================================================
    step_print(3, total_steps, "Formatting for Stage 2 (PASS/MASK entity extraction)")

    try:
        from data.scripts.stage2_formatter import format_batch as format_stage2_batch

        stage2_file = output_dir / "stage2.jsonl"
        stage2_stats = format_stage2_batch(raw_file, stage2_file)

        results["stats"]["stage2_examples"] = stage2_stats["examples"]
        results["stats"]["stage2_pass"] = stage2_stats["pass_examples"]
        results["stats"]["stage2_mask"] = stage2_stats["mask_examples"]
        results["stats"]["stage2_entities"] = stage2_stats["total_entities"]
        results["steps_completed"].append("format_stage2")

        print(f"Created {stage2_stats['examples']} Stage 2 examples")
        print(f"  PASS: {stage2_stats['pass_examples']}")
        print(f"  MASK: {stage2_stats['mask_examples']}")
        print(f"  Total entities: {stage2_stats['total_entities']}")
        print(f"  Written to: {stage2_file}")

        # Show a sample
        if verbose:
            with open(stage2_file, "r") as f:
                sample = json.loads(f.readline())
                print(f"\n  Sample Stage 2 example:")
                print(f"    Window text: {sample['window_text'][:50]}...")
                print(f"    Target: {sample['target_output']}")

    except Exception as e:
        results["success"] = False
        results["steps_failed"].append("format_stage2")
        results["errors"].append(f"Stage 2 formatting failed: {e}")
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return results

    # =========================================================================
    # Step 4: Convert to mlx-lm format
    # =========================================================================
    step_print(4, total_steps, "Converting to mlx-lm chat format")

    try:
        from data.scripts.convert_to_mlx import (
            convert_stage1_example,
            convert_stage2_example,
            extract_system_prompt,
            load_config,
            load_examples,
            write_examples,
        )

        # Load config
        config_path = Path("configs/default.yaml")
        config = load_config(config_path)

        # Convert Stage 1
        stage1_mlx_dir = output_dir / "stage1_mlx"
        stage1_mlx_dir.mkdir(exist_ok=True)

        stage1_examples = load_examples(stage1_file)
        stage1_prompt = extract_system_prompt(config, 1)

        stage1_mlx = []
        for ex in stage1_examples:
            stage1_mlx.append(convert_stage1_example(ex, stage1_prompt))

        # Split train/val
        val_size = max(1, len(stage1_mlx) // 10)
        write_examples(stage1_mlx[val_size:], stage1_mlx_dir / "train.jsonl")
        write_examples(stage1_mlx[:val_size], stage1_mlx_dir / "valid.jsonl")

        # Convert Stage 2
        stage2_mlx_dir = output_dir / "stage2_mlx"
        stage2_mlx_dir.mkdir(exist_ok=True)

        stage2_examples = load_examples(stage2_file)
        stage2_prompt = extract_system_prompt(config, 2)

        stage2_mlx = []
        for ex in stage2_examples:
            stage2_mlx.append(convert_stage2_example(ex, stage2_prompt))

        # Split train/val
        val_size = max(1, len(stage2_mlx) // 10)
        write_examples(stage2_mlx[val_size:], stage2_mlx_dir / "train.jsonl")
        write_examples(stage2_mlx[:val_size], stage2_mlx_dir / "valid.jsonl")

        results["stats"]["stage1_mlx"] = len(stage1_mlx)
        results["stats"]["stage2_mlx"] = len(stage2_mlx)
        results["steps_completed"].append("convert_mlx")

        print(f"Converted to mlx-lm format:")
        print(f"  Stage 1: {len(stage1_mlx)} examples -> {stage1_mlx_dir}")
        print(f"  Stage 2: {len(stage2_mlx)} examples -> {stage2_mlx_dir}")

        # Validate format
        print(f"\n  Validating mlx-lm format...")
        sample1 = stage1_mlx[0]
        sample2 = stage2_mlx[0]

        # Check required structure
        assert "messages" in sample1, "Stage 1 missing 'messages' key"
        assert len(sample1["messages"]) == 3, "Stage 1 should have 3 messages"
        assert sample1["messages"][0]["role"] == "system", "First message should be system"
        assert sample1["messages"][1]["role"] == "user", "Second message should be user"
        assert sample1["messages"][2]["role"] == "assistant", "Third message should be assistant"

        assert "messages" in sample2, "Stage 2 missing 'messages' key"
        assert len(sample2["messages"]) == 3, "Stage 2 should have 3 messages"

        print(f"  Format validation passed")

        # Show sample
        if verbose:
            print(f"\n  Sample Stage 1 mlx-lm example:")
            print(f"    System: {sample1['messages'][0]['content'][:60]}...")
            print(f"    User: {sample1['messages'][1]['content'][:60]}...")
            print(f"    Assistant: {sample1['messages'][2]['content']}")

    except Exception as e:
        results["success"] = False
        results["steps_failed"].append("convert_mlx")
        results["errors"].append(f"MLX conversion failed: {e}")
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return results

    # =========================================================================
    # Step 5: Forward pass verification (optional)
    # =========================================================================
    if not skip_forward_pass:
        step_print(5, total_steps, "Running forward pass with base model")

        try:
            from mlx_lm import generate, load

            # Test Stage 1 model
            model_name = "mlx-community/Qwen3-0.6B-4bit"
            print(f"Loading Stage 1 model: {model_name}")
            model, tokenizer = load(model_name)
            print(f"Model loaded")

            # Explain thinking token behavior
            print(f"\nNOTE: Qwen3 uses <think>...</think> scaffolding.")
            print(f"  - Base model: Outputs thinking content, then answer")
            print(f"  - Fine-tuned: Should output SAFE/FAIL directly after </think>")
            print(f"  - Training format: <think>\\n\\n</think>\\n\\nSAFE")

            # Run forward pass on a few examples
            test_count = min(3, len(stage1_mlx))
            valid_outputs = 0
            thinking_outputs = 0

            print(f"\nTesting {test_count} Stage 1 examples:")
            for i, ex in enumerate(stage1_mlx[:test_count]):
                messages = ex["messages"]
                prompt_messages = messages[:-1]  # Exclude assistant response

                # Apply chat template with enable_thinking=False
                # This adds empty <think></think> scaffold, matching training format
                prompt = tokenizer.apply_chat_template(
                    prompt_messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )

                # Generate
                response = generate(
                    model,
                    tokenizer,
                    prompt=prompt,
                    max_tokens=20,
                    verbose=False,
                )

                # Analyze response
                actual_raw = response.strip()

                # Check if model is producing thinking content
                has_thinking = actual_raw.startswith("<think>") or "let's" in actual_raw.lower()
                if has_thinking:
                    thinking_outputs += 1

                # Clean response - extract content after </think> if present
                actual = actual_raw
                if "</think>" in actual:
                    actual = actual.split("</think>")[-1].strip()

                expected = messages[-1]["content"]

                # Check for valid output - handle "Answer: SAFE" format from prompt template
                actual_upper = actual.upper()
                # Strip common prefixes from our prompt template
                for prefix in ["ANSWER:", "ANSWER :", "OUTPUT:"]:
                    if actual_upper.startswith(prefix):
                        actual_upper = actual_upper[len(prefix):].strip()
                        actual = actual[len(prefix):].strip()
                        break

                is_valid = actual_upper.startswith("SAFE") or actual_upper.startswith("FAIL")

                if is_valid:
                    valid_outputs += 1

                print(f"  [{i+1}] Expected: {expected}")
                print(f"       Raw output: {actual_raw[:50]}{'...' if len(actual_raw) > 50 else ''}")
                print(f"       Cleaned: {actual[:30]}, Valid: {'Y' if is_valid else 'N'}")

            results["stats"]["forward_pass_valid"] = valid_outputs
            results["stats"]["forward_pass_total"] = test_count
            results["stats"]["forward_pass_thinking"] = thinking_outputs
            results["steps_completed"].append("forward_pass")

            print(f"\nForward pass summary:")
            print(f"  Valid format: {valid_outputs}/{test_count}")
            print(f"  Producing thinking: {thinking_outputs}/{test_count}")

            if thinking_outputs > 0 and valid_outputs == 0:
                print(f"\n  This is EXPECTED for base model - it produces thinking content.")
                print(f"  After fine-tuning, model should output SAFE/FAIL directly.")

            # Clean up model to free memory
            del model
            del tokenizer

        except ImportError as e:
            print(f"WARNING: mlx_lm not available, skipping forward pass: {e}")
            results["steps_completed"].append("forward_pass_skipped")
        except Exception as e:
            results["success"] = False
            results["steps_failed"].append("forward_pass")
            results["errors"].append(f"Forward pass failed: {e}")
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
    else:
        step_print(5, total_steps, "Forward pass skipped (--quick mode)")
        results["steps_completed"].append("forward_pass_skipped")

    # =========================================================================
    # Step 6: Summary
    # =========================================================================
    step_num = 6 if not skip_forward_pass else 5
    step_print(step_num, total_steps, "Test Summary")

    print(f"Pipeline Status: {'SUCCESS' if results['success'] else 'FAILED'}")
    print(f"\nSteps completed: {', '.join(results['steps_completed'])}")

    if results["steps_failed"]:
        print(f"Steps failed: {', '.join(results['steps_failed'])}")

    if results["errors"]:
        print(f"\nErrors:")
        for err in results["errors"]:
            print(f"  - {err}")

    print(f"\nStatistics:")
    for key, value in results["stats"].items():
        print(f"  {key}: {value}")

    print(f"\nOutput files in: {output_dir}")
    print(f"  raw_conversations.jsonl - Generated conversations")
    print(f"  stage1.jsonl - Stage 1 training data")
    print(f"  stage2.jsonl - Stage 2 training data")
    print(f"  stage1_mlx/ - mlx-lm format for Stage 1")
    print(f"  stage2_mlx/ - mlx-lm format for Stage 2")

    if results["success"]:
        print(f"\nNext steps:")
        print(f"  1. Review generated data for quality")
        print(f"  2. Train Stage 1: uv run python -m mlx_lm.lora --config configs/lora_stage1.yaml")
        print(f"  3. Train Stage 2: uv run python -m mlx_lm.lora --config configs/lora_stage2.yaml")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="End-to-end test of the fine-tuning pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--count",
        type=int,
        default=2,
        help="Number of conversations to generate (default: 2)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory to save test outputs (default: temp dir)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: 1 conversation, skip forward pass",
    )
    parser.add_argument(
        "--skip-forward-pass",
        action="store_true",
        help="Skip the MLX forward pass verification",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed output",
    )

    args = parser.parse_args()

    # Quick mode overrides
    if args.quick:
        args.count = 1
        args.skip_forward_pass = True

    results = run_pipeline(
        count=args.count,
        output_dir=args.output_dir,
        skip_forward_pass=args.skip_forward_pass,
        verbose=args.verbose,
    )

    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()
