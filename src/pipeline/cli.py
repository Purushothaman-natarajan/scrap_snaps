"""CLI entry point for the batch pipeline.

Parses command-line arguments for config.yaml or individual flags
(--input, --batch-size, --collect-media, etc.) and runs the PipelineRunner.

Default config: config.yaml (pipeline section). Legacy JSON config still
supported via --config flag.
"""

import argparse
import json
import logging
import sys

from src.pipeline.runner import PipelineConfig, PipelineRunner


def main():
    """CLI entry point for batch processing."""
    parser = argparse.ArgumentParser(
        description="Batch Product Research Pipeline",
        usage="%(prog)s [--input <file.xlsx>] [options]",
    )
    parser.add_argument(
        "--input", "-i",
        default=None,
        help="Input file path (.xlsx, .csv) (overrides config.yaml pipeline.input_file)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output Excel file path (overrides config.yaml pipeline.output_file)",
    )
    parser.add_argument(
        "--config", "-c",
        default=None,
        help="Config YAML/JSON file (default: config.yaml)",
    )
    parser.add_argument(
        "--sheet",
        default=None,
        help="Sheet name to read from (Excel only, ignored for CSV)",
    )
    parser.add_argument(
        "--query-column", "--qc",
        dest="query_column",
        default=None,
        help='Header name for item description column (e.g. "item description")',
    )
    parser.add_argument(
        "--query-columns-fallback",
        default=None,
        help='Comma-separated fallback columns (e.g. "product,query")',
    )
    parser.add_argument(
        "--csv-delimiter",
        default=None,
        help='CSV delimiter: auto, ,, ;, tab (default: auto)',
    )
    parser.add_argument(
        "--csv-encoding",
        default=None,
        help='CSV encoding: utf-8, utf-8-sig, latin1 (default: utf-8)',
    )
    parser.add_argument(
        "--header-row",
        type=int,
        default=None,
        help="Row number containing headers (default: from config.yaml)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Rows per batch (default: from config.yaml)",
    )
    parser.add_argument(
        "--collect-specs",
        action="store_true",
        default=None,
        help="Collect specifications",
    )
    parser.add_argument(
        "--no-collect-specs",
        dest="collect_specs",
        action="store_false",
        help="Disable specification collection",
    )
    parser.add_argument(
        "--collect-media",
        choices=[
            "images", "videos", "video_urls", "video_frames",
            "images_and_video_urls", "both", "none",
        ],
        default=None,
        help="What media to collect (default: from config.yaml)",
    )
    parser.add_argument(
        "--focus",
        default=None,
        help="Comma-separated focus areas",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Max iterations per row (default: from config.yaml)",
    )
    parser.add_argument(
        "--storage",
        choices=["local", "azure"],
        default=None,
        help="Storage backend (default: from config.yaml)",
    )
    parser.add_argument(
        "--no-skip",
        dest="skip_existing",
        action="store_false",
        default=None,
        help="Re-process already completed rows",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Load base config from YAML or JSON
    try:
        config = PipelineConfig.load(args.config)
    except FileNotFoundError:
        if args.input:
            # No config file, build from CLI args
            config = PipelineConfig(input_file=args.input)
        else:
            print("Error: No config.yaml found and no --input specified.", file=sys.stderr)
            sys.exit(1)

    # Override with CLI args (only if explicitly provided)
    if args.input:
        config.input_file = args.input
    if args.output:
        config.output_file = args.output
    if args.sheet:
        config.sheet = args.sheet
    if args.query_column:
        config.query_column = args.query_column
    if args.query_columns_fallback:
        config.query_columns_fallback = args.query_columns_fallback
    if args.csv_delimiter:
        config.csv_delimiter = args.csv_delimiter
    if args.csv_encoding:
        config.csv_encoding = args.csv_encoding
    if args.header_row is not None:
        config.header_row = args.header_row
    if args.batch_size is not None:
        config.batch_size = args.batch_size
    if args.collect_specs is not None:
        config.collect_specs = args.collect_specs
    if args.collect_media is not None:
        config.collect_media = None if args.collect_media == "none" else args.collect_media
    if args.focus:
        config.focus_areas = args.focus
    if args.max_iterations is not None:
        config.max_iterations = args.max_iterations
    if args.storage:
        config.storage_backend = args.storage
    if args.skip_existing is not None:
        config.skip_existing = args.skip_existing

    runner = PipelineRunner(config)
    summary = runner.run()

    print("\n--- Pipeline Summary ---")
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
