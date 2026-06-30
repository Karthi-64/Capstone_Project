# v3/nodes/ingest.py — Node 1: load document, build RAG index, create summary

import json
import logging
import shutil
import time
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from file_info import get_file_info
from v3.llm import _SMALL_DOC_CHAR_LIMIT, emit, get_llm
from v3.rag.store import index_documents
from v3.rag.summaries import save_summary
from v3.state import PipelineState
from v3.tools.readers import documents_to_text, load_documents

log = logging.getLogger("FolderGuardian.v3.ingest")

_SUMMARY_SYSTEM = """
You summarize documents for an automation pipeline.
Respond ONLY with valid JSON:

{
  "title": "<short document title>",
  "overview": "<2-3 sentence overview>",
  "key_topics": ["topic1", "topic2"],
  "procedures": ["procedure1", "procedure2"],
  "generation_brief": "<one sentence describing what output document to create>"
}
""".strip()


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    ts = int(time.time())
    candidate = path.parent / f"{path.stem}_{ts}{path.suffix}"
    counter = 2
    while candidate.exists():
        candidate = path.parent / f"{path.stem}_{ts}_{counter}{path.suffix}"
        counter += 1
    return candidate


def ingest_node(state: PipelineState) -> PipelineState:
    filepath = state["filepath"]
    watched_folder = state["watched_folder"]
    step_folders = state.get("step_folders", {})
    path = Path(filepath)

    emit(state, "📂  Reading source file and extracting metadata…")

    if not path.exists():
        return {"ingest_error": f"File not found: {filepath}"}

    try:
        info = get_file_info(filepath)
        if info.get("size_raw", 0) == 0:
            return {"ingest_error": "File is empty"}

        emit(state, "🧩  Parsing document with LangChain document loaders…")
        documents = load_documents(filepath)
        document_text = documents_to_text(documents)
        if not document_text.strip():
            return {"ingest_error": "No readable content found in file"}

        source_id = path.stem
        use_rag = len(document_text) > _SMALL_DOC_CHAR_LIMIT
        chunks_indexed = 0

        if use_rag:
            emit(state, "🧠  Building vector knowledge base (Chroma + embeddings)…")
            chunks_indexed = index_documents(watched_folder, source_id, documents)
            log.info("Indexed %s chunk(s) for %s", chunks_indexed, path.name)
        else:
            log.info("Using direct context for small document: %s", path.name)

        emit(state, "🤖  Calling LLM (Groq · LangChain) to summarize content…")
        llm = get_llm()
        preview = document_text[:8000]
        response = llm.invoke(
            [
                SystemMessage(content=_SUMMARY_SYSTEM),
                HumanMessage(
                    content=(
                        f"File: {info['name']}\n"
                        f"Type: {info['type']}\n\n"
                        f"Document content:\n{preview}"
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

        summary = json.loads(raw.strip())
        summary_path = save_summary(watched_folder, source_id, summary)
        generation_brief = summary.get(
            "generation_brief",
            "Create a structured summary document from the source material.",
        )

        ingest_dir = Path(step_folders.get("Ingest", str(Path(watched_folder) / "Ingest")))
        ingest_dir.mkdir(parents=True, exist_ok=True)
        workflow_summary_path = ingest_dir / f"{source_id}_summary.json"
        workflow_summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        emit(state, "🗂️  Archiving original file into source folder…")
        source_dir = Path(step_folders.get("Source", str(Path(watched_folder) / "source")))
        source_dir.mkdir(parents=True, exist_ok=True)
        archive_target = _unique_path(source_dir / path.name)
        if path.resolve() != archive_target.resolve():
            shutil.move(str(path), str(archive_target))

        emit(state, "✅  Ingest stage complete.")

        return {
            "file_info": info,
            "document_text": document_text,
            "use_rag": use_rag,
            "chunks_indexed": chunks_indexed,
            "summary_path": summary_path,
            "workflow_summary_path": str(workflow_summary_path),
            "source_path": str(archive_target),
            "generation_brief": generation_brief,
            "ingest_error": None,
        }

    except Exception as exc:
        log.exception("Ingest failed for %s", filepath)
        emit(state, f"❌  Ingest failed: {exc}")
        return {"ingest_error": str(exc)}
