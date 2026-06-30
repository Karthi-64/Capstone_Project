# v3/state.py — LangGraph pipeline state

from typing import TypedDict
import queue as _queue


class PipelineState(TypedDict, total=False):
    filepath: str
    watched_folder: str
    file_info: dict
    workflow: dict

    # 2 or 4 — chosen by the user via the step-choice popup
    step_count: int
    # folder paths for each step, e.g. {"Ingest": ".../01_Ingest", ...}
    step_folders: dict[str, str]
    # thread-safe queue the UI polls for live progress text
    progress_queue: "_queue.Queue | None"

    document_text: str
    use_rag: bool
    chunks_indexed: int
    summary_path: str | None
    workflow_summary_path: str | None
    source_path: str | None
    generation_brief: str

    ingest_error: str | None

    # 4-step only
    analysis: dict | None
    analysis_path: str | None
    analyze_error: str | None

    output_docx_path: str | None
    generate_error: str | None

    # 4-step only
    review_notes: str | None
    review_path: str | None
    reviewed_docx_path: str | None
    review_error: str | None
