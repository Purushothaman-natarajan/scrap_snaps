from typing import Dict, Any, List
from src.state import ResearchState
from src.llm import get_llm
from pydantic import BaseModel, Field

class Task(BaseModel):
    type: str = Field(description="The type of task: 'discover', 'find_images', 'verify_spec'")
    target: str = Field(description="The target of the task (e.g. 'front view', 'weight', or the product query)")
    priority: float = Field(description="Priority from 0.0 to 1.0")

class PlannerOutput(BaseModel):
    tasks: List[Task] = Field(description="The list of next tasks to execute")

def planner(state: ResearchState) -> Dict[str, Any]:
    """
    Planner Node (LLM-powered)
    Evaluates current state, generates tasks using LLM, and decides next actions.
    """
    print("--- PLANNER NODE ---")
    
    if "iterations" not in state:
        state["iterations"] = 0
    if "max_iterations" not in state:
        state["max_iterations"] = 30
        
    state["iterations"] += 1
    
    if state["iterations"] > state["max_iterations"]:
        return {"status": "max_iterations_reached", "tasks": []}
    
    tasks = state.get("tasks", [])
    if tasks:
        # If we already have tasks pending, don't generate more right now
        return {"tasks": tasks}
        
    llm = get_llm().with_structured_output(PlannerOutput)
    
    prompt = f"""
    You are the Planner for an autonomous Product Research Agent.
    Your goal is to gather comprehensive information and images about a product.
    
    Current State:
    - Query: {state.get("query")}
    - Product Identified: {bool(state.get("product"))}
    - Specifications Found: {list(state.get("specifications", {}).keys())}
    - Missing Views: {state.get("missing_views", [])}
    - Failed Tasks: {len(state.get("failed_tasks", []))}
    
    Decide what tasks to execute next. 
    If the product is not identified, output a 'discover' task.
    If the product is identified but missing views, output 'find_images' tasks for those views.
    If the product is identified but lacks specifications (like weight, dimensions, battery), output a 'verify_spec' task.
    """
    
    try:
        result = llm.invoke(prompt)
        new_tasks = [t.dict() for t in result.tasks]
        print(f"Planner generated {len(new_tasks)} tasks.")
        return {"tasks": new_tasks}
    except Exception as e:
        print(f"Planner LLM failed: {e}")
        # Fallback heuristic
        if not state.get("product"):
            return {"tasks": [{"type": "discover", "target": state.get("query", ""), "priority": 1.0}]}
        elif state.get("missing_views"):
            return {"tasks": [{"type": "find_images", "target": state.get("missing_views")[0], "priority": 0.9}]}
        else:
            return {"tasks": [{"type": "verify_spec", "target": "general", "priority": 0.8}]}
