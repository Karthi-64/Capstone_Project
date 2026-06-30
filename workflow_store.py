# workflow_store.py  ─  FolderGuardian  workflow config persistence

import copy
import json
from pathlib import Path

STORE_FILE = Path(__file__).parent / 'workflows.json'

_TWO_STEP_TEMPLATE = {
    "name": "Document Processing Pipeline (2-step)",
    "version": 3,
    "step_count": 2,
    "steps": [
        {
            "step": 1,
            "name": "Ingest",
            "description": (
                "Read the incoming document, build the knowledge base, "
                "and create a RAG summary artifact."
            ),
        },
        {
            "step": 2,
            "name": "Generate",
            "description": (
                "Retrieve knowledge from the RAG store and generate "
                "an automated DOCX report."
            ),
        },
    ],
    "generation_template": {
        "output_type": "docx",
        "default_title": "Automated Summary Report",
        "sections": [
            "Overview",
            "Key Procedures",
            "Important Details",
            "Action Items",
        ],
    },
}

_FOUR_STEP_TEMPLATE = {
    "name": "Document Processing Pipeline (4-step)",
    "version": 3,
    "step_count": 4,
    "steps": [
        {
            "step": 1,
            "name": "Ingest",
            "description": (
                "Read the incoming document, build the knowledge base, "
                "and create a RAG summary artifact."
            ),
        },
        {
            "step": 2,
            "name": "Analyze",
            "description": (
                "Perform a deeper analysis: key entities, risks, "
                "and recommendations beyond the initial summary."
            ),
        },
        {
            "step": 3,
            "name": "Generate",
            "description": (
                "Retrieve knowledge from the RAG store and the analysis, "
                "and generate an automated DOCX report."
            ),
        },
        {
            "step": 4,
            "name": "Review",
            "description": (
                "Run a final QA pass over the generated report and "
                "produce review notes alongside the finished document."
            ),
        },
    ],
    "generation_template": {
        "output_type": "docx",
        "default_title": "Automated Summary Report",
        "sections": [
            "Overview",
            "Key Procedures",
            "Important Details",
            "Action Items",
        ],
    },
}


def load_all() -> dict:
    if STORE_FILE.exists():
        try:
            return json.loads(STORE_FILE.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def save_all(data: dict):
    STORE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def _folder_key(folder: str) -> str:
    return str(Path(folder).resolve())


def get_workflow(folder: str) -> dict | None:
    """Return workflow config for a folder, or None if not defined."""
    return load_all().get(_folder_key(folder))


def save_workflow(folder: str, workflow: dict):
    """Persist a workflow config for a folder."""
    data = load_all()
    data[_folder_key(folder)] = workflow
    save_all(data)


def build_workflow(step_count: int) -> dict:
    """Return a fresh workflow template for the chosen step count (2 or 4)."""
    if step_count == 4:
        return copy.deepcopy(_FOUR_STEP_TEMPLATE)
    return copy.deepcopy(_TWO_STEP_TEMPLATE)


def get_or_create_workflow(folder: str, step_count: int | None = None) -> dict:
    """
    Return the V3 workflow for a folder.
    If step_count is given, (re)creates the workflow to match that
    step count — this lets the user's 2-step/4-step choice take effect
    even if a workflow already existed for the folder.
    If step_count is omitted, reuses the existing workflow, or defaults
    to the 2-step template.
    """
    existing = get_workflow(folder)

    if step_count is not None:
        if existing and existing.get("version") == 3 and existing.get("step_count") == step_count:
            return existing
        fresh = build_workflow(step_count)
        save_workflow(folder, fresh)
        return fresh

    if existing and existing.get("version") == 3:
        return existing

    fresh = build_workflow(2)
    save_workflow(folder, fresh)
    return fresh


def _safe_name(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in name)
    safe = safe.strip(" ._-")
    return safe or "file"


def resolve_step_folders(
    watched_folder: str,
    workflow: dict,
    source_stem: str | None = None,
) -> dict[str, str]:
    """
    Build output folders for the given workflow.

    If source_stem is provided, step folders are grouped inside a
    per-file folder such as 'manual-workflow'. Originals are archived
    separately in the watched folder's shared 'source' directory.
    """
    base = Path(watched_folder)
    workflow_root = base
    if source_stem:
        workflow_root = base / f"{_safe_name(source_stem)}-workflow"

    folders = {
        "WorkflowRoot": str(workflow_root),
        "Source": str(base / "source"),
    }
    for s in workflow.get("steps", []):
        dirname = f"{s['step']:02d}_{s['name']}"
        folders[s["name"]] = str(workflow_root / dirname)
    return folders


def list_folders() -> list[dict]:
    """Return all configured folders with their workflow names."""
    data = load_all()
    return [
        {'path': path, 'name': cfg.get('name', Path(path).name)}
        for path, cfg in data.items()
    ]
