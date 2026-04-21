#!/bin/bash

# Second Brain MVP - Run Script

echo "🧠 Second Brain MVP"
echo "=================="
echo ""

# Check if we need to ingest
if [ ! -d "data/processed/chroma" ]; then
    echo "📥 First time setup - ingesting notes..."
    cd src
    python ingest.py
    cd ..
else
    echo "✓ Vector database found"
fi

echo ""
echo "🚀 Launching web interface..."
echo "   Open http://localhost:7860 in your browser"
echo ""

cd src
python app.py
