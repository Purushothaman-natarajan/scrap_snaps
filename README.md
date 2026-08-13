# scrap_snaps

Autonomous product research agent powered by LangGraph. Given a product query, it discovers the product, extracts technical specifications, collects images from multiple views, and builds a verified evidence dossier.

## Architecture

The agent is a LangGraph state machine with 8 nodes:

```
                         ┌──────────┐
                         │  START   │
                         └────┬─────┘
                              │
                         ┌────▼─────┐
                    ┌────│ PLANNER  │────┐────────┐
                    │    └──────────┘    │        │
                    │                    │        │
             ┌──────▼──────┐   ┌────────▼──┐  ┌──▼──────────┐
             │  DISCOVER   │   │  evidence  │  │ video_extract│
             └──────┬──────┘   └─────┬─────┘  └──────┬───────┘
                    │                │                │
             ┌──────▼──────┐        │                │
             │   (media)   │────────┘                │
             └──────┬──────┘                         │
                    └───────────────┬────────────────┘
                                    │
                               ┌────▼─────┐
                               │  VERIFY  │
                               └────┬─────┘
                                    │
                               ┌────▼──────┐
                               │ COVERAGE  │── complete ──► FINALIZE ──► END
                               └────┬──────┘
                                    │
                               more_research
                                    │
                               ┌────▼─────┐
                               │ PLANNER  │ (loop back)
                               └──────────┘
```

**Flow:** Planner generates tasks → Discovery/Evidence/Media/VideoExtract executes them → Verification scores quality → Coverage checks gaps → Planner decides next steps or finalizes.

## Installation

```bash
# Clone the repository
git clone https://github.com/Purushothaman-natarajan/scrap_snaps.git
cd scrap_snaps

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -e .

# Install Playwright browser (for JS-rendered pages)
playwright install chromium

# Install ffmpeg (required for video frame extraction)
# Ubuntu/Debian: sudo apt install ffmpeg
# macOS: brew install ffmpeg
# Windows: choco install ffmpeg

# Set up environment variables
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

## Usage

```bash
# Run with default query (Sony WH-1000XM5)
python -m src.main

# Run with a custom query
python -m src.main "iPhone 15 Pro Max"

# Run with a specific product
python -m src.main "Samsung Galaxy S24 Ultra"
```

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and edit.

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_API_KEY` | *(required)* | Google Gemini API key for LLM calls |
| `DATABASE_URL` | `sqlite:///research.db` | SQLAlchemy database connection string |
| `LLM_MODEL` | `gemini-1.5-pro-latest` | Gemini model to use for text and vision |
| `MAX_ITERATIONS` | `30` | Maximum planner iterations before forced stop |
| `RECURSION_LIMIT` | `50` | LangGraph recursion limit |
| `REQUIRED_VIEWS` | `front,back,side,top` | Comma-separated image views to collect |
| `DOWNLOAD_DIR` | `downloads` | Directory for downloaded images |
| `RATE_LIMIT_INTERVAL` | `1.0` | Minimum seconds between HTTP requests |
| `REQUEST_TIMEOUT` | `10.0` | HTTP request timeout in seconds |
| `USER_AGENT` | *(Chrome UA)* | User-Agent header for HTTP requests |
| `PLAYWRIGHT_NAV_TIMEOUT` | `30000` | Playwright page navigation timeout (ms) |
| `PLAYWRIGHT_SELECTOR_TIMEOUT` | `10000` | Playwright element wait timeout (ms) |
| `MAX_IMAGE_RESULTS` | `5` | Max images to fetch per search |
| `PAGE_TEXT_LIMIT` | `5000` | Max characters to extract from web pages |
| `MAX_DOWNLOAD_SIZE` | `10485760` | Max image file size in bytes (10MB) |
| `VIDEO_DOWNLOAD_DIR` | `downloads/videos` | Directory for downloaded videos |
| `MAX_VIDEO_RESULTS` | `2` | Number of YouTube videos to process (1-5) |
| `VIDEO_MIN_DURATION` | `180` | Min video duration in seconds (skip shorts) |
| `VIDEO_MAX_DURATION` | `900` | Max video duration in seconds (skip compilations) |
| `VIDEO_FRAME_INTERVAL` | `2.0` | Supplemental frame sampling interval (seconds) |
| `VIDEO_MAX_RESOLUTION` | `720` | Max video resolution to download (480/720/1080) |
| `AI_FRAME_SELECTION` | `true` | Use Gemini Vision for best frame selection |
| `VERIFY_WEIGHT_IDENTITY` | `0.30` | Verification weight for product identity confidence |
| `VERIFY_WEIGHT_EVIDENCE` | `0.25` | Verification weight for evidence confidence |
| `VERIFY_WEIGHT_IMAGE` | `0.30` | Verification weight for image confidence |
| `VERIFY_WEIGHT_BASE` | `0.15` | Base verification score added to all results |

## Tools

The agent uses 14 tools for web interaction and video processing:

| Tool | Description |
|------|-------------|
| `search_web` | Text search via DuckDuckGo with HTML fallback |
| `search_images` | Image search via DuckDuckGo |
| `search_videos` | Search for YouTube product review videos |
| `fetch_page` | Fetch static HTML pages with retry and rate limiting |
| `fetch_page_js` | Fetch JS-rendered pages via Playwright (headless Chromium) |
| `extract_structured_data` | Parse HTML tables, lists, and metadata from pages |
| `download_image` | Download images with size validation and retry |
| `download_video` | Download YouTube videos via yt-dlp at 720p cap |
| `extract_frames` | Extract key frames using scene detection + supplemental sampling |
| `select_best_frames` | AI-assisted frame selection using Gemini Vision |
| `analyze_image` | Classify product image view type using Gemini Vision |
| `deduplicate_images` | Perceptual hash (pHash) based image deduplication |
| `check_robots` | Check robots.txt compliance before fetching |
| `save_evidence` | Persist extracted claims to the database |

## Project Structure

```
scrap_snaps/
├── .env.example          # Environment variable template
├── .gitignore            # Git ignore rules
├── pyproject.toml        # Package config and dependencies
├── requirements.txt      # Pip dependencies
├── src/
│   ├── __init__.py
│   ├── config.py         # Centralized environment configuration
│   ├── db.py             # SQLAlchemy models and DB init
│   ├── graph.py          # LangGraph state machine definition
│   ├── llm.py            # Gemini LLM client configuration
│   ├── main.py           # CLI entry point
│   ├── state.py          # ResearchState TypedDict definition
│   ├── tools.py          # Web scraping, search, and analysis tools
│   └── nodes/
│       ├── __init__.py
│       ├── coverage.py   # Gap analysis - what's missing?
│       ├── discovery.py  # Product identification via search
│       ├── evidence.py   # Specification extraction
│       ├── media.py      # Image collection and classification
│       ├── planner.py    # LLM-powered task planning
│       ├── verification.py # Evidence quality scoring
│       └── video_extract.py # YouTube video frame extraction
└── tests/
    ├── __init__.py
    └── test_state.py     # State schema validation tests
```

## Database

The agent stores research results in a SQLAlchemy database. Models:

- **Product** - canonical product identity
- **Source** - web sources with reliability scores
- **Claim** - extracted specification claims with confidence
- **Image** - downloaded images with view classification and pHash
- **Video** - product video sources

Default: SQLite at `research.db`. Switch to PostgreSQL by setting `DATABASE_URL`:

```
DATABASE_URL=postgresql://user:pass@localhost:5432/scrap_snaps
```

## License

MIT
