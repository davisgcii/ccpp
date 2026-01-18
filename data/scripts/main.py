#!/usr/bin/env python3
"""
Main orchestrator for PII dataset generation pipeline.

Usage:
    # Generate sample conversations for validation
    uv run python -m scripts.dataset_prep.main sample --count 50

    # Generate full dataset
    uv run python -m scripts.dataset_prep.main generate --count 1000

    # Format for training
    uv run python -m scripts.dataset_prep.main format

    # Full pipeline
    uv run python -m scripts.dataset_prep.main all --count 1000

Pipeline stages:
1. Generate synthetic conversations (using Claude Haiku)
2. Format for Stage 1 training (speculative classification)
3. Format for Stage 2 training (entity extraction)
4. Create train/val splits
"""

import argparse
import json
from pathlib import Path
from datetime import datetime


# =============================================================================
# Configuration
# =============================================================================

# Default paths
DATA_DIR = Path("data")
SYNTHETIC_DIR = DATA_DIR / "synthetic"
TRAINING_DIR = DATA_DIR / "training"

# Default files
RAW_CONVERSATIONS = SYNTHETIC_DIR / "raw_conversations.jsonl"
STAGE1_DATA = TRAINING_DIR / "stage1.jsonl"
STAGE2_DATA = TRAINING_DIR / "stage2.jsonl"


def ensure_dirs():
    """Ensure output directories exist."""
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Pipeline stages
# =============================================================================

def generate_conversations(
    output_file: Path,
    count: int,
    verbose: bool = False,
) -> dict:
    """
    Generate synthetic conversations.

    Args:
        output_file: Path to output JSONL file.
        count: Number of conversations to generate.
        verbose: Print progress.

    Returns:
        Dict with generation statistics.
    """
    from .generator import ConversationGenerator

    generator = ConversationGenerator()

    stats = {
        "total": 0,
        "with_pii": 0,
        "without_pii": 0,
        "by_category": {},
        "errors": 0,
    }

    print(f"Generating {count} conversations...")

    with open(output_file, 'w') as f:
        for i in range(count):
            try:
                conv = generator.generate_conversation()

                # Write to file
                f.write(conv.to_jsonl() + '\n')

                # Update stats
                stats["total"] += 1
                if conv.has_pii:
                    stats["with_pii"] += 1
                    for cat in conv.pii_categories_present:
                        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
                else:
                    stats["without_pii"] += 1

                if verbose or (i + 1) % 10 == 0:
                    print(f"  [{i+1}/{count}] {conv.conversation_id} "
                          f"(PII: {conv.has_pii}, cats: {conv.pii_categories_present})")

            except Exception as e:
                print(f"  Error generating conversation {i+1}: {e}")
                stats["errors"] += 1
                continue

    return stats


def format_for_stage1(
    input_file: Path,
    output_file: Path,
    include_prefixes: bool = True,
) -> dict:
    """Format conversations for Stage 1 training."""
    from .formatter import format_batch

    print(f"Formatting for Stage 1: {input_file} -> {output_file}")
    return format_batch(input_file, output_file, include_prefixes=include_prefixes)


def format_for_stage2(
    input_file: Path,
    output_file: Path,
) -> dict:
    """Format conversations for Stage 2 training."""
    from .stage2_formatter import format_batch

    print(f"Formatting for Stage 2: {input_file} -> {output_file}")
    return format_batch(input_file, output_file)


def create_splits(
    stage1_file: Path,
    stage2_file: Path,
    val_ratio: float = 0.1,
) -> dict:
    """Create train/val splits for both stages."""
    from .formatter import create_train_val_split as split_stage1
    from .stage2_formatter import create_train_val_split as split_stage2

    print(f"Creating train/val splits (val_ratio={val_ratio})...")

    stats = {}

    # Stage 1 split
    stats["stage1"] = split_stage1(
        stage1_file,
        stage1_file.with_suffix('.train.jsonl'),
        stage1_file.with_suffix('.val.jsonl'),
        val_ratio=val_ratio,
    )

    # Stage 2 split
    stats["stage2"] = split_stage2(
        stage2_file,
        stage2_file.with_suffix('.train.jsonl'),
        stage2_file.with_suffix('.val.jsonl'),
        val_ratio=val_ratio,
    )

    return stats


# =============================================================================
# Commands
# =============================================================================

def cmd_sample(args):
    """Generate sample conversations for validation."""
    ensure_dirs()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = SYNTHETIC_DIR / f"sample_{timestamp}.jsonl"

    print(f"\n{'='*60}")
    print("SAMPLE GENERATION")
    print(f"{'='*60}")
    print(f"Output: {output_file}")
    print(f"Count: {args.count}")

    stats = generate_conversations(output_file, args.count, verbose=True)

    print(f"\n{'='*60}")
    print("SAMPLE STATS")
    print(f"{'='*60}")
    print(f"Total: {stats['total']}")
    print(f"With PII: {stats['with_pii']} ({stats['with_pii']/max(stats['total'],1)*100:.1f}%)")
    print(f"Without PII: {stats['without_pii']} ({stats['without_pii']/max(stats['total'],1)*100:.1f}%)")
    print(f"Errors: {stats['errors']}")
    print(f"\nBy category:")
    for cat, count in sorted(stats["by_category"].items()):
        print(f"  {cat}: {count}")

    print(f"\nSample conversations written to: {output_file}")
    print("\nNext steps:")
    print("1. Review sample conversations for quality")
    print("2. Check PII accuracy and realism")
    print("3. Verify voice-like patterns are present")
    print(f"4. Run full generation: uv run python -m scripts.dataset_prep.main generate --count 1000")


def cmd_generate(args):
    """Generate full dataset."""
    ensure_dirs()

    output_file = args.output or RAW_CONVERSATIONS

    print(f"\n{'='*60}")
    print("FULL GENERATION")
    print(f"{'='*60}")
    print(f"Output: {output_file}")
    print(f"Count: {args.count}")

    stats = generate_conversations(output_file, args.count, verbose=False)

    print(f"\n{'='*60}")
    print("GENERATION STATS")
    print(f"{'='*60}")
    print(f"Total: {stats['total']}")
    print(f"With PII: {stats['with_pii']} ({stats['with_pii']/max(stats['total'],1)*100:.1f}%)")
    print(f"Without PII: {stats['without_pii']}")
    print(f"Errors: {stats['errors']}")
    print(f"\nBy category:")
    for cat, count in sorted(stats["by_category"].items()):
        print(f"  {cat}: {count}")

    print(f"\nConversations written to: {output_file}")


def cmd_format(args):
    """Format conversations for training."""
    ensure_dirs()

    input_file = args.input or RAW_CONVERSATIONS
    stage1_file = args.stage1 or STAGE1_DATA
    stage2_file = args.stage2 or STAGE2_DATA

    print(f"\n{'='*60}")
    print("FORMATTING FOR TRAINING")
    print(f"{'='*60}")
    print(f"Input: {input_file}")

    # Stage 1
    stage1_stats = format_for_stage1(input_file, stage1_file)
    print(f"\nStage 1: {stage1_stats['examples']} examples")
    print(f"  FAIL: {stage1_stats['fail_examples']}")
    print(f"  SAFE: {stage1_stats['safe_examples']}")
    print(f"  Prefix: {stage1_stats['prefix_examples']}")
    print(f"  Full: {stage1_stats['full_examples']}")

    # Stage 2
    stage2_stats = format_for_stage2(input_file, stage2_file)
    print(f"\nStage 2: {stage2_stats['examples']} examples")
    print(f"  PASS: {stage2_stats['pass_examples']}")
    print(f"  MASK: {stage2_stats['mask_examples']}")
    print(f"  Entities: {stage2_stats['total_entities']}")

    # Splits
    if args.split:
        split_stats = create_splits(stage1_file, stage2_file, args.val_ratio)
        print(f"\nStage 1 splits:")
        print(f"  Train: {split_stats['stage1']['train_examples']} examples")
        print(f"  Val: {split_stats['stage1']['val_examples']} examples")
        print(f"\nStage 2 splits:")
        print(f"  Train: {split_stats['stage2']['train_examples']} examples")
        print(f"  Val: {split_stats['stage2']['val_examples']} examples")


def cmd_all(args):
    """Run full pipeline."""
    ensure_dirs()

    print(f"\n{'='*60}")
    print("FULL PIPELINE")
    print(f"{'='*60}")

    # Generate
    print("\n[1/3] Generating conversations...")
    gen_stats = generate_conversations(RAW_CONVERSATIONS, args.count)
    print(f"  Generated {gen_stats['total']} conversations")

    # Format
    print("\n[2/3] Formatting for training...")
    stage1_stats = format_for_stage1(RAW_CONVERSATIONS, STAGE1_DATA)
    stage2_stats = format_for_stage2(RAW_CONVERSATIONS, STAGE2_DATA)
    print(f"  Stage 1: {stage1_stats['examples']} examples")
    print(f"  Stage 2: {stage2_stats['examples']} examples")

    # Splits
    print("\n[3/3] Creating train/val splits...")
    split_stats = create_splits(STAGE1_DATA, STAGE2_DATA)

    print(f"\n{'='*60}")
    print("PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"\nOutput files:")
    print(f"  Raw: {RAW_CONVERSATIONS}")
    print(f"  Stage 1 train: {STAGE1_DATA.with_suffix('.train.jsonl')}")
    print(f"  Stage 1 val: {STAGE1_DATA.with_suffix('.val.jsonl')}")
    print(f"  Stage 2 train: {STAGE2_DATA.with_suffix('.train.jsonl')}")
    print(f"  Stage 2 val: {STAGE2_DATA.with_suffix('.val.jsonl')}")


def cmd_stats(args):
    """Print statistics about existing data."""
    input_file = args.input or RAW_CONVERSATIONS

    if not input_file.exists():
        print(f"File not found: {input_file}")
        return

    stats = {
        "total": 0,
        "with_pii": 0,
        "by_category": {},
        "by_topic": {},
        "by_modifier": {},
        "by_language": {},
        "message_counts": [],
    }

    with open(input_file, 'r') as f:
        for line in f:
            try:
                conv = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            stats["total"] += 1

            if conv.get("has_pii"):
                stats["with_pii"] += 1
                for cat in conv.get("pii_categories_present", []):
                    stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

            topic = conv.get("topic", "unknown")
            stats["by_topic"][topic] = stats["by_topic"].get(topic, 0) + 1

            modifier = conv.get("modifier", "unknown")
            stats["by_modifier"][modifier] = stats["by_modifier"].get(modifier, 0) + 1

            lang = conv.get("language", "unknown")
            stats["by_language"][lang] = stats["by_language"].get(lang, 0) + 1

            stats["message_counts"].append(len(conv.get("messages", [])))

    print(f"\n{'='*60}")
    print(f"STATISTICS: {input_file}")
    print(f"{'='*60}")
    print(f"Total conversations: {stats['total']}")
    print(f"With PII: {stats['with_pii']} ({stats['with_pii']/max(stats['total'],1)*100:.1f}%)")
    print(f"Without PII: {stats['total'] - stats['with_pii']}")

    if stats["message_counts"]:
        avg_msgs = sum(stats["message_counts"]) / len(stats["message_counts"])
        print(f"Avg messages/conversation: {avg_msgs:.1f}")

    print(f"\nBy category:")
    for cat, count in sorted(stats["by_category"].items(), key=lambda x: -x[1])[:10]:
        print(f"  {cat}: {count}")

    print(f"\nBy language:")
    for lang, count in sorted(stats["by_language"].items(), key=lambda x: -x[1]):
        print(f"  {lang}: {count}")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="PII dataset generation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # sample command
    sample_parser = subparsers.add_parser("sample", help="Generate sample conversations for validation")
    sample_parser.add_argument("--count", type=int, default=50, help="Number of samples")

    # generate command
    gen_parser = subparsers.add_parser("generate", help="Generate full dataset")
    gen_parser.add_argument("--count", type=int, default=1000, help="Number of conversations")
    gen_parser.add_argument("--output", type=Path, help="Output file path")

    # format command
    fmt_parser = subparsers.add_parser("format", help="Format conversations for training")
    fmt_parser.add_argument("--input", type=Path, help="Input JSONL file")
    fmt_parser.add_argument("--stage1", type=Path, help="Stage 1 output file")
    fmt_parser.add_argument("--stage2", type=Path, help="Stage 2 output file")
    fmt_parser.add_argument("--split", action="store_true", help="Create train/val splits")
    fmt_parser.add_argument("--val-ratio", type=float, default=0.1, help="Validation ratio")

    # all command
    all_parser = subparsers.add_parser("all", help="Run full pipeline")
    all_parser.add_argument("--count", type=int, default=1000, help="Number of conversations")

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Print dataset statistics")
    stats_parser.add_argument("--input", type=Path, help="Input JSONL file")

    args = parser.parse_args()

    if args.command == "sample":
        cmd_sample(args)
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "format":
        cmd_format(args)
    elif args.command == "all":
        cmd_all(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
