"""Debug vector similarity scores."""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doczot_analyzer.vector_store import LocalVectorStore
from doczot_analyzer.models import DocChunk

def debug():
    store = LocalVectorStore()
    
    # Case 1: Synonym
    query = "A POST request to /inventory/adjust. Update stock levels Accepts parameters: sku, quantity."
    doc_text = "Warehouse Management > Stock Control: To revise the count of items in the warehouse, use the adjustment route."
    
    chunk = DocChunk(file_path="test", content=doc_text, section_header="Stock Control")
    store.add_chunks([chunk])
    
    results = store.search(query, limit=1)
    print(f"Query: {query}")
    print(f"Doc: {doc_text}")
    print(f"Score: {results[0][1]}")
    print("-" * 40)
    
    # Case 2: Synonym 2
    query = "A DELETE request to /session/terminate. End current session"
    doc_text = "Auth > Logout: Users can sign out to clear their credentials."
    
    store = LocalVectorStore()
    chunk = DocChunk(file_path="test", content=doc_text, section_header="Logout")
    store.add_chunks([chunk])
    
    results = store.search(query, limit=1)
    print(f"Query: {query}")
    print(f"Doc: {doc_text}")
    print(f"Score: {results[0][1]}")

if __name__ == "__main__":
    debug()
    print("-" * 40)
    # Case 3: Adversarial
    query = "A POST request to /users. Create a user"
    doc_text = "Products > Create Product: POST /products Creates a new product."
    
    store = LocalVectorStore()
    chunk = DocChunk(file_path="test", content=doc_text, section_header="Create Product")
    store.add_chunks([chunk])
    
    results = store.search(query, limit=1)
    print(f"Query: {query}")
    print(f"Doc: {doc_text}")
    print(f"Score: {results[0][1]}")
