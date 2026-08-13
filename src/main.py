import os
from dotenv import load_dotenv
from src.graph import build_graph
from src.db import init_db

# Load environment variables
load_dotenv()

def run_research(query: str):
    print(f"Starting research for: {query}")
    
    # Init DB
    db_url = os.getenv("DATABASE_URL", "sqlite:///research.db")
    session = init_db(db_url)
    print(f"Initialized Database at {db_url}")
    
    graph = build_graph()
    
    initial_state = {
        "query": query,
        "product": {},
        "candidates": [],
        "search_queries": [],
        "searched_queries": [],
        "sources": [],
        "evidence": [],
        "specifications": {},
        "images": [],
        "videos": [],
        # Standard views we want to acquire for a full dossier
        "required_views": ["front", "back", "side", "top"], 
        "discovered_views": {},
        "missing_views": ["front", "back", "side", "top"],
        "tasks": [],
        "completed_tasks": [],
        "failed_tasks": [],
        "iterations": 0,
        "max_iterations": 10, # Keep it low for testing
        "confidence": 0.0,
        "status": "started"
    }

    print("\n--- Execution Trace ---\n")
    # Stream the graph execution
    for event in graph.stream(initial_state, {"recursion_limit": 50}):
        for key, value in event.items():
            print(f"Finished Node: {key}")
            # If you want verbose logging, uncomment the next line
            # print(f"State Updates: {value}\n")
    
    print("\n--- Research Complete ---\n")
    
    # We could theoretically retrieve the final state and save it to the DB here
    # or print out the final dossier.
    
    # Cleanup DB session
    session.close()

if __name__ == "__main__":
    import sys
    # For testing, you can pass a query as an argument, e.g. python -m src.main "Sony WH-1000XM5"
    query = "Sony WH-1000XM5" if len(sys.argv) < 2 else sys.argv[1]
    
    if not os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY") == "your_google_api_key_here":
        print("WARNING: GOOGLE_API_KEY is not set in .env. LLM calls will fail.")
        
    run_research(query)
