import hashlib
from datetime import datetime
from typing import Optional
from pathlib import Path
import chromadb
from chromadb import Documents, EmbeddingFunction, Embeddings

#Avoid redownloading the model if it already exists on huggingface cache
import os
model_name = "all-MiniLM-L6-v2"
cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
cached_name = f"models--sentence-transformers--{model_name.replace('/', '--')}"
is_cached = (cache_dir / cached_name).exists()
if is_cached:
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    print(f"Loading '{model_name}' from local cache.")
else:
    print(f"'{model_name}' not cached — downloading once...")

from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
import pymupdf as pdf

# Controls how the raw text gets converted to vectors
class SentenceTransformerEmbeddings(EmbeddingFunction):
    def __init__(self):
        self.model = SentenceTransformer(model_name)

    def __call__(self, input):
        return self.model.encode(input, convert_to_numpy=True).tolist()

# Connect to ChromaDB and create a collection
def get_collection(db_path: str = "./chroma_db", collection_name : str = "slm_memory") -> chromadb.Collection:
    client = chromadb.PersistentClient(path=db_path)
    embed_fn = SentenceTransformerEmbeddings()

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embed_fn,
        metadata={"hnsw:space":"cosine"} # cosine distance for text similarity
    )
    return collection

# Store plain text in the collection
def store(collection: chromadb.Collection, text: str, metadata: dict, doc_id: str):
    collection.upsert(
        documents=[text],
        metadatas=[metadata],
        ids=[doc_id]
    )

# Query the collection
def recall(collection: chromadb.Collection, query: str, n_results: int = 5, where: Optional[dict] = None) -> list[dict]:
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where
    )
    return[
        {"text":doc, "metadata": meta, "score": 1 - dist}
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        )
    ]

# Receive and extract PDF content
def pdf_ingest(collection: chromadb.Collection, pdf_path: str, source_name: Optional[str] = None):
    source = source_name or pdf_path
    doc = pdf.open(pdf_path)
    splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)

    for page_num, page in enumerate(doc, start=1):
        page_text = page.get_text("text").strip()
        if not page_text:
            continue
        for chunk_idx, chunk in enumerate(splitter.split_text(page_text)):
            chunk_id = hashlib.md5(f"{source}::{page_num}::{chunk_idx}".encode()).hexdigest()
            store(
                collection=collection,
                text=chunk,
                metadata={"source":source, "page":page_num, "chunk_index":chunk_idx},
                doc_id=chunk_id
            )

    doc.close()
