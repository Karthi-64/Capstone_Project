# v3/pipeline.py — public entry point for FolderGuardian V3

import logging
import queue as _queue
import threading
from pathlib import Path

from workflow_store import get_or_create_workflow, resolve_step_folders

from v3.graph import build_graph
from v3.llm import API_KEY

log = logging.getLogger("FolderGuardian.v3")

TIMEOUT = 180
_graphs: dict[int, object] = {}


def _get_graph(step_count: int):
    if step_count not in _graphs:
        _graphs[step_count] = build_graph(step_count)
    return _graphs[step_count]


def run_pipeline(
    filepath: str,
    watched_folder: str,
    step_count: int = 2,
    progress_queue: "_queue.Queue | None" = None,
) -> dict:
    """
    Runs the ingest → (analyze) → generate → (review) pipeline.

    step_count: 2 or 4, chosen by the user via the step-choice popup.
    progress_queue: if given, pipeline nodes push human-readable status
                     strings here so a UI can display live progress.
    """
    if not API_KEY:
        if progress_queue is not None:
            progress_queue.put("❌  GROQ_API_KEY not set.")
        return {"error": "GROQ_API_KEY not set"}

    source_stem = Path(filepath).stem
    workflow = get_or_create_workflow(watched_folder, step_count=step_count)
    step_folders = resolve_step_folders(watched_folder, workflow, source_stem)

    if progress_queue is not None:
        progress_queue.put("🧠  Connecting to LangGraph engine…")

    initial_state = {
        "filepath": filepath,
        "watched_folder": watched_folder,
        "workflow": workflow,
        "step_count": step_count,
        "step_folders": step_folders,
        "progress_queue": progress_queue,
    }

    result: dict = {}
    error: dict = {}

    def _invoke():
        nonlocal result
        try:
            result = _get_graph(step_count).invoke(initial_state)
        except Exception as exc:
            error["message"] = str(exc)

    thread = threading.Thread(target=_invoke, daemon=True)
    thread.start()
    thread.join(timeout=TIMEOUT)

    if error:
        if progress_queue is not None:
            progress_queue.put(f"❌  Pipeline error: {error['message']}")
        return {"error": error["message"]}

    if not result:
        if progress_queue is not None:
            progress_queue.put("❌  Pipeline timed out.")
        return {"error": "Pipeline timed out"}

    if result.get("ingest_error"):
        return {"error": result["ingest_error"]}
    if result.get("analyze_error"):
        return {"error": result["analyze_error"]}
    if result.get("generate_error"):
        return {"error": result["generate_error"]}
    if result.get("review_error"):
        return {"error": result["review_error"]}

    log.info(
        "Pipeline complete — summary: %s, output: %s",
        result.get("summary_path"),
        result.get("output_docx_path"),
    )

    return {
        "summary_path": result.get("summary_path"),
        "workflow_summary_path": result.get("workflow_summary_path"),
        "source_path": result.get("source_path"),
        "analysis_path": result.get("analysis_path"),
        "output_docx_path": result.get("output_docx_path"),
        "review_path": result.get("review_path"),
        "reviewed_docx_path": result.get("reviewed_docx_path"),
        "chunks_indexed": result.get("chunks_indexed", 0),
        "generation_brief": result.get("generation_brief"),
        "step_folders": step_folders,
    }
