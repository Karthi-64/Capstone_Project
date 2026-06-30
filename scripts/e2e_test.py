#!/usr/bin/env python3
"""Live end-to-end test for FolderGuardian V3 pipeline."""

import json
import os
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WATCHED = PROJECT_ROOT / "watched_folder"
SAMPLE_MANUAL = WATCHED / "sample_pump_manual.txt"


def reset_test_artifacts():
    for sub in ("Source", "Generated"):
        path = WATCHED / sub
        if path.exists():
            shutil.rmtree(path)

    archived = WATCHED / "Source" / SAMPLE_MANUAL.name
    if archived.exists() and not SAMPLE_MANUAL.exists():
        archived.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(archived), str(SAMPLE_MANUAL))


def run_checks(result: dict) -> bool:
    checks: list[tuple[str, bool]] = []

    summary_path = result.get("summary_path")
    if summary_path and Path(summary_path).exists():
        summary = json.loads(Path(summary_path).read_text())
        checks.append(("RAG summary created", True))
        checks.append(("Summary has overview", bool(summary.get("overview"))))
        checks.append(("Summary has procedures", bool(summary.get("procedures"))))
        print("\n--- RAG Summary ---")
        print("Title :", summary.get("title"))
        print("Brief :", summary.get("generation_brief"))
        print("Topics:", summary.get("key_topics"))
    else:
        checks.append(("RAG summary created", False))

    archived = WATCHED / "Source" / SAMPLE_MANUAL.name
    checks.append(("Source file archived", archived.exists()))
    checks.append(("Original removed from root", not SAMPLE_MANUAL.exists()))

    docx_path = result.get("output_docx_path")
    if docx_path and Path(docx_path).exists():
        from docx import Document

        text = "\n".join(p.text for p in Document(docx_path).paragraphs if p.text.strip())
        pump_terms = ["pump", "pressure", "maintenance", "install"]
        found = sum(1 for term in pump_terms if term.lower() in text.lower())
        checks.append(("Generated DOCX created", True))
        checks.append(("DOCX has substantial content", len(text) > 200))
        checks.append(("DOCX references manual topics", found >= 2))
        print("\n--- Generated DOCX ---")
        print("Path  :", docx_path)
        print("Chars :", len(text))
        print("\nExcerpt:")
        print(text[:700])
    else:
        checks.append(("Generated DOCX created", False))

    print("\n" + "=" * 60)
    print("Test Checks")
    print("=" * 60)
    all_ok = True
    for name, ok in checks:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}")
        all_ok = all_ok and ok

    print("\nOVERALL:", "PASS" if all_ok else "FAIL")
    return all_ok


def main() -> int:
    if not os.environ.get("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY is not set.")
        print("Run: export GROQ_API_KEY='your-key'")
        return 1

    if not SAMPLE_MANUAL.exists():
        print(f"ERROR: Sample manual missing: {SAMPLE_MANUAL}")
        return 1

    sys.path.insert(0, str(PROJECT_ROOT))
    reset_test_artifacts()

    print("=" * 60)
    print("FolderGuardian V3 — Live End-to-End Test")
    print("=" * 60)
    print(f"Input : {SAMPLE_MANUAL.name}")
    print(f"Folder: {WATCHED.name}/")
    print()

    from v3.pipeline import run_pipeline

    result = run_pipeline(str(SAMPLE_MANUAL), str(WATCHED))
    print("Pipeline result:")
    print(json.dumps(result, indent=2))

    if result.get("error"):
        print(f"\nFAILED: {result['error']}")
        return 1

    return 0 if run_checks(result) else 1


if __name__ == "__main__":
    raise SystemExit(main())
