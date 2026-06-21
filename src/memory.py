import hashlib
from typing import Optional
from pathlib import Path
import chromadb
import zlib
import re
from chromadb import Documents, EmbeddingFunction, Embeddings
import os

EN_MODEL   = "all-MiniLM-L6-v2"
PTBR_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

MODEL_FOR_LANG = {
    "EN":   EN_MODEL,
    "PTBR": PTBR_MODEL,
}

COLLECTION_FOR_LANG = {
    "EN":   "slm_memory_en",
    "PTBR": "slm_memory_ptbr",
}

def _is_model_cached(model_name: str) -> bool:
    cache_dir   = Path.home() / ".cache" / "huggingface" / "hub"
    cached_name = f"models--sentence-transformers--{model_name.replace('/', '--')}"
    return (cache_dir / cached_name).exists()

_en_cached   = _is_model_cached(EN_MODEL)
_ptbr_cached = _is_model_cached(PTBR_MODEL)

if _en_cached and _ptbr_cached:
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"]  = "1"
    print("Both embedding models loaded from local cache.")
else:
    missing = [m for m, ok in [(EN_MODEL, _en_cached), (PTBR_MODEL, _ptbr_cached)] if not ok]
    print(f"Downloading embedding model(s): {', '.join(missing)}")

from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
import pymupdf as pdf

_loaded_transformers: dict = {}
_collection_cache:    dict = {}

class SentenceTransformerEmbeddings(EmbeddingFunction):
    def __init__(self, model_name: str = EN_MODEL):
        if model_name not in _loaded_transformers:
            _loaded_transformers[model_name] = SentenceTransformer(model_name)
        self.model = _loaded_transformers[model_name]

    def __call__(self, input: Documents) -> Embeddings:
        return self.model.encode(input, convert_to_numpy=True).tolist()

def get_collection(db_path: str = "./chroma_db", collection_name: str = None, lang: str = "EN") -> chromadb.Collection:
    lang      = lang.upper()
    model_name = MODEL_FOR_LANG.get(lang, EN_MODEL)
    coll_name  = collection_name or COLLECTION_FOR_LANG.get(lang, "slm_memory_en")
    cache_key  = f"{db_path}::{coll_name}"

    if cache_key in _collection_cache:
        return _collection_cache[cache_key]

    client    = chromadb.PersistentClient(path=db_path)
    embed_fn  = SentenceTransformerEmbeddings(model_name)
    collection = client.get_or_create_collection(
        name=coll_name,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"}
    )
    _collection_cache[cache_key] = collection
    return collection

# Some chunk verification functions to avoid storing meaningless garbage
def information_density(text: str) -> float:
    """
    Compression ratio as a proxy for information density.
    Low ratio = repetitive/sparse = likely noise.
    High ratio = dense, varied content = likely useful.
    """
    encoded    = text.encode("utf-8")
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

def is_valid_chunk(text: str, min_density: float = 0.55, min_diversity: float = 0.40, min_avg_sentence: float = 5.0) -> bool:
    if len(text.split()) < 15:
        return False

    density  = information_density(text)
    diversity = lexical_diversity(text)
    avg_sent  = avg_sentence_length(text)

    if density   < min_density:      return False  # compresses too well = repetitive/empty
    if diversity < min_diversity:    return False  # too many repeated words
    if avg_sent  < min_avg_sentence: return False  # sentence fragments, not prose

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
    return [
        {"text": doc, "metadata": meta, "score": 1 - dist}
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        )
    ]

# Receive and extract PDF content
def pdf_ingest(collection: chromadb.Collection, pdf_path: str, source_name: Optional[str] = None, extra_metadata: Optional[dict] = None,
               min_density: float = 0.55, min_diversity: float = 0.40, min_avg_sentence: float = 5.0):
    source   = source_name or pdf_path
    doc      = pdf.open(pdf_path)
    splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)

    for page_num, page in enumerate(doc, start=1):
        page_text = page.get_text("text").strip()
        if not page_text:
            continue
        for chunk_idx, chunk in enumerate(splitter.split_text(page_text)):
            chunk_id = hashlib.md5(f"{source}::{page_num}::{chunk_idx}".encode()).hexdigest()

            if not is_valid_chunk(chunk, min_density=min_density, min_diversity=min_diversity, min_avg_sentence=min_avg_sentence):
                continue

            metadata = {
                "source":      source,
                "page":        page_num,
                "chunk_index": chunk_idx,
            }
            if extra_metadata:
                metadata.update(extra_metadata)

            store(collection=collection, text=chunk, metadata=metadata, doc_id=chunk_id)

    doc.close()
