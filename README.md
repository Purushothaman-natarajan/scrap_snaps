# scrap_snaps

Autonomous product research agent powered by LangGraph. Given a product query, it discovers the product, extracts technical specifications, collects images from multiple views, and builds a verified evidence dossier. Supports both single-query mode and batch processing from Excel files.

> 📚 **Developer Guide:** [`docs/DEVELOPER_GUIDE.md`](docs/DEVELOPER_GUIDE.md) — architecture, state/graph, agents, pipeline, DB, config, extending, debugging, security.

## Key Features

- **Autonomous research loop** — Planner → discover/collect/verify → coverage cycle with automatic termination
- **Focus-aware search** — Configurable focus areas (product pages, seller images, YouTube, specs)
- **Custom view types** — `REQUIRED_VIEWS` is user-configurable; LLM prompts adapt dynamically
- **Search caching** — In-memory cache with query normalization avoids redundant SerpAPI calls per run
- **Perceptual image dedup** — Fuzzy pHash matching with configurable Hamming distance threshold
- **Fingerprint dedup** — Deterministic task fingerprinting prevents planner loops
- **Multi-layer termination defense** — Recursion limit + coverage cycle limit + no-progress threshold + iteration proximity check
- **Batch pipeline** — Process millions of rows from Excel with checkpointing and crash recovery
- **Structured database** — SQLAlchemy models for products, sources, claims, images, videos, and usage metrics
- **Usage tracking** — Per-run token counts (input/output), LLM calls, SerpAPI calls, and elapsed time
- **Cost optimization** — Batch `analyze_images_batch` (up to 5 images/call), pHash caching, shared DB engine
- **Configurable everything** — ~50 settings via flat env vars or config.yaml; no hardcoded constants

## Quick Start

```bash
git clone https://github.com/Purushothaman-natarajan/scrap_snaps.git
cd scrap_snaps && uv sync && playwright install chromium
cp .env.example .env  # add your API keys
scrap-snaps "Sony WH-1000XM5"
```

## Architecture

### System Context

```mermaid
flowchart LR
    subgraph Input
        CLI["CLI Query"]
        Excel["Excel Batch"]
    end
    
    subgraph "scrap-snaps"
        Agent["Research Agent"]
        Pipeline["Batch Pipeline"]
    end
    
    subgraph External
        SerpAPI["SerpAPI\n(Google Search)"]
        LLM["Azure LLM\n(GPT-4 Vision)"]
        Web["HTTP / Playwright\n(Web Pages)"]
        YT["YouTube\n(yt-dlp)"]
        FS["Filesystem\n(Images/Videos)"]
    end
    
    subgraph Output
        JSON["JSON Result"]
        ExcelOut["Excel Output"]
        DB["SQLite / PostgreSQL"]
    end
    
    CLI --> Agent
    Excel --> Pipeline
    Pipeline --> Agent
    Agent --> SerpAPI
    Agent --> LLM
    Agent --> Web
    Agent --> YT
    Agent --> FS
    Agent --> JSON
    Pipeline --> ExcelOut
    Pipeline --> DB
    Agent --> DB
```

### Data Flow

```mermaid
flowchart TD
    subgraph "State"
        S["ResearchState\n(TypedDict)"]
    end
    
    subgraph "Planner"
        P["planner.py\nLLM → tasks"]
    end
    
    subgraph "Workers"
        D["discover\nsearch_web → candidates"]
        EV["evidence\nsearch_web+fetch → specs"]
        M["media\nsearch_images → images"]
        V["video_extract\nsearch_videos → frames"]
    end
    
    subgraph "Assessment"
        VF["verify\nweighted scoring"]
        C["coverage\ngap analysis"]
    end
    
    S -->|"iterations, missing_views,\nprevious_task_fingerprints"| P
    P -->|"tasks"| D & EV & M & V
    D -->|"product, sources,\ncandidates"| S
    EV -->|"evidence,\nspecifications"| S
    M -->|"images,\ndiscovered_views"| S
    V -->|"images, videos,\ndiscovered_views"| S
    S -->|"evidence, images,\nproduct.confidence"| VF
    VF -->|"confidence"| S
    S -->|"discovered_views,\nspecifications, iterations"| C
    C -->|"missing_views,\nstatus → complete/incomplete"| S
    C -.->|"incomplete"| P
    C -.->|"complete"| FIN["finalize"]
    
    P -.->|"LLM API"| LLM["Azure LLM"]
    D -.->|"SerpAPI"| API["SerpAPI"]
    EV -.->|"SerpAPI + HTTP"| API & WEB["Web"]
    M -.->|"SerpAPI + HTTP"| API & WEB
    V -.->|"SerpAPI + yt-dlp"| API & YT["YouTube"]
    M & V -.->|"LLM Vision"| LLM
    M & V -.->|"downloads/"| FS["Filesystem"]
    FIN -.->|"save_result_to_db()"| DB["Database"]
```

### Graph Topology

```mermaid
flowchart TD
    Start(["START"]) --> PLANNER["Planner"]

    PLANNER -- "discover" --> DISCOVER["Discovery\nsearch_web → extract candidates"]
    PLANNER -- "verify_spec" --> EVIDENCE["Evidence\nsearch_web → fetch_page → extract specs"]
    PLANNER -- "find_images" --> MEDIA["Media\nsearch_images → download → classify"]
    PLANNER -- "find_videos" --> VIDEO["Video\nsearch_videos → download → extract frames"]
    PLANNER -- "no tasks" --> FINALIZE["Finalize"]

    DISCOVER --> VERIFY
    EVIDENCE --> VERIFY
    MEDIA --> VERIFY
    VIDEO --> VERIFY

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

### State Management

All state flows through a single `ResearchState` TypedDict. Understanding this state is key to extending the system.

#### ResearchState Fields

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

#### State Flow

1. **Initial state** — CLI/pipeline builds initial state dict
2. **Planner** — reads `product`, `missing_views`, `iterations`, `previous_task_fingerprints` → writes `tasks`
3. **Workers** — read `tasks[0]` → execute → write `product`, `images`, `evidence`, `sources`, etc.
4. **Verify** — reads all data → writes `confidence`, `status`
5. **Coverage** — reads `confidence`, `discovered_views`, `iterations` → routes back to planner or finalize

#### Internal State Fields

Fields prefixed with `_` are runtime-only and not serialized:

- `_coverage_cycles` — count of coverage check cycles (terminates at `COVERAGE_MAX_CYCLES`, default 10)
- `_prev_images` — previous cycle's image count (no-progress detection)
- `_prev_specs` — previous cycle's spec count
- `_prev_views_count` — previous cycle's discovered views count

## Configuration

Configuration uses two files:

| File | Purpose | Committed to git? |
|------|---------|-------------------|
| `config.yaml` | **All settings** — execution, networking, scraping, media, search, logging, pipeline | Yes |
| `.env` | **Credentials only** — API keys, endpoints, database URL | No (gitignored) |

**Priority:** env vars > config.yaml > field defaults.

### Azure OpenAI (.env only)

| Variable | Default | Description |
|----------|---------|-------------|
| `AZURE_ENDPOINT` | *(required)* | Corporate gateway URL |
| `AZURE_DEPLOYMENT` | *(required)* | Model deployment identifier |
| `AZURE_CONSUMER_ID` | *(required)* | Consumer ID for gateway auth |

<details>
<summary>Full Configuration Reference (click to expand)</summary>

#### Execution

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

#### Networking

| Variable | Default | Description |
|----------|---------|-------------|
| `SERPAPI_KEY` | *(required)* | SerpAPI key for Google Search ([get one](https://serpapi.com/)) |
| `RATE_LIMIT_INTERVAL` | `1.0` | Minimum seconds between HTTP requests |
| `REQUEST_TIMEOUT` | `10.0` | HTTP request timeout in seconds |

#### Scraping

| Variable | Default | Description |
|----------|---------|-------------|
| `DOWNLOAD_DIR` | `downloads` | Directory for downloaded images |
| `MAX_IMAGE_RESULTS` | `5` | Max images to fetch per search |
| `PAGE_TEXT_LIMIT` | `5000` | Max characters to extract from web pages |
| `MAX_DOWNLOAD_SIZE` | `10485760` | Max image file size in bytes (10MB) |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser in headless mode |

#### Image Extraction

| Variable | Default | Description |
|----------|---------|-------------|
| `IMAGE_BATCH_SIZE` | `5` | Max images per batch LLM call |
| `IMAGE_DOWNLOAD_LIMIT` | `2` | Max images to download per search result page |
| `IMAGE_CROP_RATIO` | `0.7` | Center crop ratio (0.5-1.0, lower = more aggressive) |
| `IMAGE_ANALYZE_CACHE_TTL` | `3600` | Image analysis cache TTL in seconds |
| `ANALYZE_CACHE_MAX_SIZE` | `1000` | Max entries in pHash analysis cache (LRU eviction) |

#### Video Extraction

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

#### Perceptual Hashing

| Variable | Default | Description |
|----------|---------|-------------|
| `PHASH_SIMILARITY_THRESHOLD` | `10` | Hamming distance threshold for fuzzy dedup (lower = stricter) |

#### Coverage / Termination

| Variable | Default | Description |
|----------|---------|-------------|
| `COVERAGE_MAX_CYCLES` | `10` | Hard limit on coverage cycles before forced termination |
| `COVERAGE_NO_PROGRESS_THRESHOLD` | `1` | Items added to be considered "no progress" |
| `COVERAGE_PROXIMITY_RATIO` | `0.8` | When to force-complete based on iteration proximity |

#### Search Query Building

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARCH_DOMAINS_PER_AREA` | `2` | Domains to include in site-scoped searches |
| `SEARCH_MODIFIERS_PER_AREA` | `2` | Query modifiers per focus area |
| `SEARCH_QUERIES_PER_TASK` | `2` | Search queries generated per task |

#### Search Cache

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARCH_CACHE_SIZE` | `500` | Max cached search results per run |
| `SERPAPI_MAX_HITS_PER_ROW` | `20` | Max SerpAPI calls allowed per row/query |

#### Failed URL Tracking

| Variable | Default | Description |
|----------|---------|-------------|
| `FAILED_URL_TTL` | `300` | Seconds before a failed URL is eligible for retry (default 5 min) |

#### Verification

| Variable | Default | Description |
|----------|---------|-------------|
| `VERIFY_WEIGHT_IDENTITY` | `0.30` | Weight for product identity confidence |
| `VERIFY_WEIGHT_EVIDENCE` | `0.25` | Weight for evidence confidence |
| `VERIFY_WEIGHT_IMAGE` | `0.30` | Weight for image confidence |
| `VERIFY_WEIGHT_BASE` | `0.15` | Base score added to all results |

#### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `LOG_JSON` | `false` | Output logs as JSON (for production) |
| `LOG_CAPTURE` | `true` | Log all tool/node/agent I/O to file |
| `LOG_FILE` | `logs/scrap_snaps.log` | Path to log file |

</details>

### Overriding Settings

Override any YAML setting with an env var:

```bash
MAX_ITERATIONS=20 scrap-snaps "Sony WH-1000XM5"
COLLECT_MEDIA=images scrap-snaps-pipeline --input products.xlsx
```

Set a custom config path:

```bash
SCRAP_SNAPS_CONFIG=my_config.yaml scrap-snaps "Sony WH-1000XM5"
```

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

## Output Format

Single query mode returns JSON with this structure:

```json
{
  "status": "done | partial_complete | failed",
  "product_name": "Sony WH-1000XM5",
  "confidence": 0.85,
  "specifications": {"weight": "250g", "battery": "30h"},
  "images": [{"url": "...", "local_path": "...", "view": "front", "confidence": 0.95}],
  "videos": [{"url": "...", "title": "...", "duration": 300}],
  "missing_views": ["360_strip"],
  "usage_metrics": {"input_tokens": 12000, "llm_calls": 8, "serpapi_calls": 12}
}
```

| Field | Description |
|-------|-------------|
| `status` | `done` (all views+specs collected), `partial_complete` (hit limits), `failed` (error) |
| `product_name` | Canonical product name from discovery |
| `confidence` | Overall score 0.0–1.0 from verification |
| `specifications` | Key-value pairs extracted from web pages |
| `images` | Array of `{url, local_path, view, confidence}` |
| `videos` | Array of `{url, title, duration}` |
| `missing_views` | Views not found after all iterations |
| `usage_metrics` | Token counts, LLM calls, SerpAPI calls |

## Extending the Agent

### Adding a New Tool

```python
from langchain_core.tools import tool
from src.tools.logging import log_tool_call

@tool
@log_tool_call
def my_new_tool(param: str) -> dict:
    """Tool description for the LLM."""
    return {"result": "data"}
```

Then import it in the appropriate agent and add the task type to `src/agents/planner.py`.

### Adding a New Focus Area

1. Add the enum value to `src/search/focus.py`
2. Add domain mappings in `FocusConfig`
3. Add query templates in `src/search/query_builder.py`

### Adding a New Agent

```python
from src.agents.base import BaseAgent

class MyAgent(BaseAgent):
    def execute(self, state: dict) -> dict:
        task = state.get("tasks", [{}])[0]
        result = do_something(task["target"])
        return {"my_field": result}
```

Register it in `src/core/graph.py` with `graph.add_node("my_node", my_node)`.

### Adding a New Database Model

1. Define the model in `src/db/__init__.py` with `Base` and `Product` relationship
2. Add `save_to_my_model()` utility in `src/db/utils.py`

## Developer Reference

### Tools

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
| `download_video` | `tools/media/video.py` | Download YouTube videos via yt-dlp |
| `extract_frames` | `tools/media/video.py` | Extract key frames using scene detection |
| `select_best_frames` | `tools/media/video.py` | AI-assisted frame selection using LLM |
| `save_evidence` | `tools/db/evidence.py` | Persist extracted claims to the database |

### Database Models

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

### Cost Optimization

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

### Testing & Linting

```bash
python -m pytest tests/ -v
python -m ruff check src/
python -m ruff format src/
```

## License

MIT
