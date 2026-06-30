# v3/nodes/analyze.py — Node 2 (4-step only): deeper analysis of ingested content

import json
import logging
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from v3.llm import emit, get_llm
from v3.state import PipelineState

log = logging.getLogger("FolderGuardian.v3.analyze")

_ANALYZE_SYSTEM = """
You perform a deeper analysis of a document that has already been summarized.
Respond ONLY with valid JSON:

{
  "key_entities": ["entity1", "entity2"],
  "risks_or_concerns": ["risk1", "risk2"],
  "recommendations": ["recommendation1", "recommendation2"],
  "analysis_notes": "<2-4 sentence deeper analysis beyond the summary>"
}
""".strip()


def analyze_node(state: PipelineState) -> PipelineState:
    if state.get("ingest_error"):
        return {}

    step_folders = state.get("step_folders", {})
    emit(state, "🔎  Proceeding to LangGraph node: Analyze…")
    emit(state, "🔗  Building LangChain analysis chain…")

    try:
        document_text = state.get("document_text", "")[:8000]
        generation_brief = state.get("generation_brief", "")

        emit(state, "🤖  Calling LLM (Groq) for deeper analysis…")
        llm = get_llm()
        response = llm.invoke(
            [
                SystemMessage(content=_ANALYZE_SYSTEM),
                HumanMessage(
                    content=(
                        f"Generation brief: {generation_brief}\n\n"
                        f"Document content:\n{document_text}"
                    )
                ),
            ]
        )

        raw = response.content.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]

        analysis = json.loads(raw.strip())

        analyze_dir = Path(step_folders.get("Analyze", "."))
        analyze_dir.mkdir(parents=True, exist_ok=True)
        source_stem = Path(state["filepath"]).stem
        analysis_path = analyze_dir / f"{source_stem}_analysis.json"
        analysis_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")

        emit(state, "✅  Analyze stage complete.")

        return {
            "analysis": analysis,
            "analysis_path": str(analysis_path),
            "analyze_error": None,
        }

    except Exception as exc:
        log.exception("Analyze failed")
        emit(state, f"❌  Analyze failed: {exc}")
        return {"analyze_error": str(exc)}
