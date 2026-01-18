#!/usr/bin/env python3
"""
Test script for the conversation generator and formatters.

Generates a small number of test conversations and outputs:
1. The generated conversations (pretty-printed)
2. All prompt/response pairs used to generate them
3. Stage 1 training examples (speculative classification)
4. Stage 2 training examples (entity extraction)

Usage:
    uv run python -m scripts.dataset_prep.test_generator --count 3
    uv run python -m scripts.dataset_prep.test_generator --count 5 --output-dir data/test_output
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from .generator import ConversationGenerator
from .formatter import format_conversation_for_stage1, Stage1Example
from .stage2_formatter import format_conversation_for_stage2, Stage2Example
from .topics import PIICategory


def setup_logging(verbose: bool = False):
    """Configure logging for the test script."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main():
    parser = argparse.ArgumentParser(
        description="Test the conversation generator with full prompt/response logging"
    )
    parser.add_argument(
        "--count", type=int, default=3, help="Number of conversations to generate"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory to save output files (default: print to stdout)",
    )
    parser.add_argument(
        "--pii", action="store_true", help="Force all conversations to include PII"
    )
    parser.add_argument(
        "--no-pii", action="store_true", help="Force all conversations to exclude PII"
    )
    parser.add_argument(
        "--category",
        type=str,
        choices=[c.value for c in PIICategory],
        help="Force a specific PII category",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )

    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Determine PII settings
    include_pii = None
    if args.pii:
        include_pii = True
    elif args.no_pii:
        include_pii = False

    pii_category = None
    if args.category:
        pii_category = PIICategory(args.category)

    # Collect all API calls
    api_calls: list[dict] = []

    def capture_api_call(call_data: dict):
        """Callback to capture API call details."""
        api_calls.append(call_data)

    # Initialize generator with callback
    generator = ConversationGenerator(on_api_call=capture_api_call)

    # Generate conversations
    conversations = []
    print(f"\n{'='*80}")
    print(f"GENERATING {args.count} TEST CONVERSATIONS")
    print(f"{'='*80}\n")

    for i in range(args.count):
        print(f"[{i+1}/{args.count}] Generating conversation...")
        try:
            conv = generator.generate_conversation(
                include_pii=include_pii,
                pii_category=pii_category,
            )
            conversations.append(conv)
            print(f"  -> {conv.conversation_id}: {len(conv.messages)} messages, "
                  f"has_pii={conv.has_pii}, categories={conv.pii_categories_present}")
        except Exception as e:
            logger.error(f"Failed to generate conversation {i+1}: {e}")
            continue

    # Format conversations for training
    print(f"\n{'='*80}")
    print("FORMATTING FOR TRAINING")
    print(f"{'='*80}\n")

    all_stage1_examples: list[Stage1Example] = []
    all_stage2_examples: list[Stage2Example] = []

    for conv in conversations:
        conv_dict = conv.to_dict()

        # Stage 1: speculative classification (with prefix examples)
        stage1_examples = format_conversation_for_stage1(conv_dict, include_prefixes=True)
        all_stage1_examples.extend(stage1_examples)

        # Stage 2: entity extraction
        stage2_examples = format_conversation_for_stage2(conv_dict)
        all_stage2_examples.extend(stage2_examples)

    print(f"Stage 1 examples: {len(all_stage1_examples)} (includes prefixes)")
    print(f"  FAIL: {sum(1 for e in all_stage1_examples if e.label == 'FAIL')}")
    print(f"  SAFE: {sum(1 for e in all_stage1_examples if e.label == 'SAFE')}")
    print(f"  Full buffer: {sum(1 for e in all_stage1_examples if e.is_full)}")
    print(f"  Prefixes: {sum(1 for e in all_stage1_examples if not e.is_full)}")

    print(f"\nStage 2 examples: {len(all_stage2_examples)}")
    print(f"  PASS: {sum(1 for e in all_stage2_examples if e.target_output == 'PASS')}")
    print(f"  MASK: {sum(1 for e in all_stage2_examples if e.target_output != 'PASS')}")

    # Output results
    if args.output_dir:
        # Save to files
        args.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save conversations
        conv_file = args.output_dir / f"conversations_{timestamp}.jsonl"
        with open(conv_file, "w") as f:
            for conv in conversations:
                f.write(conv.to_jsonl() + "\n")
        print(f"\nConversations saved to: {conv_file}")

        # Save API calls (prompt/response pairs)
        api_file = args.output_dir / f"api_calls_{timestamp}.json"
        with open(api_file, "w") as f:
            json.dump(api_calls, f, indent=2)
        print(f"API calls saved to: {api_file}")

        # Save Stage 1 examples
        stage1_file = args.output_dir / f"stage1_examples_{timestamp}.jsonl"
        with open(stage1_file, "w") as f:
            for ex in all_stage1_examples:
                f.write(ex.to_jsonl() + "\n")
        print(f"Stage 1 examples saved to: {stage1_file}")

        # Save Stage 2 examples
        stage2_file = args.output_dir / f"stage2_examples_{timestamp}.jsonl"
        with open(stage2_file, "w") as f:
            for ex in all_stage2_examples:
                f.write(ex.to_jsonl() + "\n")
        print(f"Stage 2 examples saved to: {stage2_file}")

        # Save human-readable summary
        summary_file = args.output_dir / f"summary_{timestamp}.txt"
        with open(summary_file, "w") as f:
            _write_summary(f, conversations, api_calls, all_stage1_examples, all_stage2_examples)
        print(f"Summary saved to: {summary_file}")

    else:
        # Print to stdout
        _print_results(conversations, api_calls, all_stage1_examples, all_stage2_examples)


def _write_summary(f, conversations: list, api_calls: list,
                   stage1_examples: list, stage2_examples: list):
    """Write a human-readable summary to a file."""
    f.write("=" * 80 + "\n")
    f.write("CONVERSATION GENERATION TEST SUMMARY\n")
    f.write("=" * 80 + "\n\n")

    f.write(f"Total conversations: {len(conversations)}\n")
    f.write(f"Total API calls: {len(api_calls)}\n\n")

    # Stats
    with_pii = sum(1 for c in conversations if c.has_pii)
    f.write(f"With PII: {with_pii}\n")
    f.write(f"Without PII: {len(conversations) - with_pii}\n\n")

    # Category breakdown
    categories = {}
    for conv in conversations:
        for cat in conv.pii_categories_present:
            categories[cat] = categories.get(cat, 0) + 1
    if categories:
        f.write("PII categories:\n")
        for cat, count in sorted(categories.items()):
            f.write(f"  {cat}: {count}\n")
        f.write("\n")

    # Training data stats
    f.write("-" * 40 + "\n")
    f.write("TRAINING DATA STATS\n")
    f.write("-" * 40 + "\n\n")

    f.write(f"Stage 1 examples: {len(stage1_examples)}\n")
    f.write(f"  FAIL: {sum(1 for e in stage1_examples if e.label == 'FAIL')}\n")
    f.write(f"  SAFE: {sum(1 for e in stage1_examples if e.label == 'SAFE')}\n")
    f.write(f"  Full buffer: {sum(1 for e in stage1_examples if e.is_full)}\n")
    f.write(f"  Prefixes: {sum(1 for e in stage1_examples if not e.is_full)}\n\n")

    f.write(f"Stage 2 examples: {len(stage2_examples)}\n")
    f.write(f"  PASS: {sum(1 for e in stage2_examples if e.target_output == 'PASS')}\n")
    f.write(f"  MASK: {sum(1 for e in stage2_examples if e.target_output != 'PASS')}\n\n")

    # Each conversation
    for i, (conv, api_call) in enumerate(zip(conversations, api_calls)):
        f.write("=" * 80 + "\n")
        f.write(f"CONVERSATION {i+1}: {conv.conversation_id}\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Topic: {conv.topic}\n")
        f.write(f"Modifier: {conv.modifier}\n")
        f.write(f"Language: {conv.language}\n")
        f.write(f"Has PII: {conv.has_pii}\n")
        f.write(f"PII Categories: {conv.pii_categories_present}\n\n")

        f.write("-" * 40 + "\n")
        f.write("MESSAGES:\n")
        f.write("-" * 40 + "\n\n")

        for msg in conv.messages:
            f.write(f"[{msg.role.upper()}]\n")
            f.write(f"  Content: {msg.content}\n")
            if msg.content_redacted != msg.content:
                f.write(f"  Redacted: {msg.content_redacted}\n")
            if msg.pii_entities:
                f.write(f"  PII Entities: {[e.to_dict() for e in msg.pii_entities]}\n")
            f.write("\n")

        f.write("-" * 40 + "\n")
        f.write("PROMPT USED:\n")
        f.write("-" * 40 + "\n\n")

        f.write("=== SYSTEM PROMPT ===\n")
        f.write(api_call["system_prompt"] + "\n\n")

        f.write("=== USER PROMPT ===\n")
        f.write(api_call["user_prompt"] + "\n\n")

        f.write("-" * 40 + "\n")
        f.write("RAW RESPONSE:\n")
        f.write("-" * 40 + "\n\n")
        f.write(api_call["response_text"] + "\n\n")

    # Training examples section
    f.write("\n" + "=" * 80 + "\n")
    f.write("STAGE 1 TRAINING EXAMPLES (Speculative Classification)\n")
    f.write("=" * 80 + "\n\n")

    f.write("Format: buffer text -> label (category)\n")
    f.write("Full examples show complete user message, prefix examples show partial.\n\n")

    # Show some FAIL examples (full buffer only for clarity)
    fail_examples = [e for e in stage1_examples if e.label == "FAIL" and e.is_full]
    f.write(f"--- FAIL Examples ({len(fail_examples)} total full-buffer) ---\n\n")
    for ex in fail_examples[:5]:  # Show up to 5
        context_summary = f"[{len(ex.context)} prior messages]" if ex.context else "[no context]"
        f.write(f"Context: {context_summary}\n")
        f.write(f"Buffer: {ex.buffer}\n")
        f.write(f"Label: {ex.label} ({ex.category})\n\n")

    # Show some SAFE examples
    safe_examples = [e for e in stage1_examples if e.label == "SAFE" and e.is_full]
    f.write(f"--- SAFE Examples ({len(safe_examples)} total full-buffer) ---\n\n")
    for ex in safe_examples[:5]:  # Show up to 5
        context_summary = f"[{len(ex.context)} prior messages]" if ex.context else "[no context]"
        f.write(f"Context: {context_summary}\n")
        f.write(f"Buffer: {ex.buffer}\n")
        f.write(f"Label: {ex.label}\n\n")

    # Show prefix examples for one message
    f.write("--- Prefix Examples (showing speculative classification) ---\n\n")
    if fail_examples:
        # Find all prefixes for the first FAIL example's buffer
        first_fail = fail_examples[0]
        prefixes = [e for e in stage1_examples if e.buffer in first_fail.buffer or first_fail.buffer.startswith(e.buffer)]
        prefixes = sorted(prefixes, key=lambda x: len(x.buffer))[:8]  # First 8 prefixes
        f.write(f"Prefixes of: \"{first_fail.buffer[:50]}...\"\n\n")
        for ex in prefixes:
            f.write(f"  \"{ex.buffer[:60]}{'...' if len(ex.buffer) > 60 else ''}\" -> {ex.label}\n")
        f.write("\n")

    f.write("\n" + "=" * 80 + "\n")
    f.write("STAGE 2 TRAINING EXAMPLES (Entity Extraction)\n")
    f.write("=" * 80 + "\n\n")

    f.write("Format: window_text -> target_output\n\n")

    # Show MASK examples
    mask_examples = [e for e in stage2_examples if e.target_output != "PASS"]
    f.write(f"--- MASK Examples ({len(mask_examples)} total) ---\n\n")
    for ex in mask_examples[:5]:  # Show up to 5
        context_summary = f"[{len(ex.context)} prior messages]" if ex.context else "[no context]"
        f.write(f"Context: {context_summary}\n")
        f.write(f"Window: {ex.window_text}\n")
        f.write(f"Output: {ex.target_output}\n\n")

    # Show PASS examples
    pass_examples = [e for e in stage2_examples if e.target_output == "PASS"]
    f.write(f"--- PASS Examples ({len(pass_examples)} total) ---\n\n")
    for ex in pass_examples[:3]:  # Show up to 3
        context_summary = f"[{len(ex.context)} prior messages]" if ex.context else "[no context]"
        f.write(f"Context: {context_summary}\n")
        f.write(f"Window: {ex.window_text}\n")
        f.write(f"Output: {ex.target_output}\n\n")


def _print_results(conversations: list, api_calls: list,
                   stage1_examples: list, stage2_examples: list):
    """Print results to stdout."""
    print("\n" + "=" * 80)
    print("GENERATED CONVERSATIONS")
    print("=" * 80)

    for i, conv in enumerate(conversations):
        print(f"\n--- Conversation {i+1}: {conv.conversation_id} ---")
        print(f"Topic: {conv.topic}")
        print(f"Modifier: {conv.modifier}")
        print(f"Language: {conv.language}")
        print(f"Has PII: {conv.has_pii}")
        print(f"PII Categories: {conv.pii_categories_present}")
        print("\nMessages:")

        for msg in conv.messages:
            print(f"\n  [{msg.role.upper()}]")
            print(f"    {msg.content}")
            if msg.content_redacted != msg.content:
                print(f"    [Redacted: {msg.content_redacted}]")
            if msg.pii_entities:
                print(f"    [PII: {[e.to_dict() for e in msg.pii_entities]}]")

    print("\n" + "=" * 80)
    print("API CALLS (PROMPT/RESPONSE PAIRS)")
    print("=" * 80)

    for i, call in enumerate(api_calls):
        print(f"\n{'='*60}")
        print(f"API CALL {i+1}")
        print(f"{'='*60}")

        print(f"\nModel: {call['model']}")
        print(f"Temperature: {call['temperature']}")
        print(f"Topic: {call['topic']}")
        print(f"Modifier: {call['modifier']}")
        print(f"Language: {call['language']}")
        print(f"Include PII: {call['include_pii']}")
        print(f"PII Category: {call['pii_category']}")

        print(f"\n--- SYSTEM PROMPT ({len(call['system_prompt'])} chars) ---")
        # Print first 500 chars of system prompt
        if len(call["system_prompt"]) > 500:
            print(call["system_prompt"][:500] + "...[truncated]")
        else:
            print(call["system_prompt"])

        print(f"\n--- USER PROMPT ({len(call['user_prompt'])} chars) ---")
        print(call["user_prompt"])

        print(f"\n--- RESPONSE ({len(call['response_text'])} chars) ---")
        # Print first 1000 chars of response
        if len(call["response_text"]) > 1000:
            print(call["response_text"][:1000] + "...[truncated]")
        else:
            print(call["response_text"])

    # Training examples
    print("\n" + "=" * 80)
    print("STAGE 1 TRAINING EXAMPLES (Speculative Classification)")
    print("=" * 80)

    # Show some FAIL examples (full buffer only)
    fail_examples = [e for e in stage1_examples if e.label == "FAIL" and e.is_full]
    print(f"\n--- FAIL Examples ({len(fail_examples)} total full-buffer) ---")
    for ex in fail_examples[:3]:
        print(f"\n  Buffer: {ex.buffer[:80]}{'...' if len(ex.buffer) > 80 else ''}")
        print(f"  Label: {ex.label} ({ex.category})")

    # Show some SAFE examples
    safe_examples = [e for e in stage1_examples if e.label == "SAFE" and e.is_full]
    print(f"\n--- SAFE Examples ({len(safe_examples)} total full-buffer) ---")
    for ex in safe_examples[:3]:
        print(f"\n  Buffer: {ex.buffer[:80]}{'...' if len(ex.buffer) > 80 else ''}")
        print(f"  Label: {ex.label}")

    print("\n" + "=" * 80)
    print("STAGE 2 TRAINING EXAMPLES (Entity Extraction)")
    print("=" * 80)

    # Show MASK examples
    mask_examples = [e for e in stage2_examples if e.target_output != "PASS"]
    print(f"\n--- MASK Examples ({len(mask_examples)} total) ---")
    for ex in mask_examples[:3]:
        print(f"\n  Window: {ex.window_text[:80]}{'...' if len(ex.window_text) > 80 else ''}")
        print(f"  Output: {ex.target_output}")

    # Show PASS examples
    pass_examples = [e for e in stage2_examples if e.target_output == "PASS"]
    print(f"\n--- PASS Examples ({len(pass_examples)} total) ---")
    for ex in pass_examples[:2]:
        print(f"\n  Window: {ex.window_text[:80]}{'...' if len(ex.window_text) > 80 else ''}")
        print(f"  Output: {ex.target_output}")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total conversations: {len(conversations)}")
    print(f"Total API calls: {len(api_calls)}")
    with_pii = sum(1 for c in conversations if c.has_pii)
    print(f"With PII: {with_pii}")
    print(f"Without PII: {len(conversations) - with_pii}")

    print(f"\nStage 1 examples: {len(stage1_examples)}")
    print(f"  FAIL: {sum(1 for e in stage1_examples if e.label == 'FAIL')}")
    print(f"  SAFE: {sum(1 for e in stage1_examples if e.label == 'SAFE')}")

    print(f"\nStage 2 examples: {len(stage2_examples)}")
    print(f"  MASK: {len(mask_examples)}")
    print(f"  PASS: {len(pass_examples)}")

    categories = {}
    for conv in conversations:
        for cat in conv.pii_categories_present:
            categories[cat] = categories.get(cat, 0) + 1
    if categories:
        print("\nPII categories:")
        for cat, count in sorted(categories.items()):
            print(f"  {cat}: {count}")


if __name__ == "__main__":
    main()
