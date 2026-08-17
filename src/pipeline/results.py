"""Result extraction from graph execution output."""

from __future__ import annotations

from typing import Any


def extract_result(final_state: dict[str, Any]) -> dict:
    """Extract structured result from the final graph state.

    Args:
        final_state: The state dict after graph execution completes.

    Returns:
        Dict with standardized result fields for Excel output.
    """
    product = final_state.get("product", {})
    specs = final_state.get("specifications", {})
    images = final_state.get("images", [])
    videos = final_state.get("videos", [])

    image_paths = [img.get("local_path", "") for img in images if img.get("local_path")]
    video_paths = [vid.get("local_path", "") for vid in videos if vid.get("local_path")]

    return {
        "row_index": final_state.get("__row_index", 0),
        "product_name": product.get("name", final_state.get("query", "")),
        "status": final_state.get("status", "unknown"),
        "confidence": final_state.get("confidence", 0.0),
        "specifications": specs,
        "images_collected": len(images),
        "videos_collected": len(videos),
        "image_paths": image_paths,
        "video_paths": video_paths,
        "error": _extract_error(final_state),
    }


def extract_result_for_row(row_data: dict, final_state: dict[str, Any]) -> dict:
    """Extract result for a specific row from Excel input.

    Args:
        row_data: The original row dict from Excel.
        final_state: The state dict after graph execution.

    Returns:
        Dict with standardized result fields.
    """
    result = extract_result(final_state)
    result["row_index"] = row_data.get("__row_index", result["row_index"])

    if not result["product_name"]:
        for key in ["product", "name", "title", "item"]:
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
