#!/usr/bin/env python3
"""
Evaluate PII detection models on validation set.

Usage:
    # Evaluate base model on Stage 1
    uv run python -m data.scripts.evaluate --stage 1

    # Evaluate base model on Stage 2
    uv run python -m data.scripts.evaluate --stage 2

    # Evaluate both stages
    uv run python -m data.scripts.evaluate --all

    # Evaluate fine-tuned model
    uv run python -m data.scripts.evaluate --stage 1 \
        --adapter models/adapters/stage1/qwen3-0.6b-pii-classifier

    # Save results to JSON
    uv run python -m data.scripts.evaluate --all --output results/baseline.json

    # Compare two result files
    uv run python -m data.scripts.evaluate --compare results/baseline.json results/finetuned.json
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def load_validation_data(stage: int, data_dir: Optional[Path] = None) -> list[dict]:
    """
    Load validation data from existing split.

    Args:
        stage: 1 or 2
        data_dir: Base data directory (default: data/training)

    Returns:
        List of examples with messages and ground truth
    """
    if data_dir is None:
        data_dir = Path("data/training")

    valid_file = data_dir / f"stage{stage}_mlx" / "valid.jsonl"

    if not valid_file.exists():
        print(f"ERROR: Validation file not found: {valid_file}")
        print("Run the data generation pipeline first:")
        print("  uv run python -m data.scripts.main all --count 100")
        print("  uv run python -m data.scripts.convert_to_mlx --stage 1")
        print("  uv run python -m data.scripts.convert_to_mlx --stage 2")
        sys.exit(1)

    examples = []
    with open(valid_file, "r") as f:
        for line in f:
            if line.strip():
                examples.append(json.loads(line))

    return examples


def evaluate_stage1(
    adapter_path: Optional[str] = None,
    data_dir: Optional[Path] = None,
    limit: Optional[int] = None,
    verbose: bool = False,
    log_file: Optional[Path] = None,
) -> dict:
    """
    Evaluate Stage 1 classification using MLX sequence log-likelihood.

    Args:
        adapter_path: Optional path to LoRA adapter
        data_dir: Data directory
        limit: Limit number of examples (for testing)
        verbose: Print per-example results
        log_file: Optional path to write detailed per-example results as JSONL

    Returns:
        Dict with metrics
    """
    from sklearn.metrics import (
        accuracy_score,
        confusion_matrix,
        f1_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    from ccpp.llm.base import LogitExtractionConfig
    from ccpp.llm.mlx_backend import MLXBackend

    # Load validation data
    examples = load_validation_data(1, data_dir)
    if limit:
        examples = examples[:limit]

    print(f"Evaluating Stage 1 on {len(examples)} examples...")

    # Initialize backend
    model_name = "mlx-community/Qwen3-0.6B-4bit"
    print(f"Loading model: {model_name}")
    if adapter_path:
        print(f"With adapter: {adapter_path}")

    backend = MLXBackend(model_name=model_name, adapter_path=adapter_path)

    # Config for logit extraction
    logit_config = LogitExtractionConfig(
        token_a="SAFE",
        token_b="FAIL",
        enable_thinking=False,
    )

    # Evaluate each example
    predictions = []
    labels = []
    latencies = []
    logged_examples = []

    for i, ex in enumerate(examples):
        messages = ex["messages"]

        # Extract ground truth from assistant response
        ground_truth = messages[-1]["content"].strip().upper()
        labels.append(ground_truth)

        # Get prediction (messages without assistant response)
        prompt_messages = messages[:-1]

        # Extract user content (buffer text) for logging
        user_content = messages[1]["content"] if len(messages) > 1 else ""

        start_time = time.time()
        prob_safe, prob_fail = backend.extract_sequence_probs(prompt_messages, logit_config)
        latency = time.time() - start_time
        latencies.append(latency)

        predictions.append(prob_fail)

        predicted = "FAIL" if prob_fail >= 0.5 else "SAFE"
        correct = predicted == ground_truth

        # Log detailed example
        logged_examples.append({
            "index": i,
            "ground_truth": ground_truth,
            "predicted": predicted,
            "prob_fail": prob_fail,
            "prob_safe": prob_safe,
            "correct": correct,
            "latency_s": latency,
            "user_content": user_content,
        })

        if verbose:
            correct_str = "Y" if correct else "N"
            print(f"  [{i+1}/{len(examples)}] GT={ground_truth}, P(FAIL)={prob_fail:.3f}, Correct={correct_str}")

        if (i + 1) % 10 == 0 and not verbose:
            print(f"  Processed {i+1}/{len(examples)} examples...")

    # Write log file
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "w") as f:
            for ex in logged_examples:
                f.write(json.dumps(ex) + "\n")
        print(f"Detailed log written to: {log_file}")

    # Convert to binary
    y_true = [1 if l == "FAIL" else 0 for l in labels]
    y_pred = [1 if p >= 0.5 else 0 for p in predictions]

    # Compute metrics
    metrics = {
        "examples": len(examples),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
    }

    # AUROC (only if both classes present)
    if len(set(y_true)) > 1:
        metrics["auroc"] = float(roc_auc_score(y_true, predictions))
    else:
        metrics["auroc"] = None

    # False positive rate
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    metrics["fpr"] = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    metrics["fnr"] = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

    # Latency
    metrics["latency_avg_s"] = float(sum(latencies) / len(latencies))
    metrics["latency_total_s"] = float(sum(latencies))

    # Class distribution
    metrics["num_safe"] = int(sum(1 for l in labels if l == "SAFE"))
    metrics["num_fail"] = int(sum(1 for l in labels if l == "FAIL"))

    return metrics


def parse_mask_commands(text: str) -> list[dict]:
    """
    Parse MASK commands from model output.

    Args:
        text: Model output text

    Returns:
        List of {"text": entity_text, "category": category}
    """
    if text.strip().upper() == "PASS":
        return []

    entities = []
    # Pattern: MASK "entity" category
    pattern = r'MASK\s+"((?:[^"\\]|\\.)*)"\s+(\S+)'

    for match in re.finditer(pattern, text):
        entity_text = match.group(1).replace('\\"', '"')
        category = match.group(2).lower()
        entities.append({"text": entity_text, "category": category})

    return entities


def evaluate_stage2(
    adapter_path: Optional[str] = None,
    data_dir: Optional[Path] = None,
    limit: Optional[int] = None,
    verbose: bool = False,
    log_file: Optional[Path] = None,
) -> dict:
    """
    Evaluate Stage 2 entity extraction using text generation.

    Args:
        adapter_path: Optional path to LoRA adapter
        data_dir: Data directory
        limit: Limit number of examples (for testing)
        verbose: Print per-example results
        log_file: Optional path to write detailed per-example results as JSONL

    Returns:
        Dict with metrics
    """
    from mlx_lm import generate

    from ccpp.llm.mlx_backend import MLXBackend

    # Load validation data
    examples = load_validation_data(2, data_dir)
    if limit:
        examples = examples[:limit]

    print(f"Evaluating Stage 2 on {len(examples)} examples...")

    # Initialize backend
    model_name = "Qwen/Qwen3-1.7B-MLX-8bit"
    print(f"Loading model: {model_name}")
    if adapter_path:
        print(f"With adapter: {adapter_path}")

    backend = MLXBackend(model_name=model_name, adapter_path=adapter_path)

    # Evaluate each example
    all_pred_entities = []
    all_gt_entities = []
    latencies = []
    logged_examples = []

    for i, ex in enumerate(examples):
        messages = ex["messages"]

        # Extract ground truth from assistant response
        gt_text = messages[-1]["content"].strip()
        gt_entities = parse_mask_commands(gt_text)
        all_gt_entities.append(gt_entities)

        # Get prediction (messages without assistant response)
        prompt_messages = messages[:-1]

        # Extract user content for logging
        user_content = messages[1]["content"] if len(messages) > 1 else ""

        # Apply chat template
        prompt = backend.tokenizer.apply_chat_template(
            prompt_messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )

        start_time = time.time()
        response = generate(
            backend.model,
            backend.tokenizer,
            prompt=prompt,
            max_tokens=100,
            verbose=False,
        )
        latency = time.time() - start_time
        latencies.append(latency)

        # Clean response
        raw_response = response
        response = response.strip()
        if "</think>" in response:
            response = response.split("</think>")[-1].strip()

        pred_entities = parse_mask_commands(response)
        all_pred_entities.append(pred_entities)

        # Log detailed example
        pred_texts = {e["text"] for e in pred_entities}
        gt_texts = {e["text"] for e in gt_entities}
        logged_examples.append({
            "index": i,
            "ground_truth_text": gt_text,
            "predicted_text": response,
            "raw_response": raw_response,
            "gt_entities": gt_entities,
            "pred_entities": pred_entities,
            "tp": len(pred_texts & gt_texts),
            "fp": len(pred_texts - gt_texts),
            "fn": len(gt_texts - pred_texts),
            "latency_s": latency,
            "user_content": user_content,
        })

        if verbose:
            print(f"  [{i+1}/{len(examples)}]")
            print(f"    GT: {gt_text[:60]}...")
            print(f"    Pred: {response[:60]}...")
            print(f"    GT entities: {[e['text'] for e in gt_entities]}")
            print(f"    Pred entities: {[e['text'] for e in pred_entities]}")

        if (i + 1) % 5 == 0 and not verbose:
            print(f"  Processed {i+1}/{len(examples)} examples...")

    # Write log file
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "w") as f:
            for ex in logged_examples:
                f.write(json.dumps(ex) + "\n")
        print(f"Detailed log written to: {log_file}")

    # Compute entity-level metrics
    tp, fp, fn = 0, 0, 0
    exact_matches = 0
    category_matches = 0
    total_gt_entities = 0

    for pred_entities, gt_entities in zip(all_pred_entities, all_gt_entities):
        pred_texts = {e["text"] for e in pred_entities}
        gt_texts = {e["text"] for e in gt_entities}

        tp += len(pred_texts & gt_texts)
        fp += len(pred_texts - gt_texts)
        fn += len(gt_texts - pred_texts)

        # Category accuracy (for matched entities)
        for gt in gt_entities:
            total_gt_entities += 1
            for pred in pred_entities:
                if pred["text"] == gt["text"]:
                    exact_matches += 1
                    if pred["category"] == gt["category"]:
                        category_matches += 1
                    break

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    metrics = {
        "examples": len(examples),
        "entity_precision": float(precision),
        "entity_recall": float(recall),
        "entity_f1": float(f1),
        "exact_match_rate": float(exact_matches / total_gt_entities) if total_gt_entities > 0 else 0,
        "category_accuracy": float(category_matches / exact_matches) if exact_matches > 0 else 0,
        "total_gt_entities": total_gt_entities,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "latency_avg_s": float(sum(latencies) / len(latencies)),
        "latency_total_s": float(sum(latencies)),
    }

    return metrics


def print_report(
    stage1_metrics: Optional[dict],
    stage2_metrics: Optional[dict],
    model_name: str,
):
    """Print formatted evaluation report."""
    print()
    print("=" * 60)
    print(f"Evaluation Report: {model_name}")
    print("=" * 60)

    if stage1_metrics:
        print(f"\nStage 1: Classification (SAFE/FAIL)")
        print(f"  Examples:     {stage1_metrics['examples']}")
        print(f"  Distribution: {stage1_metrics['num_safe']} SAFE, {stage1_metrics['num_fail']} FAIL")
        print(f"  Accuracy:     {stage1_metrics['accuracy']:.3f}")
        print(f"  Precision:    {stage1_metrics['precision']:.3f}")
        print(f"  Recall:       {stage1_metrics['recall']:.3f}")
        print(f"  F1 Score:     {stage1_metrics['f1']:.3f}")
        if stage1_metrics['auroc'] is not None:
            print(f"  AUROC:        {stage1_metrics['auroc']:.3f}")
        print(f"  FPR:          {stage1_metrics['fpr']:.3f}")
        print(f"  FNR:          {stage1_metrics['fnr']:.3f}")
        print(f"  Latency avg:  {stage1_metrics['latency_avg_s']:.2f}s")

    if stage2_metrics:
        print(f"\nStage 2: Entity Extraction")
        print(f"  Examples:         {stage2_metrics['examples']}")
        print(f"  GT Entities:      {stage2_metrics['total_gt_entities']}")
        print(f"  Entity Precision: {stage2_metrics['entity_precision']:.3f}")
        print(f"  Entity Recall:    {stage2_metrics['entity_recall']:.3f}")
        print(f"  Entity F1:        {stage2_metrics['entity_f1']:.3f}")
        print(f"  Exact Match:      {stage2_metrics['exact_match_rate']:.3f}")
        print(f"  Category Acc:     {stage2_metrics['category_accuracy']:.3f}")
        print(f"  TP/FP/FN:         {stage2_metrics['tp']}/{stage2_metrics['fp']}/{stage2_metrics['fn']}")
        print(f"  Latency avg:      {stage2_metrics['latency_avg_s']:.2f}s")

    print()


def compare_results(baseline_path: Path, finetuned_path: Path):
    """Compare baseline and fine-tuned results."""
    with open(baseline_path) as f:
        baseline = json.load(f)
    with open(finetuned_path) as f:
        finetuned = json.load(f)

    print()
    print("=" * 60)
    print("Comparison: Baseline vs Fine-tuned")
    print("=" * 60)

    if "stage1" in baseline and "stage1" in finetuned:
        print("\nStage 1: Classification")
        b1, f1 = baseline["stage1"], finetuned["stage1"]
        for metric in ["accuracy", "precision", "recall", "f1", "fpr"]:
            if metric in b1 and metric in f1:
                diff = f1[metric] - b1[metric]
                direction = "+" if diff > 0 else ""
                # For FPR, lower is better
                improvement = "improved" if (diff > 0 and metric != "fpr") or (diff < 0 and metric == "fpr") else "worse"
                print(f"  {metric:12s}: {b1[metric]:.3f} → {f1[metric]:.3f} ({direction}{diff:.3f}) [{improvement}]")

    if "stage2" in baseline and "stage2" in finetuned:
        print("\nStage 2: Entity Extraction")
        b2, f2 = baseline["stage2"], finetuned["stage2"]
        for metric in ["entity_precision", "entity_recall", "entity_f1", "exact_match_rate"]:
            if metric in b2 and metric in f2:
                diff = f2[metric] - b2[metric]
                direction = "+" if diff > 0 else ""
                improvement = "improved" if diff > 0 else "worse"
                print(f"  {metric:18s}: {b2[metric]:.3f} → {f2[metric]:.3f} ({direction}{diff:.3f}) [{improvement}]")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate PII detection models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--stage",
        type=int,
        choices=[1, 2],
        help="Stage to evaluate (1=classification, 2=extraction)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Evaluate both stages",
    )
    parser.add_argument(
        "--adapter",
        "--stage1-adapter",
        type=str,
        dest="stage1_adapter",
        help="Path to Stage 1 LoRA adapter",
    )
    parser.add_argument(
        "--stage2-adapter",
        type=str,
        help="Path to Stage 2 LoRA adapter",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/training"),
        help="Data directory (default: data/training)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        type=Path,
        metavar=("BASELINE", "FINETUNED"),
        help="Compare two result files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of examples (for testing)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print per-example results",
    )
    parser.add_argument(
        "--log",
        type=Path,
        help="Save detailed per-example results to JSONL (auto-generates stage1.log.jsonl and stage2.log.jsonl if directory)",
    )

    args = parser.parse_args()

    # Handle comparison mode
    if args.compare:
        compare_results(args.compare[0], args.compare[1])
        return

    # Determine what to evaluate
    if not args.stage and not args.all:
        print("ERROR: Specify --stage 1, --stage 2, or --all")
        sys.exit(1)

    results = {}
    stage1_metrics = None
    stage2_metrics = None

    # Determine log file paths
    stage1_log = None
    stage2_log = None
    if args.log:
        if args.log.is_dir() or str(args.log).endswith("/"):
            # If directory, auto-generate filenames
            log_dir = args.log
            log_dir.mkdir(parents=True, exist_ok=True)
            stage1_log = log_dir / "stage1.log.jsonl"
            stage2_log = log_dir / "stage2.log.jsonl"
        elif args.stage == 1:
            stage1_log = args.log
        elif args.stage == 2:
            stage2_log = args.log
        else:
            # --all mode with a file path - use as base
            base = args.log.stem
            parent = args.log.parent
            parent.mkdir(parents=True, exist_ok=True)
            stage1_log = parent / f"{base}_stage1.jsonl"
            stage2_log = parent / f"{base}_stage2.jsonl"

    # Evaluate Stage 1
    if args.stage == 1 or args.all:
        stage1_metrics = evaluate_stage1(
            adapter_path=args.stage1_adapter,
            data_dir=args.data_dir,
            limit=args.limit,
            verbose=args.verbose,
            log_file=stage1_log,
        )
        results["stage1"] = stage1_metrics

    # Evaluate Stage 2
    if args.stage == 2 or args.all:
        stage2_metrics = evaluate_stage2(
            adapter_path=args.stage2_adapter,
            data_dir=args.data_dir,
            limit=args.limit,
            verbose=args.verbose,
            log_file=stage2_log,
        )
        results["stage2"] = stage2_metrics

    # Print report
    model_name = "Base Model"
    if args.stage1_adapter or args.stage2_adapter:
        model_name = "Fine-tuned Model"

    print_report(stage1_metrics, stage2_metrics, model_name)

    # Save results
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to: {args.output}")


if __name__ == "__main__":
    main()
