"""CLI entry point for the batch pipeline."""

import argparse
import json
import logging
import sys

from src.pipeline.runner import PipelineConfig, PipelineRunner


def main():
    """CLI entry point for batch processing."""
    parser = argparse.ArgumentParser(
        description="Batch Product Research Pipeline",
        usage="%(prog)s --input <file.xlsx> [options]",
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input Excel file path",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output Excel file path (default: results_<input>.xlsx)",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Pipeline config JSON file (overrides other args)",
    )
    parser.add_argument(
        "--sheet",
        default=None,
        help="Sheet name to read from",
    )
    parser.add_argument(
        "--header-row",
        type=int,
        default=1,
        help="Row number containing headers (default: 1)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Rows per batch (default: 10)",
    )
    parser.add_argument(
        "--collect-specs",
        action="store_true",
        default=True,
        help="Collect specifications (default: true)",
    )
    parser.add_argument(
        "--no-collect-specs",
        dest="collect_specs",
        action="store_false",
        help="Disable specification collection",
    )
    parser.add_argument(
        "--collect-media",
        choices=["images", "videos", "both", "none"],
        default="both",
        help="What media to collect (default: both)",
    )
    parser.add_argument(
        "--focus",
        default="",
        help="Comma-separated focus areas",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=30,
        help="Max iterations per row (default: 30)",
    )
    parser.add_argument(
        "--storage",
        choices=["local", "azure"],
        default="local",
        help="Storage backend (default: local)",
    )
    parser.add_argument(
        "--no-skip",
        dest="skip_existing",
        action="store_false",
        default=True,
        help="Re-process already completed rows",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.config:
        config = PipelineConfig.from_json(args.config)
    else:
        collect_media = args.collect_media if args.collect_media != "none" else None
        config = PipelineConfig(
            input_file=args.input,
            output_file=args.output,
            sheet=args.sheet,
            header_row=args.header_row,
            batch_size=args.batch_size,
            collect_specs=args.collect_specs,
            collect_media=collect_media,
            focus_areas=args.focus,
            max_iterations=args.max_iterations,
            storage_backend=args.storage,
            skip_existing=args.skip_existing,
        )

    runner = PipelineRunner(config)
    summary = runner.run()

    print("\n--- Pipeline Summary ---")
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
