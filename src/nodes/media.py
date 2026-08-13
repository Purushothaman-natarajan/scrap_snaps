from typing import Dict, Any
from src.state import ResearchState
from src.tools import search_images, download_image, analyze_image, deduplicate_images

def media(state: ResearchState) -> Dict[str, Any]:
    """
    Media Subgraph/Node
    Image searches -> download candidates -> deduplicate -> classify views.
    """
    print("--- MEDIA NODE ---")
    product = state.get("product", {})
    query = product.get("name", state.get("query", ""))
    
    tasks = state.get("tasks", [])
    target_view = "front"
    for t in tasks:
        if t.get("type") == "find_images":
            target_view = t.get("target")
            break

    search_q = f"{query} {target_view} view high quality"
    results = search_images.invoke({"query": search_q})
    
    images_list = state.get("images", [])
    discovered_views = state.get("discovered_views", {})
    
    if results:
        # Just grab the top 2 to avoid downloading too much in test
        for res in results[:2]:
            img_url = res.get("url")
            local_path = download_image.invoke({"url": img_url, "save_dir": "downloads"})
            
            if not local_path:
                continue
                
            # Deduplicate logic (simplified here)
            existing_paths = [img["local_path"] for img in images_list]
            existing_paths.append(local_path)
            
            unique_paths = deduplicate_images.invoke({"image_paths": existing_paths})
            
            if local_path in unique_paths:
                # It's unique, analyze it
                analysis = analyze_image.invoke({"image_path": local_path})
                
                view_type = analysis.get("view", "unknown")
                confidence = analysis.get("confidence", 0.0)
                product_match = analysis.get("product_match", False)
                
                if product_match:
                    images_list.append({
                        "url": img_url,
                        "local_path": local_path,
                        "view": view_type,
                        "confidence": confidence
                    })
                    
                    if view_type not in discovered_views:
                        discovered_views[view_type] = []
                    discovered_views[view_type].append(local_path)
            else:
                print(f"Skipped duplicate image: {local_path}")

    # Clean up processed tasks
    tasks = [t for t in tasks if t.get("type") != "find_images"]

    return {
        "images": images_list,
        "discovered_views": discovered_views,
        "tasks": tasks
    }
