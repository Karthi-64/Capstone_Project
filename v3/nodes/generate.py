# v3/nodes/generate.py — Node: RAG retrieval and DOCX generation

import logging
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from v3.llm import emit, get_llm
from v3.rag.store import get_retriever
from v3.rag.summaries import load_summary
from v3.state import PipelineState
from v3.tools.writers import write_docx

log = logging.getLogger("FolderGuardian.v3.generate")

_SECTION_SYSTEM = """
You write one section of a professional document.
Use ONLY the provided source context.
Return plain text for the section body with short paragraphs or bullet points.
Do not include the section title in your response.
""".strip()


def _retrieve_context(state: PipelineState, section: str) -> str:
    watched_folder = state["watched_folder"]
    source_id = Path(state["filepath"]).stem
    query = f"{section}: {state.get('generation_brief', '')}"

    if state.get("use_rag"):
        retriever = get_retriever(watched_folder, source_id)
        docs = retriever.invoke(query)
        return "\n\n".join(doc.page_content for doc in docs)

    return state.get("document_text", "")[:8000]


def _generate_section_content(state: PipelineState, section: str, context: str) -> str:
    llm = get_llm()
    response = llm.invoke(
        [
            SystemMessage(content=_SECTION_SYSTEM),
            HumanMessage(
                content=(
                    f"Section: {section}\n"
                    f"Brief: {state.get('generation_brief', '')}\n\n"
                    f"Source context:\n{context}"
                )
            ),
        ]
    )
    return response.content.strip()


def generate_node(state: PipelineState) -> PipelineState:
    if state.get("ingest_error"):
        return {}

    try:
        emit(state, "🔗  Proceeding to LangGraph node: Generate…")
        emit(state, "🔗  Initializing LangChain retrieval chain…")

        workflow = state.get("workflow") or {}
        template = workflow.get("generation_template", {})
        sections = template.get(
            "sections",
            ["Overview", "Key Procedures", "Important Details", "Action Items"],
        )

        source_stem = Path(state["filepath"]).stem
        summary = load_summary(state["watched_folder"], source_stem) or {}
        title = summary.get("title") or template.get(
            "default_title",
            "Automated Summary Report",
        )

        section_content: dict[str, str] = {}
        for section in sections:
            emit(state, f"🤖  Generating section with LLM: {section}…")
            context = _retrieve_context(state, section)
            if summary.get("overview") and section.lower() == "overview":
                context = f"{summary['overview']}\n\n{context}"

            if state.get("analysis"):
                context += f"\n\nDeeper analysis notes:\n{state['analysis'].get('analysis_notes', '')}"

            section_content[section] = _generate_section_content(
                state,
                section,
                context,
            )
            log.info("Generated section: %s", section)

        step_folders = state.get("step_folders", {})
        output_dir = Path(step_folders.get("Generate", str(Path(state["watched_folder"]) / "Generated")))
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_title = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in title)
        output_path = output_dir / f"{safe_title.strip() or 'Report'}.docx"

        emit(state, "📝  Writing DOCX report…")
        final_path = write_docx(
            str(output_path),
            title,
            section_content,
        )

        emit(state, "✅  Generate stage complete.")

        return {
            "output_docx_path": final_path,
            "generate_error": None,
        }

    except Exception as exc:
        log.exception("Generate failed")
        emit(state, f"❌  Generate failed: {exc}")
        return {"generate_error": str(exc)}
