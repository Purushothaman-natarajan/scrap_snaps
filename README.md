# scrap_snaps

Autonomous product research agent powered by LangGraph. Given a product query, it discovers the product, extracts technical specifications, collects images from multiple views, and builds a verified evidence dossier. Supports both single-query mode and batch processing from Excel files.

## Features

- **Autonomous research loop** — Planner, discover, verify, coverage cycle with automatic termination
- **Focus-aware search** — Configurable focus areas (product pages, seller images, YouTube, specs)
- **Configurable collection** — Collect specs only, media only, or both
- **Search caching** — In-memory cache avoids redundant SerpAPI calls within a run
- **Failure tracking** — 403/bot-detection failures are tracked and never retried
- **Task dedup** — LLM-based dedup prevents planner loops on identical tasks
- **Batch pipeline** — Process millions of rows from Excel with checkpointing
- **Streaming I/O** — openpyxl read_only/write_only for large files
- **Structured database** — SQLAlchemy models for products, sources, claims, images, videos

## Agent Graph Flow

```mermaid
flowchart TD
    Start(["START"]) --> PLANNER["Planner"]

    PLANNER -- "discover" --> DISCOVER["Discovery\nsearch_web -> extract candidates"]
    PLANNER -- "verify_spec" --> EVIDENCE["Evidence\nsearch_web -> fetch_page -> extract specs"]
    PLANNER -- "find_images" --> MEDIA_COLLECTOR["Media\nsearch_images -> download -> classify"]
    PLANNER -- "find_videos" --> VIDEO_EXTRACTOR["Video\nsearch_videos -> download -> extract frames"]
    PLANNER -- "no tasks" --> FINALIZE["Finalize"]

    DISCOVER --> VERIFY
    EVIDENCE --> VERIFY
    MEDIA_COLLECTOR --> VERIFY
    VIDEO_EXTRACTOR --> VERIFY

    VERIFY["Verify\nscore confidence"] --> COVERAGE["Coverage\ngap analysis"]

    COVERAGE -- "incomplete" --> PLANNER
    COVERAGE -- "complete" --> FINALIZE

    FINALIZE --> End(["END"])
```

**Termination conditions:**
- All required views and specs collected (`complete`)
- Max iterations reached (`max_iterations_reached`)
- No new data collected since last check (`partial_complete`)
- Planner generates duplicate tasks (`partial_complete`)

## Project Structure

```
scrap_snaps/
├── .env.example              # Environment variable template
├── .gitignore
├── pyproject.toml            # Package config (hatchling build)
├── uv.lock                   # Reproducible dependency lock
├── pipeline.json             # Default batch pipeline config
│
├── src/
│   ├── __init__.py
│   ├── main.py               # CLI entry point (single query)
│   ├── llm.py                # Corporate Azure/OpenAI LLM client
│   ├── state.py              # ResearchState TypedDict definition
│   ├── graph.py              # Backward-compatible graph re-export
│   │
│   ├── config/               # Configuration package
│   │   ├── __init__.py       # Backward-compatible exports
│   │   ├── settings.py       # Pydantic Settings (flat env vars)
│   │   └── logging.py        # Structured logging (structlog)
│   │
│   ├── core/                 # Core infrastructure
│   │   ├── __init__.py
│   │   ├── graph.py          # LangGraph state machine builder
│   │   └── registry.py       # Plugin registry for nodes/tools/agents
│   │
│   ├── agents/               # Business logic classes
│   │   ├── __init__.py
│   │   ├── base.py           # BaseAgent with common utilities
│   │   ├── planner.py        # PlannerAgent (task generation + dedup)
│   │   ├── researcher.py     # ResearchAgent (discovery + evidence)
│   │   ├── media_collector.py# MediaAgent (images + videos + failure tracking)
│   │   ├── verifier.py       # VerificationAgent (scoring)
│   │   └── coverage.py       # CoverageAgent (gap analysis + no-progress detection)
│   │
│   ├── nodes/                # Thin LangGraph node wrappers
│   │   ├── __init__.py
│   │   ├── planner.py        # -> PlannerAgent
│   │   ├── discovery.py      # -> ResearchAgent
│   │   ├── evidence.py       # -> ResearchAgent
│   │   ├── media.py          # -> MediaAgent
│   │   ├── video_extract.py  # -> MediaAgent
│   │   ├── verification.py   # -> VerifierAgent
│   │   └── coverage.py       # -> CoverageAgent
│   │
│   ├── tools/                # Modular tool package
│   │   ├── __init__.py
│   │   ├── logging.py        # @log_tool_call decorator
│   │   ├── web/
│   │   │   ├── search.py     # search_web, search_images, search_videos (SerpAPI + cache)
│   │   │   ├── cache.py      # Per-run search result cache
│   │   │   ├── fetch.py      # fetch_page, fetch_page_js, extract_structured_data
│   │   │   └── robots.py     # check_robots
│   │   ├── media/
│   │   │   ├── images.py     # download_image, analyze_image, deduplicate_images
│   │   │   └── video.py      # download_video, extract_frames, select_best_frames
│   │   ├── db/
│   │   │   └── evidence.py   # save_evidence
│   │   └── utils/
│   │       ├── http.py       # rate_limit, can_fetch, http_get (smart retries)
│   │       └── hashing.py    # perceptual_hash, are_similar
│   │
│   ├── io/                   # Excel I/O and storage
│   │   ├── __init__.py
│   │   ├── naming.py         # File naming: row_{ROW}_{product}_{view}_{hash}.{ext}
│   │   ├── excel_reader.py   # Streaming openpyxl reader (read_only mode)
│   │   ├── excel_writer.py   # Streaming openpyxl writer
│   │   └── storage.py        # Storage abstraction (local + Azure Blob placeholder)
│   │
│   ├── pipeline/             # Batch processing orchestrator
│   │   ├── __init__.py
│   │   ├── runner.py         # PipelineRunner (batch orchestrator)
│   │   ├── checkpoint.py     # CheckpointManager for crash recovery
│   │   ├── results.py        # Result extraction from graph state
│   │   └── cli.py            # CLI entry point for batch mode
│   │
│   ├── db/                   # Database package
│   │   ├── __init__.py       # SQLAlchemy models + init_db()
│   │   └── utils.py          # save_result_to_db()
│   │
│   └── search/               # Focus-aware search
│       ├── __init__.py
│       ├── focus.py          # FocusArea enum, FocusConfig
│       ├── query_builder.py  # Focus-aware query generation
│       ├── filters.py        # Domain filtering, source scoring
│       └── focus_config.py   # Focus configuration helpers
│
└── tests/
    ├── __init__.py
    └── test_state.py
```

## Installation

```bash
# Clone the repository
git clone https://github.com/Purushothaman-natarajan/scrap_snaps.git
cd scrap_snaps

# Install with uv (recommended)
uv sync

# Or with pip
pip install -e .

# Install Playwright browser (for JS-rendered pages)
playwright install chromium

# Install ffmpeg (required for video frame extraction)
# Ubuntu/Debian: sudo apt install ffmpeg
# macOS: brew install ffmpeg
# Windows: choco install ffmpeg

# Set up environment variables
cp .env.example .env
# Edit .env and add your API keys
```

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and edit.

### Azure OpenAI (Corporate Gateway)

| Variable | Default | Description |
|----------|---------|-------------|
| `AZURE_ENDPOINT` | *(required)* | Corporate gateway URL |
| `AZURE_DEPLOYMENT` | *(required)* | Model deployment identifier |
| `AZURE_CONSUMER_ID` | *(required)* | Consumer ID for gateway auth |

### Execution

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///research.db` | SQLAlchemy database connection string |
| `MAX_ITERATIONS` | `30` | Maximum planner iterations before forced stop |
| `RECURSION_LIMIT` | `200` | LangGraph recursion limit |
| `REQUIRED_VIEWS` | `front,back,side,top` | Comma-separated image views to collect |
| `FOCUS_AREAS` | `product_pages,seller_images,youtube,specs` | Comma-separated focus areas |
| `COLLECT_SPECS` | `true` | Collect specifications from web pages |
| `COLLECT_MEDIA` | `both` | What media to collect: `images`, `videos`, or `both` |

### Networking

| Variable | Default | Description |
|----------|---------|-------------|
| `SERPAPI_KEY` | *(required)* | SerpAPI key for Google Search ([get one](https://serpapi.com/)) |
| `RATE_LIMIT_INTERVAL` | `1.0` | Minimum seconds between HTTP requests |
| `REQUEST_TIMEOUT` | `10.0` | HTTP request timeout in seconds |

### Scraping

| Variable | Default | Description |
|----------|---------|-------------|
| `DOWNLOAD_DIR` | `downloads` | Directory for downloaded images |
| `MAX_IMAGE_RESULTS` | `5` | Max images to fetch per search |
| `PAGE_TEXT_LIMIT` | `5000` | Max characters to extract from web pages |
| `MAX_DOWNLOAD_SIZE` | `10485760` | Max image file size in bytes (10MB) |

### Video

| Variable | Default | Description |
|----------|---------|-------------|
| `VIDEO_DOWNLOAD_DIR` | `downloads/videos` | Directory for downloaded videos |
| `MAX_VIDEO_RESULTS` | `2` | Number of YouTube videos to process (1-5) |
| `VIDEO_MIN_DURATION` | `180` | Min video duration in seconds |
| `VIDEO_MAX_DURATION` | `900` | Max video duration in seconds |
| `VIDEO_FRAME_INTERVAL` | `2.0` | Supplemental frame sampling interval (seconds) |
| `VIDEO_MAX_RESOLUTION` | `720` | Max video resolution to download |
| `AI_FRAME_SELECTION` | `true` | Use LLM Vision to select best frames |

### Search Cache

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARCH_CACHE_SIZE` | `500` | Max cached search results per run |

### Verification

| Variable | Default | Description |
|----------|---------|-------------|
| `VERIFY_WEIGHT_IDENTITY` | `0.30` | Weight for product identity confidence |
| `VERIFY_WEIGHT_EVIDENCE` | `0.25` | Weight for evidence confidence |
| `VERIFY_WEIGHT_IMAGE` | `0.30` | Weight for image confidence |
| `VERIFY_WEIGHT_BASE` | `0.15` | Base score added to all results |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_JSON` | `false` | Output logs as JSON (for production) |
| `LOG_CAPTURE` | `true` | Log all tool/node/agent I/O to file |
| `LOG_FILE` | `logs/scrap_snaps.log` | Path to log file |

## Usage

### Single Query Mode

```bash
# Basic usage
scrap-snaps "Sony WH-1000XM5"

# Focus on specific areas
scrap-snaps "iPhone 15 Pro" --focus product_pages,specs

# Collect specs only (no images/videos)
scrap-snaps "MacBook Pro M3" --collect-media none

# Collect images only (no spec extraction)
scrap-snaps "Samsung Galaxy S24" --no-collect-specs --collect-media images

# Or run as module
python -m src.main "Sony WH-1000XM5" --focus youtube
```

### Batch Pipeline Mode

```bash
# Process an Excel file with default settings
scrap-snaps-pipeline --input products.xlsx

# With custom settings
scrap-snaps-pipeline --input products.xlsx --batch-size 5 --collect-media images

# Use a config file
scrap-snaps-pipeline --config pipeline.json

# Resume interrupted run (uses checkpoint)
scrap-snaps-pipeline --input products.xlsx
```

#### pipeline.json

```json
{
  "input_file": "input.xlsx",
  "output_file": "results.xlsx",
  "sheet": null,
  "header_row": 1,
  "batch_size": 10,
  "collect_specs": true,
  "collect_media": "both",
  "focus_areas": "product_pages,seller_images",
  "max_iterations": 30,
  "storage_backend": "local",
  "storage_base_dir": "downloads",
  "skip_existing": true
}
```

## Tools

The agent uses 15 tools organized by domain:

| Tool | Module | Description |
|------|--------|-------------|
| `search_web` | `tools/web/search.py` | Google search via SerpAPI (cached per-run) |
| `search_images` | `tools/web/search.py` | Google image search via SerpAPI (cached) |
| `search_videos` | `tools/web/search.py` | YouTube search via SerpAPI (cached) |
| `fetch_page` | `tools/web/fetch.py` | Fetch static HTML pages with retry |
| `fetch_page_js` | `tools/web/fetch.py` | Fetch JS-rendered pages via Playwright |
| `extract_structured_data` | `tools/web/fetch.py` | Parse HTML tables, lists, metadata |
| `check_robots` | `tools/web/robots.py` | Check robots.txt compliance |
| `download_image` | `tools/media/images.py` | Download images with size validation and failure tracking |
| `analyze_image` | `tools/media/images.py` | Classify product image view type using LLM |
| `deduplicate_images` | `tools/media/images.py` | Perceptual hash (pHash) based deduplication |
| `download_video` | `tools/media/video.py` | Download YouTube videos via yt-dlp with failure tracking |
| `extract_frames` | `tools/media/video.py` | Extract key frames using scene detection |
| `select_best_frames` | `tools/media/video.py` | AI-assisted frame selection using LLM |
| `save_evidence` | `tools/db/evidence.py` | Persist extracted claims to the database |

## Database

SQLAlchemy models store all research results:

- **Product** — canonical product identity, query, confidence, status
- **Source** — web source URLs visited during research
- **Claim** — extracted specification claims with confidence scores
- **Image** — image URLs, local paths, view classifications
- **Video** — video URLs, local paths, durations, scores

Default: SQLite at `research.db`. Switch to PostgreSQL:

```
DATABASE_URL=postgresql://user:pass@localhost:5432/scrap_snaps
```

## Search Cache

Search results are cached in-memory for the duration of a run. This prevents:
- Retrying the same query when the planner re-discovers the same search terms
- Wasting SerpAPI quota on duplicate requests within a single graph execution

The cache is keyed on `(engine, query, num)` and cleared between runs. Set `SEARCH_CACHE_SIZE` to control max entries (default 500).

## Failure Tracking

The agent tracks permanently failed media URLs (HTTP 403, bot detection, etc.) to prevent infinite retry loops:

- **Image downloads** — 403/bot/captcha failures are tracked; the URL is never retried
- **Video downloads** — yt-dlp "sign in" / "blocked" failures are tracked
- **HTTP layer** — 4xx errors (except 429) are not retried; only transient errors (5xx, connection, timeout) get retries

Failed URLs are propagated through the state (`failed_media_urls`) so the planner knows not to schedule them again.

## Task Dedup

The planner uses LLM-based dedup to prevent generating identical tasks across iterations. Previous task fingerprints are tracked in state (`previous_task_fingerprints`). If the LLM determines new tasks are not meaningfully different from previous attempts, the graph terminates with `partial_complete` status.

## Developer Guide

### Quick Start

```python
from src.core.graph import build_graph
from src.search.focus import get_focus_config
from src.config import REQUIRED_VIEWS, MAX_ITERATIONS

graph = build_graph()
focus = get_focus_config("product_pages,seller_images")

initial_state = {
    "query": "Sony WH-1000XM5",
    "focus_areas": [a.value for a in focus.areas],
    "focus_config": focus.to_dict(),
    "collect_specs": True,
    "collect_media": "both",
    "product": {},
    "candidates": [],
    "search_queries": [],
    "searched_queries": [],
    "sources": [],
    "evidence": [],
    "specifications": {},
    "images": [],
    "videos": [],
    "required_views": REQUIRED_VIEWS,
    "discovered_views": {},
    "missing_views": REQUIRED_VIEWS.copy(),
    "tasks": [],
    "completed_tasks": [],
    "failed_tasks": [],
    "failed_media_urls": [],
    "previous_task_fingerprints": [],
    "iterations": 0,
    "max_iterations": MAX_ITERATIONS,
    "confidence": 0.0,
    "status": "started",
}

for event in graph.stream(initial_state, {"recursion_limit": 200}):
    for key, value in event.items():
        print(f"Finished: {key}")
```

### Configuration

Flat Pydantic Settings with env var binding:

```python
from src.config import settings, COLLECT_SPECS, COLLECT_MEDIA, SEARCH_CACHE_SIZE

print(settings.azure_endpoint)
print(COLLECT_SPECS)       # True
print(COLLECT_MEDIA)       # "both"
print(SEARCH_CACHE_SIZE)   # 500
```

### LLM Client

Corporate Azure gateway with custom auth headers:

```python
from src.llm import get_llm, get_vision_llm, clear_llm_cache

llm = get_llm(temperature=0.0)
vision_llm = get_vision_llm(temperature=0.0)
clear_llm_cache()  # For testing or config changes
```

### Testing & Linting

```bash
python -m pytest tests/ -v
python -m ruff check src/
python -m ruff format src/
```

## License

MIT
