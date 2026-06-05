"""
Corpus ingestion: load resume + about_me + GitHub content → FAISS index.

Run once (or after corpus changes):
    python -c "from persona.ingest import build_index; build_index()"
"""

import os
import json
import pickle
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

RESUME_PATH = os.getenv("RESUME_PATH", "corpus/resume.pdf")
ABOUT_ME_PATH = os.getenv("ABOUT_ME_PATH", "corpus/about_me.md")
GITHUB_DIR = Path("corpus/github")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "corpus/faiss_index")

EMBED_MODEL = "multi-qa-MiniLM-L6-cos-v1"  # asymmetric Q->doc retrieval, better for QA

CHUNK_SIZE = 500
CHUNK_OVERLAP = 80


def _load_resume() -> List[Document]:
    path = Path(RESUME_PATH)
    if not path.exists():
        print(f"[ingest] WARNING: resume not found at {path}")
        return []
    docs = PyPDFLoader(str(path)).load()
    for d in docs:
        d.metadata["source"] = "resume"
    return docs


def _load_about_me() -> List[Document]:
    path = Path(ABOUT_ME_PATH)
    if not path.exists():
        print(f"[ingest] WARNING: about_me not found at {path}")
        return []
    docs = TextLoader(str(path), encoding="utf-8").load()
    for d in docs:
        d.metadata["source"] = "about_me"
    return docs


def _load_github_corpus() -> List[Document]:
    """Load all .md and .txt files under corpus/github/."""
    docs = []
    if not GITHUB_DIR.exists():
        print("[ingest] WARNING: corpus/github/ not found — run scripts/ingest_github.py first")
        return docs

    for fpath in sorted(GITHUB_DIR.rglob("*")):
        if fpath.suffix.lower() not in {".md", ".txt"}:
            continue
        try:
            text = fpath.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                continue
            # derive repo name from directory structure: corpus/github/<repo>/...
            parts = fpath.relative_to(GITHUB_DIR).parts
            repo = parts[0] if parts else fpath.stem
            docs.append(Document(
                page_content=text,
                metadata={"source": f"github:{repo}", "file": str(fpath.relative_to(GITHUB_DIR))},
            ))
        except Exception as e:
            print(f"[ingest] WARNING: could not load {fpath}: {e}")
    return docs


def _chunk(docs: List[Document]) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents(docs)


def build_index(force: bool = False) -> FAISS:
    """Build (or load) FAISS index from corpus. Returns the vectorstore."""
    index_path = Path(FAISS_INDEX_PATH)

    if index_path.exists() and not force:
        print(f"[ingest] Loading existing index from {index_path}")
        embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
        return FAISS.load_local(str(index_path), embeddings, allow_dangerous_deserialization=True)

    print("[ingest] Building index from corpus...")

    raw: List[Document] = []
    raw += _load_resume()
    raw += _load_about_me()
    raw += _load_github_corpus()

    if not raw:
        raise RuntimeError(
            "No corpus documents found. Add resume.pdf and about_me.md to corpus/, "
            "then run scripts/ingest_github.py."
        )

    chunks = _chunk(raw)
    print(f"[ingest] {len(raw)} source docs -> {len(chunks)} chunks")

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    store = FAISS.from_documents(chunks, embeddings)
    index_path.mkdir(parents=True, exist_ok=True)
    store.save_local(str(index_path))
    print(f"[ingest] Index saved to {index_path}")
    return store


if __name__ == "__main__":
    build_index(force=True)
