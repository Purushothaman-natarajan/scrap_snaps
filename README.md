# scrap_snaps

Autonomous product research agent powered by LangGraph. Given a product query, it discovers the product, extracts technical specifications, collects images from multiple views, and builds a verified evidence dossier. Supports both single-query mode and batch processing from Excel files.

## Features

- **Autonomous research loop** — Planner → discover/collect/verify → coverage cycle with automatic termination
- **Focus-aware search** — Configurable focus areas (product pages, seller images, YouTube, specs)
- **Configurable collection** — 7 media modes: `images`, `videos`, `video_urls`, `video_frames`, `images_and_video_urls`, `both`, `none`
- **Custom view types** — `REQUIRED_VIEWS` is user-configurable; LLM prompts adapt dynamically. Includes standard angles (`front`, `back`, `left`, `right`, `top`) plus composite views (`360_strip`, `multi_angle_composite`)
- **Search caching** — In-memory cache with query normalization avoids redundant SerpAPI calls per run
- **Per-row API limiting** — `SERPAPI_MAX_HITS_PER_ROW` prevents SerpAPI quota burn
- **Failure tracking** — TTL-based `FailedURLTracker` (configurable `FAILED_URL_TTL`) shared across rows
- **Fingerprint dedup** — Deterministic task fingerprinting prevents planner loops
- **Multi-layer termination defense** — Auto-scaled recursion limit + coverage cycle limit + no-progress threshold + iteration proximity check
- **Batch pipeline** — Process millions of rows from Excel with checkpointing and crash recovery
- **Streaming I/O** — openpyxl read_only/write_only for large files
- **Structured database** — SQLAlchemy models for products, sources, claims, images, videos, and usage metrics
- **Usage tracking** — Per-run token counts (input/output), LLM calls, SerpAPI calls, and elapsed time
- **Cost optimization** — Batch `analyze_images_batch` (up to 5 images/call), pHash caching, shared DB engine, configurable JPEG quality and video resolution
- **Perceptual image dedup** — Fuzzy pHash matching with configurable Hamming distance threshold
- **Configurable everything** — ~50 settings via flat env vars; no hardcoded constants

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
- Coverage hard cycle limit reached (`partial_complete`)
- No new data collected since last check — threshold-based (`partial_complete`)
- Planner fingerprint repeats 2+ cycles (`partial_complete`)
- Iterations proximity check (≥80% of max) (`complete`)

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
| `collect_media` | `str` | `"images"`, `"videos"`, `"video_urls"`, `"video_frames"`, `"images_and_video_urls"`, `"both"`, or `None` |
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

- `_coverage_cycles` — count of coverage check cycles (terminates at `COVERAGE_MAX_CYCLES`, default 10)
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
│   │   ├── usage.py          # UsageTracker singleton (tokens, LLM calls, timing)
│   │   ├── web/
│   │   │   ├── search.py     # search_web, search_images, search_videos (SerpAPI + cache)
│   │   │   ├── cache.py      # Per-run search result cache with query normalization
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
│   │       └── failed_urls.py# FailedURLTracker with configurable TTL
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
│       └── filters.py        # Domain filtering, source scoring
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

# Set up credentials (required)
cp .env.example .env
# Edit .env and add your API keys

# All other settings are in config.yaml (edit as needed)
```

## Configuration

Configuration uses two files:

| File | Purpose | Committed to git? |
|------|---------|-------------------|
| `config.yaml` | **All settings** — execution, networking, scraping, media, search, logging, pipeline | Yes |
| `.env` | **Credentials only** — API keys, endpoints, database URL | No (gitignored) |

**Priority:** env vars > config.yaml > field defaults.

```
config.yaml          ← single source of truth for all non-credential settings
  .env               ← credentials only (AZURE_*, SERPAPI_KEY, DATABASE_URL)
```

### Azure OpenAI (Corporate Gateway) — .env only

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
| `REQUIRED_VIEWS` | `front,back,left,right,top,360_strip,multi_angle_composite` | Comma-separated image views to collect (custom views supported) |
| `FOCUS_AREAS` | `product_pages,seller_images,youtube,specs` | Comma-separated focus areas |
| `COLLECT_SPECS` | `true` | Collect specifications from web pages |
| `COLLECT_MEDIA` | `images_and_video_urls` | What media to collect (see below) |

**`COLLECT_MEDIA` options:**
- `images` — image search + download + classify only
- `videos` — full video pipeline (download → extract → classify → AI select)
- `video_urls` — YouTube search only, return URLs, no download
- `video_frames` — download + extract frames + classify, skip AI frame selection
- `images_and_video_urls` — images (full pipeline) + video URLs only (closest match)
- `both` — images + videos (full pipeline)
- `none` — no media collection, specs only

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
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser in headless mode |

### Image Extraction

| Variable | Default | Description |
|----------|---------|-------------|
| `IMAGE_BATCH_SIZE` | `5` | Max images per batch LLM call |
| `IMAGE_DOWNLOAD_LIMIT` | `2` | Max images to download per search result page |
| `IMAGE_CROP_RATIO` | `0.7` | Center crop ratio (0.5-1.0, lower = more aggressive) |
| `IMAGE_ANALYZE_CACHE_TTL` | `3600` | Image analysis cache TTL in seconds |
| `ANALYZE_CACHE_MAX_SIZE` | `1000` | Max entries in pHash analysis cache (LRU eviction) |

### Video Extraction

| Variable | Default | Description |
|----------|---------|-------------|
| `VIDEO_DOWNLOAD_DIR` | `downloads/videos` | Directory for downloaded videos |
| `MAX_VIDEO_RESULTS` | `2` | Number of YouTube videos to process (1-5) |
| `VIDEO_MIN_DURATION` | `180` | Min video duration in seconds |
| `VIDEO_MAX_DURATION` | `900` | Max video duration in seconds |
| `VIDEO_FRAME_INTERVAL` | `5.0` | Supplemental frame sampling interval (seconds) |
| `VIDEO_MAX_RESOLUTION` | `480` | Max video resolution to download |
| `CROP_VIDEO_FRAMES` | `false` | Crop video frames to center region |
| `AI_FRAME_SELECTION` | `true` | Use LLM Vision to select best frames |
| `VIDEO_SCENE_THRESHOLD` | `27.0` | Scene detection sensitivity (lower = more scenes) |
| `VIDEO_FRAME_JPEG_QUALITY` | `85` | JPEG quality of extracted frames (1-100) |
| `VIDEO_MAX_FRAMES_PER_VIEW` | `2` | Max frames selected per view angle |
| `VIDEO_AI_SELECTION_MAX_FRAMES` | `12` | Max frames sent to LLM Vision for AI selection |

### Perceptual Hashing

| Variable | Default | Description |
|----------|---------|-------------|
| `PHASH_SIMILARITY_THRESHOLD` | `10` | Hamming distance threshold for fuzzy dedup (lower = stricter) |

### Coverage / Termination

| Variable | Default | Description |
|----------|---------|-------------|
| `COVERAGE_MAX_CYCLES` | `10` | Hard limit on coverage cycles before forced termination |
| `COVERAGE_NO_PROGRESS_THRESHOLD` | `1` | Items added to be considered "no progress" |
| `COVERAGE_PROXIMITY_RATIO` | `0.8` | When to force-complete based on iteration proximity |

### Search Query Building

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARCH_DOMAINS_PER_AREA` | `2` | Domains to include in site-scoped searches |
| `SEARCH_MODIFIERS_PER_AREA` | `2` | Query modifiers per focus area |
| `SEARCH_QUERIES_PER_TASK` | `2` | Search queries generated per task |

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
# Process an Excel file (reads pipeline settings from config.yaml)
scrap-snaps-pipeline --input products.xlsx

# Override settings from config.yaml via CLI flags
scrap-snaps-pipeline --input products.xlsx --batch-size 5 --collect-media images

# Use a legacy JSON config file
scrap-snaps-pipeline --config pipeline.json --input products.xlsx

# Resume interrupted run (uses checkpoint)
scrap-snaps-pipeline --input products.xlsx
```

### Config File (config.yaml)

All non-credential settings live in `config.yaml`. Credentials stay in `.env`:

```yaml
# config.yaml
execution:
  max_iterations: 15
  required_views: [front, back, left, right, top, 360_strip, multi_angle_composite]

focus:
  areas: [product_pages, seller_images, youtube, specs]
  collect_specs: true
  collect_media: images_and_video_urls  # images | videos | video_urls | video_frames | images_and_video_urls | both | none

# ... networking, scraping, image, video, search, logging, pipeline sections

pipeline:
  input_file: input.xlsx
  output_file: results.xlsx
  batch_size: 10
```

Override any YAML setting with an env var:

```bash
MAX_ITERATIONS=20 scrap-snaps "Sony WH-1000XM5"
COLLECT_MEDIA=images scrap-snaps-pipeline --input products.xlsx
```

Set a custom config path:

```bash
SCRAP_SNAPS_CONFIG=my_config.yaml scrap-snaps "Sony WH-1000XM5"
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
- **RunMetric** — per-run usage metrics (tokens, LLM calls, SerpAPI calls, elapsed time)

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
2. **Coverage agent** — hard cycle limit (`COVERAGE_MAX_CYCLES`, default 10), threshold no-progress (`COVERAGE_NO_PROGRESS_THRESHOLD`, default ≤1 new item), iterations proximity (`COVERAGE_PROXIMITY_RATIO`, default ≥80% of max)
3. **Planner fingerprint dedup** — if the planner generates identical tasks 2+ cycles in a row, terminates with `partial_complete`

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
from src.state import create_initial_state
from src.tools.usage import get_usage_tracker
from src.tools.web.cache import get_search_cache

graph = build_graph()
focus = get_focus_config("product_pages,seller_images")

# Clear cache and tracker for this run
get_search_cache().clear()
tracker = get_usage_tracker()
tracker.reset()
tracker.start()

initial_state = create_initial_state(
    query="Sony WH-1000XM5",
    focus_areas=[a.value for a in focus.areas],
    focus_config=focus.to_dict(),
    collect_specs=True,
    collect_media="both",
    max_iterations=15,
)

for event in graph.stream(initial_state, {"recursion_limit": 200}):
    for key, value in event.items():
        print(f"Finished: {key}")

# Get usage stats
usage = tracker.get_stats(search_cache_stats=get_search_cache().stats)
print(f"Tokens: {usage['input_tokens']} in / {usage['output_tokens']} out")
```

### Configuration

Settings are loaded from `config.yaml` (non-credential) + `.env` (credentials):

```python
from src.config import settings, COLLECT_SPECS, COLLECT_MEDIA, SEARCH_CACHE_SIZE

print(settings.azure_endpoint)  # from .env
print(COLLECT_SPECS)            # True (from config.yaml)
print(COLLECT_MEDIA)            # "both" (from config.yaml)
print(SEARCH_CACHE_SIZE)        # 500 (from config.yaml)
```

Pipeline config from the `pipeline:` section of config.yaml:

```python
from src.pipeline.runner import PipelineConfig

config = PipelineConfig.from_yaml("config.yaml")
print(config.input_file)    # "input.xlsx"
print(config.batch_size)    # 10
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
