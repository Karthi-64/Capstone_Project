# agent.py ─ FolderGuardian AI workflow agent

import json
import os
import threading
from pathlib import Path

from file_info import get_file_info
from workflow_store import (
    get_workflow,
    save_workflow
)

TIMEOUT = 15
API_KEY = os.environ.get("GROQ_API_KEY", "")

MODEL = "llama-3.1-8b-instant"

_SYSTEM = """
You are a workflow classification assistant.

You will be given information about an incoming file and optionally an existing workflow.

You MUST respond ONLY with valid JSON.

If a workflow exists:

{
  "workflow_exists": true,
  "workflow_name": "<workflow>",
  "suggested_step": 1,
  "step_name": "<step>",
  "reason": "<reason>",
  "suggested_workflow": null
}

If no workflow exists:

{
  "workflow_exists": false,
  "workflow_name": null,
  "suggested_step": 1,
  "step_name": "<step>",
  "reason": "<reason>",
  "suggested_workflow": {
    "name": "<workflow name>",
    "steps": [
      {
        "step": 1,
        "name": "<step>",
        "description": "<description>"
      },
      {
        "step": 2,
        "name": "<step>",
        "description": "<description>"
      },
      {
        "step": 3,
        "name": "<step>",
        "description": "<description>"
      },
      {
        "step": 4,
        "name": "<step>",
        "description": "<description>"
      }
    ]
  }
}
""".strip()


def _read_preview(filepath: str, max_chars: int = 1000) -> str:

    ext = Path(filepath).suffix.lower()

    if ext in {
        ".txt",
        ".md",
        ".csv",
        ".json",
        ".xml",
        ".html"
    }:
        try:
            return Path(filepath).read_text(
                encoding="utf-8",
                errors="ignore"
            )[:max_chars]
        except Exception:
            pass

    return ""


def _create_workflow_folders(
    folder: str,
    workflow: dict
):

    for step in workflow.get("steps", []):

        folder_name = step.get("name")

        if not folder_name:
            continue

        Path(
            folder,
            folder_name
        ).mkdir(
            parents=True,
            exist_ok=True
        )


def _lookup_target_folder(
    folder: str,
    workflow: dict,
    step_number: int
):

    for step in workflow.get("steps", []):

        if step.get("step") == step_number:

            return str(
                Path(folder) /
                step.get("name")
            )

    return None


def analyse_file(
    filepath: str,
    folder: str
) -> dict:

    if not API_KEY:
        return {
            "error":
            "GROQ_API_KEY not set"
        }

    try:

        info = get_file_info(filepath)

        if info.get("size_raw", 0) == 0:

            return {
                "empty_file": True,
                "file": info["name"]
            }

    except Exception:
        pass

    result = {}
    error = {}

    def _call():

        nonlocal result
        nonlocal error

        try:

            from groq import Groq

            client = Groq(
                api_key=API_KEY
            )

            info = get_file_info(filepath)

            workflow = get_workflow(folder)

            preview = _read_preview(filepath)

            file_desc = (
                f"File name: {info['name']}\n"
                f"File type: {info['type']}\n"
                f"Extension: {info['ext']}\n"
                f"Size: {info['size']}\n"
            )

            if preview:

                file_desc += (
                    f"\nContent Preview:\n"
                    f"{preview}\n"
                )

            if workflow:

                wf_desc = (
                    f"Workflow name: "
                    f"{workflow.get('name')}\n\n"
                )

                for step in workflow.get(
                    "steps",
                    []
                ):

                    wf_desc += (
                        f"Step {step['step']}: "
                        f"{step['name']} - "
                        f"{step.get('description','')}\n"
                    )

                user_msg = (
                    f"{file_desc}\n\n"
                    f"Existing Workflow:\n"
                    f"{wf_desc}"
                )

            else:

                user_msg = (
                    f"{file_desc}\n\n"
                    f"No workflow exists.\n"
                    f"Generate a practical "
                    f"4-step workflow."
                )

            response = (
                client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": _SYSTEM
                        },
                        {
                            "role": "user",
                            "content": user_msg
                        }
                    ],
                    temperature=0.2,
                    max_tokens=700
                )
            )

            raw = (
                response
                .choices[0]
                .message.content
                .strip()
            )

            if raw.startswith("```"):

                parts = raw.split("```")

                raw = (
                    parts[1]
                    if len(parts) > 1
                    else raw
                )

                if raw.startswith("json"):
                    raw = raw[4:]

            result = json.loads(
                raw.strip()
            )

            # Auto-save workflow
            if (
                not workflow
                and result.get(
                    "suggested_workflow"
                )
            ):

                save_workflow(
                    folder,
                    result[
                        "suggested_workflow"
                    ]
                )

                _create_workflow_folders(
                    folder,
                    result[
                        "suggested_workflow"
                    ]
                )

                workflow = result[
                    "suggested_workflow"
                ]

            else:

                workflow = get_workflow(
                    folder
                )

            if workflow:

                target = _lookup_target_folder(
                    folder,
                    workflow,
                    result.get(
                        "suggested_step",
                        1
                    )
                )

                if target:

                    result[
                        "target_folder"
                    ] = target

        except Exception as e:

            error["message"] = str(e)

    t = threading.Thread(
        target=_call,
        daemon=True
    )

    t.start()

    t.join(
        timeout=TIMEOUT
    )

    if error:

        return {
            "error":
            error["message"]
        }

    if not result:

        return {
            "error":
            "Timeout — Groq did not respond."
        }

    return result