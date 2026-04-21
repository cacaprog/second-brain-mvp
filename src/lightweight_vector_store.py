"""
Lightweight vector store using TF-IDF for semantic search
"""
import pickle
import json
from pathlib import Path
from typing import List, Dict, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from models import Note


class LightweightVectorStore:
    """
    A lightweight vector store using TF-IDF for semantic search.
    Much smaller and faster than embedding-based approaches, perfect for MVP.
    """
    
    def __init__(self, persist_directory: str = None):
        """Initialize the lightweight vector store"""
        if persist_directory is None:
            # Default to project root's data/processed directory
            project_root = Path(__file__).parent.parent
            persist_directory = project_root / "data" / "processed"
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        
        self.notes: List[Note] = []
        self.vectorizer = None
        self.tfidf_matrix = None
        
        # Try to load existing data
        self._load()
    
    def add_notes(self, notes: List[Note]):
        """Add notes to the vector store"""
        if not notes:
            return
        
        print(f"Processing {len(notes)} notes...")
        
        # Add to notes list
        self.notes.extend(notes)
        
        # Prepare documents
        documents = [note.get_full_text() for note in self.notes]
        
        # Create TF-IDF vectorizer with multilingual support
        print("Creating TF-IDF vectors...")
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),  # unigrams and bigrams
            min_df=1,
            stop_words=None,  # Keep all words for multilingual support
            lowercase=True,
            token_pattern=r'(?u)\b\w+\b'  # Unicode word boundaries
        )
        
        # Fit and transform
        self.tfidf_matrix = self.vectorizer.fit_transform(documents)
        
        print(f"Added {len(notes)} notes to vector store")
        print(f"Total notes: {len(self.notes)}")
        
        # Save
        self._save()
    
    def search(
        self,
        query: str,
        n_results: int = 10,
        filter_dict: Dict[str, Any] = None
    ) -> List[Dict]:
        """
        Search for similar notes using cosine similarity
        
        Args:
            query: Search query
            n_results: Number of results to return
            filter_dict: Optional metadata filters (e.g., {"source": "notion"})
        
        Returns:
            List of search results with metadata
        """
        if not self.notes or self.vectorizer is None:
            return []
        
        # Transform query to TF-IDF vector
        query_vector = self.vectorizer.transform([query])
        
        # Calculate cosine similarities
        similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
        
        # Get indices of filtered notes if filter is specified
        valid_indices = list(range(len(self.notes)))
        if filter_dict:
            valid_indices = []
            for i, note in enumerate(self.notes):
                match = True
                for key, value in filter_dict.items():
                    if key == "source":
                        if note.source.value != value:
                            match = False
                            break
                    elif key in note.metadata:
                        if note.metadata[key] != value:
                            match = False
                            break
                if match:
                    valid_indices.append(i)
        
        # Get top N results from valid indices
        valid_similarities = [(i, similarities[i]) for i in valid_indices]
        valid_similarities.sort(key=lambda x: x[1], reverse=True)
        top_indices = [i for i, _ in valid_similarities[:n_results]]
        
        # Format results
        results = []
        for idx in top_indices:
            note = self.notes[idx]
            similarity = similarities[idx]
            
            results.append({
                'id': note.id,
                'content': note.get_full_text(),
                'metadata': note.to_dict(),
                'distance': 1 - similarity,  # Convert to distance (lower is better)
                'similarity': similarity
            })
        
        return results
    
    def get_stats(self) -> Dict:
        """Get statistics about the vector store"""
        return {
            "total_notes": len(self.notes),
            "vocabulary_size": len(self.vectorizer.vocabulary_) if self.vectorizer else 0
        }
    
    def clear(self):
        """Clear all data"""
        self.notes = []
        self.vectorizer = None
        self.tfidf_matrix = None
        self._save()
    
    def _save(self):
        """Save the vector store to disk"""
        # Save notes as JSON
        notes_data = [note.to_dict() for note in self.notes]
        with open(self.persist_directory / "notes.json", 'w', encoding='utf-8') as f:
            json.dump(notes_data, f, ensure_ascii=False, indent=2)
        
        # Save vectorizer and matrix
        if self.vectorizer and self.tfidf_matrix is not None:
            with open(self.persist_directory / "vectorizer.pkl", 'wb') as f:
                pickle.dump(self.vectorizer, f)
            with open(self.persist_directory / "tfidf_matrix.pkl", 'wb') as f:
                pickle.dump(self.tfidf_matrix, f)
        
        print(f"Saved to {self.persist_directory}")
    
    def _load(self):
        """Load the vector store from disk"""
        notes_file = self.persist_directory / "notes.json"
        vectorizer_file = self.persist_directory / "vectorizer.pkl"
        matrix_file = self.persist_directory / "tfidf_matrix.pkl"
        
        if notes_file.exists():
            print(f"Loading existing data from {self.persist_directory}...")
            
            # Load notes
            with open(notes_file, 'r', encoding='utf-8') as f:
                notes_data = json.load(f)
            
            # Convert back to Note objects
            from models import SourceType
            from datetime import datetime
            
            for note_dict in notes_data:
                note = Note(
                    id=note_dict['id'],
                    title=note_dict['title'],
                    content=note_dict['content'],
                    source=SourceType(note_dict['source']),
                    tags=note_dict['tags'],
                    created_at=datetime.fromisoformat(note_dict['created_at']) if note_dict['created_at'] else None,
                    metadata=note_dict['metadata'],
                    language=note_dict.get('language')
                )
                self.notes.append(note)
            
            # Load vectorizer and matrix
            if vectorizer_file.exists() and matrix_file.exists():
                with open(vectorizer_file, 'rb') as f:
                    self.vectorizer = pickle.load(f)
                with open(matrix_file, 'rb') as f:
                    self.tfidf_matrix = pickle.load(f)
            
            print(f"Loaded {len(self.notes)} notes")


# Alias for backward compatibility
VectorStore = LightweightVectorStore
