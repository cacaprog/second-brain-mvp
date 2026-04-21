"""
Quick test of the search functionality
"""
from lightweight_vector_store import VectorStore

# Load the vector store
print("Loading vector store...")
vs = VectorStore()

# Get stats
stats = vs.get_stats()
print(f"\nTotal notes: {stats['total_notes']}")
print(f"Vocabulary size: {stats['vocabulary_size']}")

# Test searches
test_queries = [
    "modelos mentais",
    "otimismo",
    "mental models",
    "sorte",
]

print("\n" + "="*60)
print("TEST SEARCHES")
print("="*60)

for query in test_queries:
    print(f"\n🔍 Query: '{query}'")
    print("-" * 60)
    
    results = vs.search(query, n_results=3)
    
    if results:
        for i, result in enumerate(results, 1):
            metadata = result['metadata']
            content = result['content'][:150] + "..." if len(result['content']) > 150 else result['content']
            similarity = result.get('similarity', 0)
            
            print(f"\n{i}. [{metadata['source'].upper()}] {metadata['title']}")
            print(f"   Similarity: {similarity:.2%}")
            print(f"   {content}")
    else:
        print("   No results found")

print("\n" + "="*60)
print("✓ Test complete!")
