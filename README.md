# scrap_snaps

Autonomous product research agent powered by LangGraph. Given a product query, it discovers the product, extracts technical specifications, collects images from multiple views, and builds a verified evidence dossier.

## Architecture Overview

```mermaid
block-beta
    columns 5

    block:CONFIG:1
        columns 1
        CFG["⚙️ Config"]
        SETTINGS["Pydantic Settings"]
        LOGGING["structlog"]
    end

    block:CORE:1
        columns 1
        INFRA["🔧 Core"]
        REGISTRY["Plugin Registry"]
        GRAPH["Graph Builder"]
    end

    block:AGENTS:1
        columns 1
        BIZ["🧠 Agents"]
        PLANNER["Planner"]
        RESEARCHER["Researcher"]
        MEDIA["Media"]
        VERIFIER["Verifier"]
        COVERAGE["Coverage"]
    end

    block:NODES:1
        columns 1
        LG["🔗 LangGraph"]
        N_PLAN["planner"]
        N_DISC["discovery"]
        N_EVID["evidence"]
        N_MEDIA["media"]
        N_VERIFY["verification"]
        N_COV["coverage"]
    end

    block:TOOLS:1
        columns 1
        T["🛠️ Tools"]
        subgraph WEB["web/"]
            W1["search"]
            W2["fetch"]
            W3["robots"]
        end
        subgraph MEDIA_T["media/"]
            M1["images"]
            M2["video"]
        end
        DB_T["db/evidence"]
        UTILS["utils/"]
    end

    CONFIG --> CORE --> AGENTS --> NODES --> TOOLS
```

**Layer Responsibilities:**
| Layer | Purpose | Components |
|-------|---------|------------|
| Config | App settings & logging | Pydantic Settings, structlog |
| Core | Infrastructure & orchestration | Plugin registry, graph builder |
| Agents | Business logic & reasoning | Planner, Researcher, Media, Verifier, Coverage |
| LangGraph | Execution & state management | Node wrappers for each agent |
| Tools | External integrations | Web search, media, database, utilities |

### Agent Graph Flow

```mermaid
flowchart TD
    Start(["▶️ START"]) --> PLANNER["🧠 Planner"]
    
    PLANNER -- "discover" --> DISCOVER["🔍 Discovery"]
    PLANNER -- "verify_spec" --> EVIDENCE["📋 Evidence"]
    PLANNER -- "find_images" --> MEDIA_COLLECTOR["🖼️ Media"]
    PLANNER -- "find_videos" --> VIDEO_EXTRACTOR["🎬 Video"]
    PLANNER -- "no tasks" --> FINALIZE["✅ Finalize"]
    
    DISCOVER --> VERIFY
    EVIDENCE --> VERIFY
    MEDIA_COLLECTOR --> VERIFY
    VIDEO_EXTRACTOR --> VERIFY
    
    VERIFY["🔎 Verify"] --> COVERAGE["📊 Coverage"]
    
    COVERAGE -- "incomplete" --> PLANNER
    COVERAGE -- "complete" --> FINALIZE
    
    FINALIZE --> End(["⏹️ END"])
    
    style PLANNER fill:#E8D5FF,stroke:#6B21A8,stroke-width:2px,color:#000
    style VERIFY fill:#D5F0FF,stroke:#1E40AF,stroke-width:2px,color:#000
    style COVERAGE fill:#D5FFE8,stroke:#166534,stroke-width:2px,color:#000
    style FINALIZE fill:#FFE8D5,stroke:#9A3412,stroke-width:2px,color:#000
    style DISCOVER fill:#FFF,stroke:#333,stroke-width:1px
    style EVIDENCE fill:#FFF,stroke:#333,stroke-width:1px
    style MEDIA_COLLECTOR fill:#FFF,stroke:#333,stroke-width:1px
    style VIDEO_EXTRACTOR fill:#FFF,stroke:#333,stroke-width:1px
```

### Data Flow

```mermaid
sequenceDiagram
    participant User
    participant Main
    participant Graph
    participant Planner
    participant Agent
    participant LLM
    participant Tools
    participant DB

    User->>Main: query("Sony WH-1000XM5")
    Main->>Graph: stream(initial_state)
    
    loop Until Complete
        Graph->>Planner: state
        Planner->>LLM: generate_tasks(state)
        LLM-->>Planner: tasks[]
        
        alt discover task
            Planner->>Agent: ResearchAgent.discover()
            Agent->>Tools: search_web()
            Tools-->>Agent: results[]
            Agent->>LLM: extract_candidates()
            LLM-->>Agent: candidates[]
        else find_images task
            Planner->>Agent: MediaAgent.collect_images()
            Agent->>Tools: search_images()
            Agent->>Tools: download_image()
            Agent->>LLM: analyze_image()
        end
        
        Agent-->>Graph: updated_state
        Graph->>Graph: Verify (score)
        Graph->>Graph: Coverage (gap check)
    end
    
    Graph-->>Main: final_state
    Main-->>User: results
```

## Project Structure

```
scrap_snaps/
├── .env.example              # Environment variable template
├── .gitignore
├── pyproject.toml            # Package config and dependencies
├── requirements.txt          # Pip dependencies
├── src/
│   ├── __init__.py
│   ├── config.py             # Backward-compatible config exports
│   ├── graph.py              # Backward-compatible graph exports
│   ├── tools.py              # Backward-compatible tool exports
│   ├── llm.py                # Azure OpenAI LLM client
│   ├── main.py               # CLI entry point
│   ├── state.py              # ResearchState TypedDict definition
│   ├── db.py                 # SQLAlchemy models and DB init
│   │
│   ├── config/               # Configuration package
│   │   ├── __init__.py       # Backward-compatible exports
│   │   ├── settings.py       # Pydantic Settings (env + validation)
│   │   └── logging.py        # Structured logging (structlog)
│   │
│   ├── core/                 # Core infrastructure
│   │   ├── __init__.py
│   │   ├── graph.py          # Enhanced graph builder with registry
│   │   └── registry.py       # Plugin registry for nodes/tools/agents
│   │
│   ├── agents/               # Business logic classes
│   │   ├── __init__.py
│   │   ├── base.py           # BaseAgent with common utilities
│   │   ├── planner.py        # PlannerAgent (task generation)
│   │   ├── researcher.py     # ResearchAgent (discovery + evidence)
│   │   ├── media_collector.py# MediaAgent (images + videos)
│   │   ├── verifier.py       # VerificationAgent (scoring)
│   │   └── coverage.py       # CoverageAgent (gap analysis)
│   │
│   ├── nodes/                # Thin LangGraph node wrappers
│   │   ├── __init__.py
│   │   ├── planner.py        # → PlannerAgent
│   │   ├── discovery.py      # → ResearchAgent
│   │   ├── evidence.py       # → ResearchAgent
│   │   ├── media.py          # → MediaAgent
│   │   ├── video_extract.py  # → MediaAgent
│   │   ├── verification.py   # → VerifierAgent
│   │   └── coverage.py       # → CoverageAgent
│   │
│   ├── tools/                # Modular tool package
│   │   ├── __init__.py       # Centralized tool registry
│   │   ├── web/
│   │   │   ├── search.py     # search_web, search_images, search_videos
│   │   │   ├── fetch.py      # fetch_page, fetch_page_js, extract_structured_data
│   │   │   └── robots.py     # check_robots
│   │   ├── media/
│   │   │   ├── images.py     # download_image, analyze_image, deduplicate_images
│   │   │   └── video.py      # download_video, extract_frames, select_best_frames
│   │   ├── db/
│   │   │   └── evidence.py   # save_evidence
│   │   └── utils/
│   │       ├── http.py       # rate_limit, can_fetch, http_get
│   │       └── hashing.py    # perceptual_hash, are_similar
│   │
│   └── db/                   # Database package
│       ├── __init__.py
│       └── (models in db.py)
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
# Edit .env and add your API keys
```

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and edit.

### LLM Provider (Azure OpenAI)

| Variable | Default | Description |
|----------|---------|-------------|
| `AZURE_API_KEY` | *(required)* | Azure OpenAI API key |
| `AZURE_ENDPOINT` | *(required)* | Azure OpenAI endpoint URL (e.g., `https://your-resource.openai.azure.com/`) |
| `AZURE_DEPLOYMENT` | *(required)* | Azure deployment name (model deployment identifier) |
| `AZURE_CONSUMER_ID` | *(required)* | Azure consumer ID (for request tracking) |

### Execution

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///research.db` | SQLAlchemy database connection string |
| `MAX_ITERATIONS` | `30` | Maximum planner iterations before forced stop |
| `RECURSION_LIMIT` | `50` | LangGraph recursion limit |
| `REQUIRED_VIEWS` | `front,back,side,top` | Comma-separated image views to collect |

### Networking

| Variable | Default | Description |
|----------|---------|-------------|
| `SERPAPI_KEY` | *(required)* | SerpAPI key for Google Search ([get one](https://serpapi.com/)) |
| `RATE_LIMIT_INTERVAL` | `1.0` | Minimum seconds between HTTP requests |
| `REQUEST_TIMEOUT` | `10.0` | HTTP request timeout in seconds |
| `USER_AGENT` | *(Chrome UA)* | User-Agent header for HTTP requests |

### Playwright

| Variable | Default | Description |
|----------|---------|-------------|
| `PLAYWRIGHT_NAV_TIMEOUT` | `30000` | Playwright page navigation timeout (ms) |
| `PLAYWRIGHT_SELECTOR_TIMEOUT` | `10000` | Playwright element wait timeout (ms) |

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

## Usage

```bash
# Run with default query (Sony WH-1000XM5)
python -m src.main

# Run with a custom query
python -m src.main "iPhone 15 Pro Max"

# Run with a specific product
python -m src.main "Samsung Galaxy S24 Ultra"
```

## Tools

The agent uses 14 tools organized by domain:

| Tool | Module | Description |
|------|--------|-------------|
| `search_web` | `tools/web/search.py` | Google search via SerpAPI |
| `search_images` | `tools/web/search.py` | Google image search via SerpAPI |
| `search_videos` | `tools/web/search.py` | YouTube search via SerpAPI |
| `fetch_page` | `tools/web/fetch.py` | Fetch static HTML pages with retry and rate limiting |
| `fetch_page_js` | `tools/web/fetch.py` | Fetch JS-rendered pages via Playwright |
| `extract_structured_data` | `tools/web/fetch.py` | Parse HTML tables, lists, and metadata |
| `check_robots` | `tools/web/robots.py` | Check robots.txt compliance |
| `download_image` | `tools/media/images.py` | Download images with size validation |
| `analyze_image` | `tools/media/images.py` | Classify product image view type using LLM |
| `deduplicate_images` | `tools/media/images.py` | Perceptual hash (pHash) based deduplication |
| `download_video` | `tools/media/video.py` | Download YouTube videos via yt-dlp |
| `extract_frames` | `tools/media/video.py` | Extract key frames using scene detection |
| `select_best_frames` | `tools/media/video.py` | AI-assisted frame selection using LLM |
| `save_evidence` | `tools/db/evidence.py` | Persist extracted claims to the database |

## Developer Guide

### Quick Start

```python
# 1. Import the graph builder
from src.core.graph import build_graph

# 2. Build and compile the graph
graph = build_graph()

# 3. Define initial state
initial_state = {
    "query": "Sony WH-1000XM5",
    "product": {},
    "candidates": [],
    "search_queries": [],
    "searched_queries": [],
    "sources": [],
    "evidence": [],
    "specifications": {},
    "images": [],
    "videos": [],
    "video_frames": {},
    "required_views": ["front", "back", "side", "top"],
    "discovered_views": {},
    "missing_views": ["front", "back", "side", "top"],
    "tasks": [],
    "completed_tasks": [],
    "failed_tasks": [],
    "iterations": 0,
    "max_iterations": 30,
    "confidence": 0.0,
    "status": "started",
}

# 4. Run the graph
for event in graph.stream(initial_state, {"recursion_limit": 50}):
    for key, value in event.items():
        print(f"Finished: {key}")
```

### Architecture Deep Dive

#### 1. Configuration Layer (`config/`)

The configuration uses Pydantic Settings for type-safe, validated environment variables:

```python
from src.config import settings

# Access nested configs
print(settings.llm.provider)      # "azure"
print(settings.database.url)       # "sqlite:///research.db"
print(settings.execution.max_iterations)  # 30

# Validate required settings
missing = settings.validate_required()
if missing:
    print(f"Missing: {missing}")
```

**Key Features:**
- Nested config groups (LLM, Database, Execution, etc.)
- Environment variable binding with `env_prefix`
- Type validation and defaults
- Sensitive data redaction in logs

#### 2. Structured Logging (`config/logging.py`)

Uses `structlog` for structured, JSON-ready logs:

```python
from src.config.logging import get_logger

logger = get_logger(__name__)
logger.info("Processing started", query="Sony WH-1000XM5", user_id="123")
# Output: {"query": "Sony WH-1000XM5", "user_id": "123", "level": "info", "service": "scrap-snaps"}

# Sensitive data is automatically redacted
logger.debug("API call", api_key="secret123")
# Output: {"api_key": "[REDACTED]", "level": "debug"}
```

#### 3. Plugin Registry (`core/registry.py`)

Register and discover components at runtime:

```python
from src.core.registry import registry

# Register custom components
@registry.node("my_custom_node")
def my_node(state: dict) -> dict:
    return {"result": "done"}

@registry.tool("my_custom_tool")
def my_tool(query: str) -> str:
    return f"Result: {query}"

# List registered components
print(registry.list_nodes())     # ["planner", "discover", ..., "my_custom_node"]
print(registry.list_tools())     # ["my_custom_tool"]

# Get summary
print(registry.summary())
# {"nodes": [...], "tools": [...], "agents": [...], "graphs": [...]}
```

#### 4. Agent Classes (`agents/`)

Agents encapsulate business logic, LLM calls, and decision-making:

```python
from src.agents.base import BaseAgent
from src.agents.planner import PlannerAgent

# Use existing agents
planner = PlannerAgent()
result = planner.run(state)

# Create custom agent
class MyAgent(BaseAgent):
    name = "my_agent"

    def run(self, state: dict) -> dict:
        llm = self.get_llm(temperature=0.5)
        # ... your logic here
        return {"result": "done"}
```

**Agent Hierarchy:**
```
BaseAgent
├── PlannerAgent        # Task generation and iteration control
├── ResearchAgent       # Discovery and evidence extraction
├── MediaAgent          # Image and video collection
├── VerifierAgent       # Evidence quality scoring
└── CoverageAgent       # Gap analysis and routing
```

#### 5. Node Wrappers (`nodes/`)

Nodes are thin LangGraph wrappers that call agents:

```python
from src.agents.planner import PlannerAgent
from src.state import ResearchState

_agent = PlannerAgent()

def planner(state: ResearchState) -> dict:
    """Planner Node - delegates to PlannerAgent."""
    return _agent.run(state)
```

**Why Thin Nodes?**
- Separation of concerns (business logic vs. graph wiring)
- Easy to test agents independently
- Reusable across different graphs

#### 6. Modular Tools (`tools/`)

Tools are organized by domain for maintainability:

```
tools/
├── web/           # Web scraping and search
│   ├── search.py  # DuckDuckGo search
│   ├── fetch.py   # Page fetching (static + JS)
│   └── robots.py  # robots.txt checking
├── media/         # Image and video processing
│   ├── images.py  # Image download and analysis
│   └── video.py   # Video download and frame extraction
├── db/            # Database operations
│   └── evidence.py
└── utils/         # Shared utilities
    ├── http.py    # HTTP client with retry
    └── hashing.py # Image hashing
```

**Adding a New Tool:**

```python
# src/tools/web/my_tool.py
from langchain_core.tools import tool
from src.config.logging import get_logger

logger = get_logger(__name__)

@tool
def my_custom_tool(query: str, limit: int = 10) -> list[dict]:
    """Search for custom data matching a query.

    Args:
        query: The search query
        limit: Maximum results to return

    Returns:
        List of result dicts with 'url', 'title', 'snippet' keys
    """
    logger.info("Executing custom search for: %s", query)
    # Your implementation here
    return [{"url": "...", "title": "...", "snippet": "..."}]
```

**Register the Tool:**

```python
# src/tools/__init__.py
from src.tools.web.my_tool import my_custom_tool

__all__ = [..., "my_custom_tool"]
```

#### 7. Graph Builder (`core/graph.py`)

Build graphs with or without the registry:

```python
from src.core.graph import build_graph

# Standard build (uses registry)
graph = build_graph()

# Build without registry (direct imports)
graph = build_graph(use_registry=False)

# Get builder without compiling
builder = build_graph(compile=False)
builder.add_node("custom", my_custom_func)
builder.add_edge("planner", "custom")
compiled = builder.compile()
```

### End-to-End Flow

1. **Initialization**
   - Load settings from environment
   - Configure structured logging
   - Register default components in registry
   - Build and compile the LangGraph

2. **Planner Node**
   - Evaluates current state (iterations, tasks, coverage)
   - Calls LLM to generate research tasks
   - Routes to appropriate execution node based on task type

3. **Execution Nodes**
   - **Discovery**: Web search → LLM extraction → product identification
   - **Evidence**: Search → fetch page → LLM spec extraction
   - **Media**: Image search → download → dedup → LLM classification
   - **Video**: YouTube search → download → frame extraction → classification

4. **Verification Node**
   - Computes weighted confidence score
   - Factors: identity, evidence, image quality

5. **Coverage Node**
   - Checks which views are still missing
   - Routes back to planner (if incomplete) or finalize (if complete)

6. **Finalize Node**
   - Packages results
   - Returns final state

### Database Models

```python
# src/db.py
class Product(Base):
    """Canonical product identity."""
    id: int
    canonical_name: str
    created_at: datetime

class Source(Base):
    """Web source with reliability score."""
    id: int
    url: str
    source_type: str
    reliability_score: float

class Claim(Base):
    """Extracted specification claim."""
    id: int
    product_id: int
    source_id: int
    claim_type: str
    value: str
    confidence: float

class Image(Base):
    """Downloaded and classified image."""
    id: int
    product_id: int
    url: str
    phash: str
    view_type: str
    local_path: str
```

### Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src

# Run specific test
python -m pytest tests/test_state.py -v
```

### Linting

```bash
# Check for issues
python -m ruff check src/

# Auto-fix issues
python -m ruff check src/ --fix

# Format code
python -m ruff format src/
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