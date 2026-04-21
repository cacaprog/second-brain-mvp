"""
Vector store for semantic search using ChromaDB
"""
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
from pathlib import Path
from models import Note
import json


class VectorStore:
    """Manages the vector database for semantic search"""
    
    def __init__(self, persist_directory: str = "./data/processed/chroma"):
        """Initialize ChromaDB and embedding model"""
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="notes",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Initialize embedding model (multilingual)
        print("Loading embedding model...")
        self.embedding_model = SentenceTransformer('intfloat/multilingual-e5-large')
        print("Model loaded!")
    
    def add_notes(self, notes: List[Note]):
        """Add notes to the vector store"""
        if not notes:
            return
        
        print(f"Processing {len(notes)} notes...")
        
        # Prepare data
        ids = [note.id for note in notes]
        documents = [note.get_full_text() for note in notes]
        metadatas = [note.to_dict() for note in notes]
        
        # For multilingual-e5, we should add instruction prefix
        # Using passage: prefix for documents to be stored
        prefixed_docs = [f"passage: {doc}" for doc in documents]
        
        # Generate embeddings
        print("Generating embeddings...")
        embeddings = self.embedding_model.encode(
            prefixed_docs,
            show_progress_bar=True,
            convert_to_numpy=True
        ).tolist()
        
        # Add to ChromaDB in batches
        batch_size = 100
        for i in range(0, len(notes), batch_size):
            end_idx = min(i + batch_size, len(notes))
            self.collection.add(
                ids=ids[i:end_idx],
                embeddings=embeddings[i:end_idx],
                documents=documents[i:end_idx],
                metadatas=metadatas[i:end_idx]
            )
        
        print(f"Added {len(notes)} notes to vector store")
    
    def search(
        self, 
        query: str, 
        n_results: int = 10,
        filter_dict: Dict[str, Any] = None
    ) -> List[Dict]:
        """
        Search for similar notes
        
        Args:
            query: Search query
            n_results: Number of results to return
            filter_dict: Optional metadata filters (e.g., {"source": "notion"})
        
        Returns:
            List of search results with metadata
        """
        # Add query prefix for multilingual-e5
        prefixed_query = f"query: {query}"
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode(
            prefixed_query,
            convert_to_numpy=True
        ).tolist()
        
        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_dict
        )
        
        # Format results
        formatted_results = []
        if results and results['ids']:
            for i, doc_id in enumerate(results['ids'][0]):
                formatted_results.append({
                    'id': doc_id,
                    'content': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
        
        return formatted_results
    
    def get_stats(self) -> Dict:
        """Get statistics about the vector store"""
        count = self.collection.count()
        return {
            "total_notes": count,
            "collection_name": self.collection.name
        }
    
    def clear(self):
        """Clear all data from the collection"""
        self.client.delete_collection(name="notes")
        self.collection = self.client.get_or_create_collection(
            name="notes",
            metadata={"hnsw:space": "cosine"}
        )
