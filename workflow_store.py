# workflow_store.py  ─  FolderGuardian  workflow config persistence

import json
from pathlib import Path

STORE_FILE = Path(__file__).parent / 'workflows.json'


def load_all() -> dict:
    if STORE_FILE.exists():
        try:
            return json.loads(STORE_FILE.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def save_all(data: dict):
    STORE_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')


def get_workflow(folder: str) -> dict | None:
    """Return workflow config for a folder, or None if not defined."""
    key = str(Path(folder).resolve())
    return load_all().get(key)


def save_workflow(folder: str, workflow: dict):
    """Persist a workflow config for a folder."""
    data = load_all()
    data[str(Path(folder).resolve())] = workflow
    save_all(data)


def list_folders() -> list[dict]:
    """Return all configured folders with their workflow names."""
    data = load_all()
    return [
        {'path': path, 'name': cfg.get('name', Path(path).name)}
        for path, cfg in data.items()
    ]
