"""Media acquisition node - search, download, deduplicate, and classify product images."""

from __future__ import annotations

import logging

from src.config import DOWNLOAD_DIR, MAX_IMAGE_RESULTS
from src.state import ResearchState
from src.tools import analyze_image, deduplicate_images, download_image, search_images

logger = logging.getLogger(__name__)

DEFAULT_TARGET_VIEW = "front"


def media(state: ResearchState) -> dict:
    """Media Node.

    Image searches -> download candidates -> deduplicate -> classify views.
    """
    logger.info("Media node executing")
    product = state.get("product", {})
    query = product.get("name", state.get("query", ""))

    tasks = state.get("tasks", [])
    target_view = DEFAULT_TARGET_VIEW
    # Extract the target view from the first find_images task.
    # The planner may generate multiple tasks, but we process them one at a time.
    for t in tasks:
        if t.get("type") == "find_images":
            target_view = t.get("target")
            break

    search_q = f"{query} {target_view} view high quality"
    results = search_images.invoke({"query": search_q, "limit": MAX_IMAGE_RESULTS})

    images_list = state.get("images", [])
    discovered_views = state.get("discovered_views", {})

    if results:
        # Process top 2 results to balance thoroughness vs. download time/cost.
        # Each image goes through: download -> dedup -> vision analysis -> classify.
        for res in results[:2]:
            img_url = res.get("url")
            local_path = download_image.invoke({"url": img_url, "save_dir": DOWNLOAD_DIR})

            if not local_path:
                continue

            existing_paths = [img["local_path"] for img in images_list]
            existing_paths.append(local_path)

            unique_paths = deduplicate_images.invoke({"image_paths": existing_paths})

            if local_path in unique_paths:
                analysis = analyze_image.invoke({"image_path": local_path})

                view_type = analysis.get("view", "unknown")
                confidence = analysis.get("confidence", 0.0)
                product_match = analysis.get("product_match", False)

                if product_match:
                    images_list.append(
                        {
                            "url": img_url,
                            "local_path": local_path,
                            "view": view_type,
                            "confidence": confidence,
                        }
                    )

                    if view_type not in discovered_views:
                        discovered_views[view_type] = []
                    discovered_views[view_type].append(local_path)
            else:
                logger.info("Skipped duplicate image: %s", local_path)

    tasks = [t for t in tasks if t.get("type") != "find_images"]

    return {"images": images_list, "discovered_views": discovered_views, "tasks": tasks}
