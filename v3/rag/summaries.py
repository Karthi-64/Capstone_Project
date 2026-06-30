# v3/rag/summaries.py — LLM-generated knowledge summary artifacts

import hashlib
import json
from pathlib import Path

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"


def _folder_key(folder: str) -> str:
    resolved = str(Path(folder).resolve())
    return hashlib.sha256(resolved.encode()).hexdigest()[:16]


def summary_path_for(folder: str, source_stem: str) -> Path:
    return KNOWLEDGE_ROOT / _folder_key(folder) / "summaries" / f"{source_stem}.json"


def save_summary(folder: str, source_stem: str, summary: dict) -> str:
    path = summary_path_for(folder, source_stem)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return str(path.resolve())


def load_summary(folder: str, source_stem: str) -> dict | None:
    path = summary_path_for(folder, source_stem)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
