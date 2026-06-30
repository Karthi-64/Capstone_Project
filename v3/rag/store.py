# v3/rag/store.py — local Chroma vector store per watched folder

import hashlib
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[2] / "knowledge"

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
)

_embeddings = None


def _folder_key(folder: str) -> str:
    resolved = str(Path(folder).resolve())
    return hashlib.sha256(resolved.encode()).hexdigest()[:16]


def _persist_dir(folder: str) -> Path:
    return KNOWLEDGE_ROOT / _folder_key(folder) / "chroma"


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_community.embeddings import HuggingFaceEmbeddings

        _embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
        )
    return _embeddings


def _get_vector_store(folder: str):
    from langchain_community.vectorstores import Chroma

    persist_dir = str(_persist_dir(folder))
    return Chroma(
        collection_name=f"fg_{_folder_key(folder)}",
        embedding_function=_get_embeddings(),
        persist_directory=persist_dir,
    )


def index_documents(folder: str, source_id: str, documents: list[Document]) -> int:
    chunks = _splitter.split_documents(documents)
    for chunk in chunks:
        chunk.metadata["source_id"] = source_id

    if not chunks:
        return 0

    store = _get_vector_store(folder)
    store.add_documents(chunks)
    return len(chunks)


def get_retriever(folder: str, source_id: str, k: int = 4):
    store = _get_vector_store(folder)
    return store.as_retriever(
        search_kwargs={
            "k": k,
            "filter": {"source_id": source_id},
        }
    )
