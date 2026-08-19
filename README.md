# scrap_snaps

Autonomous product research agent powered by LangGraph. Given a product query, it discovers the product, extracts technical specifications, collects images from multiple views, and builds a verified evidence dossier. Supports both single-query mode and batch processing from Excel files.

## Features

- **Autonomous research loop** — Planner, discover, verify, coverage cycle with automatic termination
- **Focus-aware search** — Configurable focus areas (product pages, seller images, YouTube, specs)
- **Configurable collection** — Collect specs only, media only, or both
- **Search caching** — In-memory cache avoids redundant SerpAPI calls within a run
- **Failure tracking** — 403/bot-detection failures are tracked with TTL-based retry
- **Fingerprint dedup** — Deterministic task fingerprinting prevents planner loops
- **Batch pipeline** — Process millions of rows from Excel with checkpointing
- **Streaming I/O** — openpyxl read_only/write_only for large files
- **Structured database** — SQLAlchemy models for products, sources, claims, images, videos
- **Cost optimization** — Batch image analysis, pHash caching, shared DB engine

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
- Planner fingerprint repeats 3+ cycles (`partial_complete`)

## State Management

All state flows through a single `ResearchState` TypedDict. Understanding this state is key to extending the system.

### ResearchState Fields

| Field | Type | Description |
|-------|------|-------------|
| `query` | `str` | Original product query |
| `__row_index` | `int` | Row number (batch mode) or 0 (single query) |
| `focus_areas` | `list[str]` | Active focus area values |
| `focus_config` | `dict` | FocusConfig serialized |
| `collect_specs` | `bool` | Whether to extract specifications |
| `collect_media` | `str` | `"images"`, `"videos"`, or `"both"` |
| `product` | `dict` | Canonical product identity (name, brand, mpn, model) |
| `candidates` | `list[dict]` | Product candidates from discovery |
| `search_queries` | `list[str]` | Generated search queries |
| `searched_queries` | `list[str]` | Queries already executed (dedup) |
| `sources` | `list[dict]` | Visited URLs with content |
| `evidence` | `list[dict]` | Extracted specification claims |
| `specifications` | `dict` | Merged specifications |
| `images` | `list[dict]` | Downloaded images with view classifications |
| `videos` | `list[dict]` | Downloaded videos with metadata |
| `required_views` | `list[str]` | Views to collect (from `REQUIRED_VIEWS`) |
| `discovered_views` | `dict[str, list[str]]` | View type -> list of local paths |
| `missing_views` | `list[str]` | Views still needed |
| `tasks` | `list[dict]` | Current task queue |
| `completed_tasks` | `list[dict]` | Finished tasks |
| `failed_tasks` | `list[dict]` | Failed tasks |
| `failed_media_urls` | `list[str]` | Permanently failed URLs (never retried) |
| `previous_task_fingerprints` | `list[str]` | Fingerprint history for dedup |
| `iterations` | `int` | Current planner iteration count |
| `max_iterations` | `int` | Iteration limit |
| `confidence` | `float` | Overall verification confidence |
| `status` | `str` | `started`, `complete`, `partial_complete`, `failed` |

### State Flow

1. **Initial state** — CLI/pipeline builds initial state dict
2. **Planner** — reads `product`, `missing_views`, `iterations`, `previous_task_fingerprints` → writes `tasks`
3. **Workers** — read `tasks[0]` → execute → write `product`, `images`, `evidence`, `sources`, etc.
4. **Verify** — reads all data → writes `confidence`, `status`
5. **Coverage** — reads `confidence`, `discovered_views`, `iterations` → routes back to planner or finalize

### Internal State Fields

Fields prefixed with `_` are runtime-only and not serialized:

- `_coverage_cycles` — count of coverage check cycles (terminates at 10)
- `_prev_images` — previous cycle's image count (no-progress detection)
- `_prev_specs` — previous cycle's spec count
- `_prev_views_count` — previous cycle's discovered views count

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
│   │   ├── planner.py        # PlannerAgent (task generation + fingerprint dedup)
│   │   ├── researcher.py     # ResearchAgent (discovery + evidence)
│   │   ├── media_collector.py# MediaAgent (images + videos + failure tracking)
│   │   ├── verifier.py       # VerificationAgent (scoring)
│   │   └── coverage.py       # CoverageAgent (gap analysis + termination defense)
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
│   │   │   ├── images.py     # download_image, analyze_image(s_batch), deduplicate_images
│   │   │   └── video.py      # download_video, extract_frames, select_best_frames
│   │   ├── db/
│   │   │   └── evidence.py   # save_evidence
│   │   └── utils/
│   │       ├── http.py       # rate_limit, can_fetch, http_get (smart retries)
│   │       ├── hashing.py    # PHashCache, perceptual_hash, are_hashes_similar
│   │       └── failed_urls.py# FailedURLTracker with TTL
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
│   │   ├── runner.py         # PipelineRunner (batch orchestrator, shared DB engine)
│   │   ├── checkpoint.py     # CheckpointManager for crash recovery
│   │   ├── results.py        # Result extraction from graph state
│   │   └── cli.py            # CLI entry point for batch mode
│   │
│   ├── db/                   # Database package
│   │   ├── __init__.py       # SQLAlchemy models + init_db() + get_engine()
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
| `MAX_ITERATIONS` | `15` | Maximum planner iterations before forced stop |
| `RECURSION_LIMIT` | `200` | LangGraph recursion limit (auto-scaled to `max(MAX_ITERATIONS*8, this)`) |
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
| `VIDEO_FRAME_INTERVAL` | `5.0` | Supplemental frame sampling interval (seconds) |
| `VIDEO_MAX_RESOLUTION` | `480` | Max video resolution to download |
| `CROP_VIDEO_FRAMES` | `false` | Crop video frames to center 70% of image |
| `AI_FRAME_SELECTION` | `true` | Use LLM Vision to select best frames |

### Search Cache

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARCH_CACHE_SIZE` | `500` | Max cached search results per run |
| `SERPAPI_MAX_HITS_PER_ROW` | `20` | Max SerpAPI calls allowed per row/query |

### Failed URL Tracking

| Variable | Default | Description |
|----------|---------|-------------|
| `FAILED_URL_TTL` | `300` | Seconds before a failed URL is eligible for retry (default 5 min) |

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

# With custom output file
scrap-snaps "Sony WH-1000XM5" --output results/sony.json
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
  "max_iterations": 15,
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
| `download_image` | `tools/media/images.py` | Download images with failure tracking |
| `analyze_image` | `tools/media/images.py` | Classify product image view type using LLM |
| `analyze_images_batch` | `tools/media/images.py` | Batch analyze up to 5 images per LLM call |
| `deduplicate_images` | `tools/media/images.py` | Fuzzy pHash dedup (Hamming distance ≤10) |
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

The cache is keyed on `(engine, normalized_query, num)` with query normalization (lowercase, strip, sorted words). Set `SEARCH_CACHE_SIZE` to control max entries (default 500). Set `SERPAPI_MAX_HITS_PER_ROW` to limit per-row API calls (default 20).

## Failure Tracking

Failed media URLs are tracked with a TTL-based system:

- **Image downloads** — 403/bot/captcha failures are tracked; URL is not retried until TTL expires (default 5 min)
- **Video downloads** — yt-dlp "sign in" / "blocked" failures are tracked
- **HTTP layer** — 4xx errors (except 429) are not retried; only transient errors (5xx, connection, timeout) get retries
- **Shared singleton** — `FailedURLTracker` is shared across all rows in a pipeline run; TTL-based expiry allows retry after cooldown

Failed URLs are propagated through the state (`failed_media_urls`) so the planner knows not to schedule them again.

## Termination Defense

The agent has a 3-layer defense against infinite loops:

1. **Auto-scaled recursion limit** — `recursion_limit` is automatically set to `max(RECURSION_LIMIT, MAX_ITERATIONS * 8)` to ensure the graph has enough headroom
2. **Coverage agent** — hard cycle limit (10), threshold no-progress (≤1 new item), iterations proximity (≥80% of max)
3. **Planner fingerprint dedup** — if the planner generates identical tasks 3+ cycles in a row, terminates with `partial_complete`

## Extending the Agent

### Adding a New Tool

1. Create a function in the appropriate `src/tools/` module:

```python
from langchain_core.tools import tool
from src.tools.logging import log_tool_call

@tool
@log_tool_call
def my_new_tool(param: str) -> dict:
    """Tool description for the LLM."""
    # Implementation
    return {"result": "data"}
```

2. Import and use it in an agent or node. For the planner, add it to the task types:

```python
# In src/agents/planner.py, add a new task type
elif task_type == "my_new_task":
    # Handle new task
    pass
```

3. Add the task to the coverage check if it produces data:

```python
# In src/agents/coverage.py, check for the new data type
new_items = len(new_data) - prev_data_count
```

### Adding a New Focus Area

1. Add the enum value to `src/search/focus.py`:

```python
class FocusArea(str, Enum):
    NEW_AREA = "new_area"
```

2. Add domain mappings in `FocusConfig`:

```python
FOCUS_DOMAINS = {
    FocusArea.NEW_AREA: ["example.com", "other.com"],
}
```

3. Add query templates in `src/search/query_builder.py`:

```python
elif FocusArea.NEW_AREA in areas:
    queries.append(f"{query} site:example.com")
```

### Adding a New Agent

1. Create `src/agents/my_agent.py`:

```python
from src.agents.base import BaseAgent

class MyAgent(BaseAgent):
    def execute(self, state: dict) -> dict:
        # Read from state
        task = state.get("tasks", [{}])[0]

        # Do work
        result = do_something(task["target"])

        # Return state updates
        return {"my_field": result}
```

2. Create `src/nodes/my_node.py`:

```python
from src.agents.my_agent import MyAgent

def my_node(state: dict) -> dict:
    agent = MyAgent()
    return agent.execute(state)
```

3. Register in `src/core/graph.py`:

```python
from src.nodes.my_node import my_node

# In build_graph():
graph.add_node("my_node", my_node)
```

### Adding a New Database Model

1. Add to `src/db/__init__.py`:

```python
class MyModel(Base):
    __tablename__ = "my_table"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    my_field = Column(String(500), default="")
```

2. Add relationship to `Product`:

```python
product = relationship("Product", back_populates="my_models")
```

3. Add `save_to_my_model()` utility in `src/db/utils.py`.

### Adding a New Pipeline Output Format

1. Create `src/io/my_format.py`:

```python
def write_my_format(output_path: str, results: list[dict]) -> None:
    # Write results in your format
    pass
```

2. Register in `src/pipeline/cli.py`:

```python
if args.format == "my_format":
    from src.io.my_format import write_my_format
    write_my_format(args.output, results)
```

## Cost Optimization

The agent includes several cost optimization strategies:

| Optimization | Impact | Implementation |
|-------------|--------|----------------|
| Batch `analyze_images_batch` | ~4-5x fewer LLM calls | Up to 5 images per LLM call in `tools/media/images.py` |
| pHash result caching | Avoids re-analyzing same images | 1-hour TTL cache keyed on perceptual hash |
| Fingerprint-only dedup | Eliminates LLM dedup calls | Deterministic fingerprint comparison in planner |
| Search result caching | Prevents redundant SerpAPI calls | In-memory cache with query normalization |
| Failed URL TTL | Prevents wasted retry attempts | 5-minute cooldown before retry |
| Lower video resolution | Fewer bandwidth + processing | 480p default (configurable) |
| Wider frame intervals | Fewer frames to analyze | 5s default (configurable) |
| Lower JPEG quality | Smaller files, faster I/O | Quality 85 (configurable) |
| Shared DB engine | Fewer connection overhead | Engine created once per pipeline run |

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
