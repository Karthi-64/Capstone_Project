# v3/llm.py — Groq LLM via LangChain

import os

API_KEY = os.environ.get("GROQ_API_KEY", "")
MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

_SMALL_DOC_CHAR_LIMIT = 12_000


def get_llm(temperature: float = 0.2):
    if not API_KEY:
        raise ValueError(
            "GROQ_API_KEY not set. Export it before running: "
            "export GROQ_API_KEY=\"your-groq-api-key\""
        )

    from langchain_groq import ChatGroq

    return ChatGroq(
        api_key=API_KEY,
        model=MODEL,
        temperature=temperature,
    )


def emit(state: dict, message: str):
    """
    Push a progress message to the UI, if a progress_queue was passed
    into the pipeline state. Safe no-op if there's no queue (e.g. when
    running the pipeline directly without the popup UI).
    """
    q = state.get("progress_queue")
    if q is not None:
        try:
            q.put(message)
        except Exception:
            pass
