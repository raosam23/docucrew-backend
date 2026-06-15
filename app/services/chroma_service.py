from typing import Any, Dict, List

import chromadb
from chromadb import Collection

from app.core.config import settings

chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)

def get_or_create_collection(collection_id: str) -> Collection:
    """Get or create a ChromaDB collection"""
    return chroma_client.get_or_create_collection(
        name=collection_id,
        metadata={"hnsw:space": "cosine"}
    )

def add_chunks(collection_id: str, chunks: List[Dict[str, Any]]) -> None:
    """Add chunks to a ChromaDB collection"""
    collection = get_or_create_collection(collection_id)
    documents = [chunk["text"] for chunk in chunks]
    metadatas = [chunk["metadata"] for chunk in chunks]
    ids = [f"{chunk['metadata']['doc_id']}_{chunk['metadata']['chunk_index']}" for chunk in chunks]
    collection.add(documents=documents, metadatas=metadatas, ids=ids)

def search(collection_id: str, query: str, top_k: int = 8) -> List[Dict[str, Any]]:
    """Search a ChromaDB collection"""
    collection = get_or_create_collection(collection_id)
    results = collection.query(query_texts=[query], n_results=top_k)
    output = []
    if results["documents"] is not None:
        for it in range(len(results["documents"][0])):
            output.append({
                "text": results["documents"][0][it],
                "metadata": results["metadatas"][0][it] if results["metadatas"] is not None else None,
                "distance": results["distances"][0][it] if results["distances"] is not None else None
            })
    return output

def delete_collection(collection_id: str) -> None:
    """Delete a ChromaDB collection"""
    chroma_client.delete_collection(collection_id)

def delete_chunks_by_doc_id(collection_id: str, doc_id: str) -> None:
    """Delete chunks from a ChromaDB collection by doc_id"""
    collection = get_or_create_collection(collection_id)
    collection.delete(where={"doc_id": doc_id})
