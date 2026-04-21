# Second Brain MVP 🧠

A minimal viable product for your personal knowledge management system with semantic search across multiple sources.

## Features

✨ **Multi-source support**: Notion, Google Keep, Kindle highlights  
🌍 **Multilingual**: Portuguese, English, French, Spanish  
🔍 **Semantic search**: Find notes by meaning, not just keywords  
⚡ **Local & free**: Runs entirely on your machine, no API costs for embeddings  

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt --break-system-packages
```

### 2. Prepare Your Data

Organize your exported files in `data/raw/`:

```
data/raw/
├── notion/      # Place your .md files here
├── keep/        # Place your .json files here
└── kindle/      # Place your my_clippings.txt here
```

### 3. Ingest Your Notes

```bash
cd src
python ingest.py
```

This will:
- Parse all your notes
- Detect languages
- Generate embeddings
- Store everything in ChromaDB

### 4. Launch the Interface

```bash
cd src
python app.py
```

Open http://localhost:7860 in your browser.

## How It Works

### Data Flow

```
Your Notes → Parsers → Language Detection → Embeddings → ChromaDB → Search UI
```

### Semantic Search

The system uses **multilingual-e5-large**, which:
- Creates 1024-dimensional embeddings
- Understands multiple languages
- Finds similar notes by meaning

Example: Searching for "mental models" will also find your Portuguese notes about "modelos mentais"!

## Project Structure

```
second-brain-mvp/
├── src/
│   ├── models.py           # Data models
│   ├── notion_parser.py    # Parse Notion markdown
│   ├── keep_parser.py      # Parse Google Keep JSON
│   ├── kindle_parser.py    # Parse Kindle clippings
│   ├── vector_store.py     # ChromaDB wrapper
│   ├── ingest.py           # Main ingestion script
│   └── app.py              # Gradio interface
├── data/
│   ├── raw/                # Your source files
│   └── processed/          # ChromaDB storage
└── requirements.txt
```

## Usage Examples

### Search Interface

1. **Simple search**: "modelos mentais"
2. **Cross-language**: "mental models" (finds PT and EN notes)
3. **Filter by source**: Use the radio buttons
4. **Adjust results**: Slide to get more/fewer results

### Sample Queries

- "regressão à média" - Find notes about regression to the mean
- "sorte" - Find notes about luck
- "otimismo Voltaire" - Find Kindle highlights about optimism
- "data science" - Find your technical notes

## Technical Details

### Embeddings

- **Model**: intfloat/multilingual-e5-large
- **Dimensions**: 1024
- **Languages**: 100+ languages supported
- **Speed**: ~100 notes/second on CPU

### Vector Database

- **Backend**: ChromaDB
- **Distance metric**: Cosine similarity
- **Storage**: Local persistent storage
- **Index**: HNSW for fast search

### Parsing

- **Notion**: Extracts titles, tags, content from markdown
- **Keep**: Parses JSON, extracts labels, timestamps
- **Kindle**: Splits clippings, extracts book/author metadata

## Next Steps

This MVP demonstrates:
✅ Data ingestion from multiple sources  
✅ Multilingual semantic search  
✅ Simple web interface  

### Potential Enhancements

- 🤖 **RAG with Claude**: Answer questions using your notes
- 🏷️ **Auto-tagging**: AI-suggested tags
- 📊 **Clustering**: Discover themes in your notes
- 🔗 **Link suggestions**: Find related notes
- ✍️ **Writing assistant**: Draft using your knowledge
- 📱 **Mobile support**: Responsive design

## Troubleshooting

### Import errors
```bash
# Make sure you're in the src/ directory
cd src
python app.py
```

### No notes found
Check that your files are in the correct directories under `data/raw/`

### Slow embedding generation
First run will download the model (~2GB). Subsequent runs are faster.

## Stats from Your Data

Run the ingestion to see:
- Total notes count
- Breakdown by source (Notion/Keep/Kindle)
- Language distribution

---

**Built with**: Python, ChromaDB, Sentence Transformers, Gradio
