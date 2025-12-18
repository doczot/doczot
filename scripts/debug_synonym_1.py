"""Debug synonym_001 with mpnet."""
from doczot_analyzer.vector_store import LocalVectorStore
from doczot_analyzer.models import DocChunk

def debug_synonym_1():
    store = LocalVectorStore()
    doc_text = "Warehouse Management > Stock Control: To revise the count of items in the warehouse, use the adjustment route."
    chunk = DocChunk(file_path="test", content=doc_text, section_header="Stock Control")
    store.add_chunks([chunk])
    
    q = "Update stock levels. Method: POST /inventory/adjust. Parameters: sku, quantity"
    
    print(f"Doc: {doc_text}")
    print(f"Q: {q} -> {store.search(q, limit=1)[0][1]}")

if __name__ == "__main__":
    debug_synonym_1()
