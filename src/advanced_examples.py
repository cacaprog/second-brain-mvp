"""
Advanced Usage Examples for Second Brain MVP

This script demonstrates various ways to interact with your knowledge base.
"""

from lightweight_vector_store import VectorStore
from pathlib import Path
import json

# Initialize vector store
vs = VectorStore()

print("="*70)
print("SECOND BRAIN - ADVANCED USAGE EXAMPLES")
print("="*70)

# Example 1: Basic Search
print("\n1. BASIC SEARCH")
print("-" * 70)
results = vs.search("modelos mentais", n_results=3)
print(f"Found {len(results)} results for 'modelos mentais'")
for r in results:
    print(f"  - {r['metadata']['title'][:50]}... ({r['metadata']['source']})")

# Example 2: Filtered Search (Kindle only)
print("\n2. FILTERED SEARCH - Kindle Only")
print("-" * 70)
results = vs.search(
    "mental models",
    n_results=5,
    filter_dict={"source": "kindle"}
)
print(f"Found {len(results)} Kindle highlights about 'mental models'")
for r in results:
    author = r['metadata'].get('author', 'Unknown')
    print(f"  - {r['metadata']['title'][:40]}... by {author}")

# Example 3: Filtered Search (Notion only)
print("\n3. FILTERED SEARCH - Notion Only")
print("-" * 70)
results = vs.search(
    "modelos",
    n_results=10,
    filter_dict={"source": "notion"}
)
print(f"Found {len(results)} Notion notes")
for r in results:
    tags = r['metadata'].get('tags', [])
    print(f"  - {r['metadata']['title']}")
    if tags:
        print(f"    Tags: {', '.join(tags)}")

# Example 4: Analyzing Your Notes
print("\n4. ANALYZING YOUR NOTES")
print("-" * 70)

# Count by source
sources = {}
languages = {}
authors = {}

for note in vs.notes:
    # Count sources
    source = note.source.value
    sources[source] = sources.get(source, 0) + 1
    
    # Count languages
    if note.language:
        languages[note.language] = languages.get(note.language, 0) + 1
    
    # Count authors (for Kindle)
    if note.source.value == "kindle" and 'author' in note.metadata:
        author = note.metadata['author']
        authors[author] = authors.get(author, 0) + 1

print("\nBy Source:")
for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
    print(f"  {source:10} {count:6,} notes")

print("\nTop 5 Languages:")
for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True)[:5]:
    print(f"  {lang:10} {count:6,} notes")

print("\nTop 10 Most-Highlighted Authors:")
for author, count in sorted(authors.items(), key=lambda x: x[1], reverse=True)[:10]:
    print(f"  {count:4} highlights - {author}")

# Example 5: Finding Related Notes
print("\n5. FINDING RELATED NOTES")
print("-" * 70)

# Pick a random note and find similar ones
import random
random_note = random.choice(vs.notes)
print(f"Starting from: {random_note.title[:60]}...")

related = vs.search(random_note.get_full_text()[:200], n_results=5)
print(f"\nFound {len(related)} related notes:")
for i, r in enumerate(related[1:], 1):  # Skip first (itself)
    print(f"  {i}. {r['metadata']['title'][:50]}... "
          f"({r['metadata']['source']})")

# Example 6: Tag Analysis (for Notion notes)
print("\n6. TAG ANALYSIS")
print("-" * 70)
notion_notes = [n for n in vs.notes if n.source.value == "notion"]
all_tags = []
for note in notion_notes:
    all_tags.extend(note.tags)

if all_tags:
    from collections import Counter
    tag_counts = Counter(all_tags)
    print("Tags in your Notion notes:")
    for tag, count in tag_counts.most_common():
        print(f"  {tag}: {count}")
else:
    print("No tags found in Notion notes")

# Example 7: Temporal Analysis (for dated notes)
print("\n7. TEMPORAL ANALYSIS")
print("-" * 70)
from datetime import datetime
from collections import defaultdict

notes_by_year = defaultdict(int)
for note in vs.notes:
    if note.created_at:
        year = note.created_at.year
        notes_by_year[year] += 1

if notes_by_year:
    print("Notes by year:")
    for year in sorted(notes_by_year.keys()):
        count = notes_by_year[year]
        bar = "█" * (count // 100)
        print(f"  {year}: {count:4,} {bar}")
else:
    print("No date information available")

# Example 8: Content Length Analysis
print("\n8. CONTENT LENGTH ANALYSIS")
print("-" * 70)
lengths = [len(note.content) for note in vs.notes]
import numpy as np

print(f"Total notes: {len(lengths):,}")
print(f"Average length: {np.mean(lengths):.0f} characters")
print(f"Median length: {np.median(lengths):.0f} characters")
print(f"Shortest: {min(lengths)} characters")
print(f"Longest: {max(lengths):,} characters")

# Example 9: Full-Text Search with Context
print("\n9. FULL-TEXT SEARCH WITH CONTEXT")
print("-" * 70)
query = "obstinação"
results = vs.search(query, n_results=3)

print(f"Searching for: '{query}'")
for i, result in enumerate(results, 1):
    content = result['content']
    title = result['metadata']['title']
    
    # Find the query in content (case-insensitive)
    content_lower = content.lower()
    query_lower = query.lower()
    
    if query_lower in content_lower:
        idx = content_lower.find(query_lower)
        # Get context (100 chars before and after)
        start = max(0, idx - 100)
        end = min(len(content), idx + len(query) + 100)
        context = content[start:end]
        
        print(f"\n{i}. {title[:50]}...")
        print(f"   ...{context}...")

# Example 10: Export Search Results
print("\n10. EXPORT SEARCH RESULTS")
print("-" * 70)
query = "mental models"
results = vs.search(query, n_results=10)

# Export to JSON
export_data = {
    "query": query,
    "timestamp": datetime.now().isoformat(),
    "total_results": len(results),
    "results": [
        {
            "title": r['metadata']['title'],
            "source": r['metadata']['source'],
            "content": r['content'][:200] + "...",
            "similarity": r.get('similarity', 0)
        }
        for r in results
    ]
}

export_file = Path("search_results_export.json")
with open(export_file, 'w', encoding='utf-8') as f:
    json.dump(export_data, f, ensure_ascii=False, indent=2)

print(f"Exported search results to: {export_file}")
print(f"Query: '{query}'")
print(f"Results: {len(results)}")

print("\n" + "="*70)
print("✓ All examples complete!")
print("="*70)
