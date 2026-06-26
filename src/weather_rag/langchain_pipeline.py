"""
Optional LangChain/Chroma upgrade path.

The default demo runs without third-party dependencies so it can be opened in
an interview environment. This module documents the production-style swap:
replace LocalVectorStore with Chroma and wire a LangChain retriever/LLM chain.
"""

from __future__ import annotations

from pathlib import Path


def build_chroma_retriever(docs_dir: Path, persist_dir: Path):
    try:
        from langchain_chroma import Chroma
        from langchain_community.document_loaders import DirectoryLoader, TextLoader
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError as exc:  # pragma: no cover - optional dependency path.
        raise RuntimeError("请先执行 pip install -r requirements.txt") from exc

    loader = DirectoryLoader(
        str(docs_dir),
        glob="*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=80)
    chunks = splitter.split_documents(docs)
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    vector_db = Chroma.from_documents(chunks, embeddings, persist_directory=str(persist_dir))
    return vector_db.as_retriever(search_kwargs={"k": 4})
