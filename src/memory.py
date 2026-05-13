import hashlib
from datetime import datetime
from typing import Optional
from pathlib import Path
import chromadb
import zlib
import re
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

# Some chunk verification functions to avoid storing meaningless garbage
def information_density(text: str) -> float:
    """
    Compression ratio as a proxy for information density.
    Low ratio = repetitive/sparse = likely noise.
    High ratio = dense, varied content = likely useful.
    """
    encoded = text.encode("utf-8")
    compressed = zlib.compress(encoded, level=9)
    return len(compressed) / len(encoded)

def lexical_diversity(text: str) -> float:
    """
    Ratio of unique words to total words.
    Low diversity = repetitive headers/footers.
    High diversity = actual content.
    """
    words = re.findall(r'\b\w+\b', text.lower())
    if not words:
        return 0.0
    return len(set(words)) / len(words)

def avg_sentence_length(text: str) -> float:
    """
    Headers and footers tend to be very short sentences or fragments.
    Real content has longer, more complete sentences.
    """
    sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
    if not sentences:
        return 0.0
    return sum(len(s.split()) for s in sentences) / len(sentences)

def is_valid_chunk(text : str) -> bool:
    if len(text.split()) < 15:
        return False
    
    density    = information_density(text)
    diversity  = lexical_diversity(text)
    avg_sent   = avg_sentence_length(text)

    if density    < 0.55:   return False   # compresses too well = repetitive/empty
    if diversity  < 0.40:   return False   # too many repeated words
    if avg_sent   < 5.0:    return False   # sentence fragments, not prose

    return True

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

    # print("ingesting PDF...")
    for page_num, page in enumerate(doc, start=1):
        page_text = page.get_text("text").strip()
        if not page_text:
            continue
        for chunk_idx, chunk in enumerate(splitter.split_text(page_text)):
            chunk_id = hashlib.md5(f"{source}::{page_num}::{chunk_idx}".encode()).hexdigest()
            density   = information_density(chunk)
            diversity = lexical_diversity(chunk)
            avg_sent  = avg_sentence_length(chunk)
            valid     = is_valid_chunk(chunk)

            if not valid:
                # print(f"REJECTED [{density:.2f} / {diversity:.2f} / {avg_sent:.1f}]: {chunk[:80]}")
                continue
            
            store(
                collection=collection,
                text=chunk,
                metadata={"source":source, "page":page_num, "chunk_index":chunk_idx},
                doc_id=chunk_id
            )
    doc.close()
