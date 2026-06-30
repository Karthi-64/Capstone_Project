# v3/nodes/review.py — Node 4 (4-step only): review the generated report

import logging
import shutil
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from v3.llm import emit, get_llm
from v3.state import PipelineState

log = logging.getLogger("FolderGuardian.v3.review")

_REVIEW_SYSTEM = """
You are a QA reviewer for an automatically generated document.
Given the analysis notes and the document title, write a short review note
(3-5 sentences) confirming the document's completeness and flagging anything
that may need a human's attention. Plain text only, no JSON.
""".strip()


def review_node(state: PipelineState) -> PipelineState:
    if state.get("ingest_error") or state.get("generate_error"):
        return {}

    step_folders = state.get("step_folders", {})

    try:
        emit(state, "🔗  Proceeding to LangGraph node: Review…")
        emit(state, "🤖  Calling LLM for final QA review…")

        analysis = state.get("analysis") or {}
        generation_brief = state.get("generation_brief", "")

        llm = get_llm()
        response = llm.invoke(
            [
                SystemMessage(content=_REVIEW_SYSTEM),
                HumanMessage(
                    content=(
                        f"Generation brief: {generation_brief}\n"
                        f"Recommendations: {analysis.get('recommendations', [])}\n"
                        f"Risks/concerns: {analysis.get('risks_or_concerns', [])}"
                    )
                ),
            ]
        )
        review_notes = response.content.strip()

        review_dir = Path(step_folders.get("Review", "."))
        review_dir.mkdir(parents=True, exist_ok=True)

        source_stem = Path(state["filepath"]).stem
        notes_path = review_dir / f"{source_stem}_review_notes.txt"
        notes_path.write_text(review_notes, encoding="utf-8")

        # Copy the final generated docx into the Review folder as the
        # final reviewed deliverable
        output_docx = state.get("output_docx_path")
        reviewed_docx_path = None
        if output_docx and Path(output_docx).exists():
            dest = review_dir / Path(output_docx).name
            shutil.copy2(output_docx, dest)
            reviewed_docx_path = str(dest)

        emit(state, "✅  Review stage complete.")

        return {
            "review_notes": review_notes,
            "review_path": str(notes_path),
            "reviewed_docx_path": reviewed_docx_path,
            "review_error": None,
        }

    except Exception as exc:
        log.exception("Review failed")
        emit(state, f"❌  Review failed: {exc}")
        return {"review_error": str(exc)}
