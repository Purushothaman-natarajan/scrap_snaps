"""Result extraction from graph execution output."""

from __future__ import annotations

from typing import Any


def extract_result(
    final_state: dict[str, Any],
    usage_metrics: dict | None = None,
) -> dict:
    """Extract structured result from the final graph state.

    Args:
        final_state: The state dict after graph execution completes.
        usage_metrics: Optional usage metrics dict to include in output.

    Returns:
        Dict with standardized result fields for Excel output.
    """
    product = final_state.get("product", {})
    specs = final_state.get("specifications", {})
    images = final_state.get("images", [])
    videos = final_state.get("videos", [])
    sources = final_state.get("sources", [])
    evidence = final_state.get("evidence", [])

    source_urls = [s.get("url", "") for s in sources if s.get("url")]
    evidence_urls = [e.get("source", "") for e in evidence if e.get("source")]
    all_source_urls = list(dict.fromkeys(source_urls + evidence_urls))

    image_urls = [img.get("url", "") for img in images if img.get("url")]
    image_paths = [img.get("local_path", "") for img in images if img.get("local_path")]
    image_views = [img.get("view", "unknown") for img in images]

    video_urls = [vid.get("url", "") for vid in videos if vid.get("url")]
    video_paths = [vid.get("local_path", "") for vid in videos if vid.get("local_path")]

    return {
        "row_index": final_state.get("__row_index", 0),
        "product_name": product.get("name", final_state.get("query", "")),
        "status": final_state.get("status", "unknown"),
        "confidence": final_state.get("confidence", 0.0),
        "specifications": specs,
        "source_urls": all_source_urls,
        "image_urls": image_urls,
        "image_paths": image_paths,
        "image_views": image_views,
        "video_urls": video_urls,
        "video_paths": video_paths,
        "images": [
            {
                "url": img.get("url", ""),
                "local_path": img.get("local_path", ""),
                "view": img.get("view", "unknown"),
                "confidence": img.get("confidence", 0.0),
                "source": img.get("source", "web"),
            }
            for img in images
        ],
        "videos": [
            {
                "url": vid.get("url", ""),
                "local_path": vid.get("local_path", ""),
                "title": vid.get("title", ""),
                "duration": vid.get("duration", 0),
                "score": vid.get("score", 0.0),
            }
            for vid in videos
        ],
        "error": _extract_error(final_state),
        **({"usage_metrics": usage_metrics} if usage_metrics else {}),
    }


def extract_result_for_row(
    row_data: dict,
    final_state: dict[str, Any],
    usage_metrics: dict | None = None,
) -> dict:
    """Extract result for a specific row from Excel input.

    Args:
        row_data: The original row dict from Excel.
        final_state: The state dict after graph execution.
        usage_metrics: Optional usage metrics dict to include in output.

    Returns:
        Dict with standardized result fields.
    """
    result = extract_result(final_state, usage_metrics=usage_metrics)
    result["row_index"] = row_data.get("__row_index", result["row_index"])

    if not result["product_name"]:
        for key in ["product", "name", "title", "item", "product_name"]:
            if key in row_data and row_data[key]:
                result["product_name"] = str(row_data[key])
                break

    return result


def _extract_error(state: dict) -> str:
    """Extract error message from failed tasks."""
    failed = state.get("failed_tasks", [])
    if not failed:
        return ""

    errors = []
    for task in failed:
        error = task.get("error", "")
        if error:
            errors.append(error)

    return "; ".join(errors) if errors else ""
