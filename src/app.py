"""
Gradio interface for the Second Brain MVP
"""
import gradio as gr
from pathlib import Path
from lightweight_vector_store import VectorStore
from datetime import datetime


class SecondBrainUI:
    """User interface for the second brain system"""
    
    def __init__(self):
        """Initialize the UI with vector store"""
        print("Loading vector store...")
        self.vector_store = VectorStore()
        self.stats = self.vector_store.get_stats()
        print(f"Loaded {self.stats['total_notes']} notes")
    
    def search(
        self, 
        query: str, 
        num_results: int = 10,
        source_filter: str = "All"
    ) -> str:
        """
        Search the knowledge base
        
        Args:
            query: Search query
            num_results: Number of results to return
            source_filter: Filter by source (All, Notion, Keep, Kindle)
        
        Returns:
            Formatted search results as markdown
        """
        if not query.strip():
            return "Please enter a search query."
        
        # Prepare filter
        filter_dict = None
        if source_filter != "All":
            filter_dict = {"source": source_filter.lower()}
        
        # Search
        results = self.vector_store.search(
            query=query,
            n_results=num_results,
            filter_dict=filter_dict
        )
        
        if not results:
            return "No results found."
        
        # Format results
        output = f"# Search Results for: '{query}'\n\n"
        output += f"Found {len(results)} results\n\n"
        output += "---\n\n"
        
        for i, result in enumerate(results, 1):
            metadata = result['metadata']
            content = result['content']
            
            # Format based on source
            title = metadata.get('title', 'Untitled')
            source = metadata.get('source', 'unknown')
            tags = metadata.get('tags', [])
            created = metadata.get('created_at', '')
            
            # Create result card
            output += f"## {i}. {title}\n\n"
            output += f"**Source:** {source.upper()}"
            
            if tags:
                output += f" | **Tags:** {', '.join(tags)}"
            
            if created:
                try:
                    dt = datetime.fromisoformat(created)
                    output += f" | **Date:** {dt.strftime('%Y-%m-%d')}"
                except:
                    pass
            
            output += "\n\n"
            
            # Add content (truncate if too long)
            content_display = content
            if len(content) > 500:
                content_display = content[:500] + "..."
            
            output += f"{content_display}\n\n"
            
            # Add metadata for Kindle
            if source == 'kindle':
                author = metadata.get('author')
                if author:
                    output += f"*Author: {author}*\n\n"
            
            # Similarity score
            if result.get('distance') is not None:
                similarity = 1 - result['distance']  # Convert distance to similarity
                output += f"*Similarity: {similarity:.2%}*\n\n"
            
            output += "---\n\n"
        
        return output
    
    def get_stats_display(self) -> str:
        """Get database statistics"""
        stats = self.vector_store.get_stats()
        return f"📊 **Total Notes:** {stats['total_notes']}"
    
    def create_interface(self):
        """Create the Gradio interface"""
        
        with gr.Blocks(title="Second Brain MVP", theme=gr.themes.Soft()) as interface:
            gr.Markdown(
                """
                # 🧠 Second Brain MVP
                
                Search your personal knowledge base using semantic search.
                The system understands multiple languages: Portuguese, English, French, and Spanish.
                """
            )
            
            # Stats display
            stats_display = gr.Markdown(self.get_stats_display())
            
            # Search section
            with gr.Row():
                with gr.Column(scale=4):
                    query_input = gr.Textbox(
                        label="Search Query",
                        placeholder="e.g., modelos mentais, mental models, ideas about...",
                        lines=2
                    )
                with gr.Column(scale=1):
                    num_results = gr.Slider(
                        minimum=1,
                        maximum=20,
                        value=10,
                        step=1,
                        label="Results"
                    )
            
            with gr.Row():
                source_filter = gr.Radio(
                    choices=["All", "Notion", "Keep", "Kindle"],
                    value="All",
                    label="Filter by Source"
                )
            
            search_button = gr.Button("🔍 Search", variant="primary", size="lg")
            
            # Results section
            results_output = gr.Markdown(label="Results")
            
            # Examples
            gr.Examples(
                examples=[
                    ["modelos mentais", 10, "All"],
                    ["otimismo", 5, "Kindle"],
                    ["sorte", 10, "Notion"],
                    ["mental models", 10, "All"],
                ],
                inputs=[query_input, num_results, source_filter],
            )
            
            # Wire up the search
            search_button.click(
                fn=self.search,
                inputs=[query_input, num_results, source_filter],
                outputs=results_output
            )
            
            # Also search on Enter
            query_input.submit(
                fn=self.search,
                inputs=[query_input, num_results, source_filter],
                outputs=results_output
            )
            
            gr.Markdown(
                """
                ---
                ### 💡 Tips
                - Search works across all languages automatically
                - Use natural language queries
                - Results are ranked by semantic similarity
                - Try different phrasings if you don't find what you're looking for
                """
            )
        
        return interface


def main():
    """Launch the interface"""
    ui = SecondBrainUI()
    interface = ui.create_interface()
    interface.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False
    )


if __name__ == "__main__":
    main()
