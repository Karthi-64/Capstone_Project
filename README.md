# FolderGuardian

FolderGuardian is a desktop real-time file monitoring and document automation system built with Python. It watches configured folders for incoming files, lets you allow or deny them through a Guardian popup, then runs an agentic **ingest → generate** pipeline powered by LangChain, LangGraph, and RAG.

## Version 3 Highlights

- **Real-time monitoring** with Watchdog
- **Allow / Deny popup** for incoming files
- **2-step LangGraph pipeline**
  1. **Ingest** — read the document, build a vector knowledge base, create a RAG summary
  2. **Generate** — retrieve knowledge and produce an automated DOCX report
- **Supported inputs:** TXT, MD, CSV, JSON, PDF, DOCX, XLSX
- **Local RAG storage** via Chroma + HuggingFace embeddings
- **LLM provider:** Groq (`llama-3.1-8b-instant`)

## Architecture

```
Incoming file
     ↓
Guardian popup (Allow / Deny)
     ↓ Allow
Node 1: Ingest
  • LangChain document loaders
  • Chunk + embed → Chroma
  • LLM summary → knowledge/.../summaries/*.json
  • Archive source → Source/
     ↓
Node 2: Generate
  • RAG retrieval per section
  • LLM writes section content
  • Output → Generated/{title}.docx
```

### Project Layout

```
File_Monitoring_System/
├── main.py              # Entry point, watchdog + popup dispatcher
├── agent.py             # V3 pipeline wrapper
├── popup.py             # Guardian allow/deny UI
├── file_info.py         # File metadata helpers
├── workflow_store.py    # Per-folder V3 workflow config
├── workflows.json       # Persisted workflow settings (gitignored)
├── requirements.txt
├── v3/
│   ├── pipeline.py      # Public pipeline entry
│   ├── graph.py         # LangGraph state machine
│   ├── llm.py           # Groq / LangChain LLM setup
│   ├── state.py         # Pipeline state schema
│   ├── nodes/           # Ingest + generate nodes
│   ├── tools/           # Document readers + DOCX writer
│   └── rag/             # Chroma store + summary artifacts
└── knowledge/           # Vector DB + RAG summaries (gitignored)
```

## Requirements

- Python 3.13+
- Groq API key

## Setup

```bash
cd File_Monitoring_System
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Set your Groq API key:

```bash
export GROQ_API_KEY="your-groq-api-key"
```

Optional:

```bash
export GROQ_MODEL="llama-3.1-8b-instant"
```

## Usage

Watch the default folder:

```bash
python main.py
```

Watch one or more custom folders (up to 4):

```bash
python main.py /path/to/folder1 /path/to/folder2
```

### What Happens When a File Arrives

1. FolderGuardian detects the new file.
2. The Guardian popup appears with **Allow / Deny**.
3. If you **Allow**, the V3 pipeline runs:
   - Original file is moved to `Source/`
   - RAG summary is saved under `knowledge/`
   - Generated report is saved under `Generated/`
4. If you **Deny**, the file is removed or returned to its origin.

### Output Folders (per watched folder)

| Folder | Contents |
|---|---|
| `Source/` | Archived originals after ingest |
| `Generated/` | Automated DOCX reports |
| `knowledge/` | Chroma index + JSON summaries |

## Workflow Configuration

Each watched folder gets a V3 workflow stored in `workflows.json`:

```json
{
  "/path/to/watched_folder": {
    "name": "Document Processing Pipeline",
    "version": 3,
    "steps": [
      { "step": 1, "name": "Ingest", "description": "..." },
      { "step": 2, "name": "Generate", "description": "..." }
    ],
    "generation_template": {
      "output_type": "docx",
      "default_title": "Automated Summary Report",
      "sections": [
        "Overview",
        "Key Procedures",
        "Important Details",
        "Action Items"
      ]
    }
  }
}
```

Edit `generation_template.sections` to customize the generated report structure.

## Run the Pipeline Directly

For testing without the popup:

```python
from v3.pipeline import run_pipeline

result = run_pipeline("/path/to/manual.pdf", "/path/to/watched_folder")
print(result)
```

## End-to-End Test

A sample manual is included at `watched_folder/sample_pump_manual.txt`.

Run the full live pipeline test (requires `GROQ_API_KEY`):

```bash
export GROQ_API_KEY="your-groq-api-key"
python scripts/e2e_test.py
```

The test will:

1. Ingest the sample pump manual
2. Build the RAG summary under `knowledge/`
3. Archive the source to `Source/`
4. Generate a DOCX report under `Generated/`
5. Print pass/fail checks

## Security Notes

- Never commit API keys, `.env`, or local runtime data.
- `workflows.json`, `knowledge/`, and `.env` are gitignored.
- Always load the Groq key from the environment:

```python
API_KEY = os.environ.get("GROQ_API_KEY", "")
```

## Troubleshooting

| Issue | Likely cause |
|---|---|
| `GROQ_API_KEY not set` | Export the env var before running |
| `V3 pipeline unavailable` | Run `pip install -r requirements.txt` |
| Slow first run | Embedding model download on first ingest |
| Empty generated report | Source file had no readable text |

## Version History

| Tag | Description |
|---|---|
| **v1.0** | Real-time monitoring, allow/deny popup, quarantine flow |
| **v2.0** | AI workflow generation and automatic folder classification |
| **v3.0** | Agentic LangGraph pipeline with RAG ingest and DOCX generation |

## License

Internal / project use — update as needed.
