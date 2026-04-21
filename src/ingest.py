"""
Main ingestion script to load all notes into the vector store
"""
from pathlib import Path
from typing import List
from models import Note
from notion_parser import NotionParser
from keep_parser import KeepParser
from kindle_parser import KindleParser
from lightweight_vector_store import VectorStore
from langdetect import detect, LangDetectException


def detect_language(text: str) -> str:
    """Detect language of text"""
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def ingest_all(data_directory: Path) -> VectorStore:
    """
    Ingest all notes from the data directory
    
    Expected structure:
    data_directory/
        notion/
            *.md
        keep/
            *.json
        kindle/
            *.txt
    """
    all_notes: List[Note] = []
    
    # Parse Notion notes
    notion_dir = data_directory / "notion"
    if notion_dir.exists():
        print(f"\nParsing Notion notes from {notion_dir}...")
        notion_notes = NotionParser.parse_directory(notion_dir)
        print(f"Found {len(notion_notes)} Notion notes")
        all_notes.extend(notion_notes)
    
    # Parse Google Keep notes
    keep_dir = data_directory / "keep"
    if keep_dir.exists():
        print(f"\nParsing Google Keep notes from {keep_dir}...")
        keep_notes = KeepParser.parse_directory(keep_dir)
        print(f"Found {len(keep_notes)} Keep notes")
        all_notes.extend(keep_notes)
    
    # Parse Kindle clippings
    #kindle_file = data_directory / "kindle" / "my_clippings.txt"
    kindle_dir = data_directory / "kindle"
    if kindle_dir.exists():
        print(f"\nParsing Kindle clippings from {kindle_dir}...")
        kindle_notes = KindleParser.parse_directory(kindle_dir)
        print(f"Found {len(kindle_notes)} Kindle highlights")
        all_notes.extend(kindle_notes)
    
    # Detect language for each note
    print("\nDetecting languages...")
    for note in all_notes:
        note.language = detect_language(note.content)
    
    # Initialize vector store
    print("\nInitializing vector store...")
    vector_store = VectorStore()
    
    # Add all notes to vector store
    if all_notes:
        vector_store.add_notes(all_notes)
        
        # Print statistics
        stats = vector_store.get_stats()
        print(f"\n✓ Ingestion complete!")
        print(f"Total notes in database: {stats['total_notes']}")
        
        # Show breakdown by source
        sources = {}
        languages = {}
        for note in all_notes:
            sources[note.source.value] = sources.get(note.source.value, 0) + 1
            if note.language:
                languages[note.language] = languages.get(note.language, 0) + 1
        
        print("\nBreakdown by source:")
        for source, count in sources.items():
            print(f"  {source}: {count}")
        
        print("\nBreakdown by language:")
        for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
            print(f"  {lang}: {count}")
    else:
        print("\n⚠ No notes found to ingest")
    
    return vector_store


if __name__ == "__main__":
    # For testing, use the uploads directory
    data_dir = Path("/home/cairo/code/second-brain-mvp/data/processed")
    
    # Create a simple structure
    import shutil
    test_data = Path("/home/cairo/code/second-brain-mvp/data/raw")
    test_data.mkdir(parents=True, exist_ok=True)
    
    # Copy files to organized structure
    notion_dir = test_data / "notion"
    keep_dir = test_data / "keep"
    kindle_dir = test_data / "kindle"
    
    notion_dir.mkdir(exist_ok=True)
    keep_dir.mkdir(exist_ok=True)
    kindle_dir.mkdir(exist_ok=True)
    
    # Copy Notion files
    for md_file in data_dir.glob("*.md"):
        shutil.copy(md_file, notion_dir)
    
    # Copy Keep files
    for json_file in data_dir.glob("*.json"):
        shutil.copy(json_file, keep_dir)
    
    # Copy Kindle file
    kindle_source = data_dir / "*.txt"
    if kindle_source.exists():
        shutil.copy(kindle_source, kindle_dir)
    
    # Now ingest
    vector_store = ingest_all(test_data)
