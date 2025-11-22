"""Test simplified signature."""
from doczot_analyzer.vector_store import LocalVectorStore
from doczot_analyzer.models import DocChunk

def test_simplified():
    store = LocalVectorStore()
    
    # Adversarial
    doc_text = "Products > Create Product: POST /products Creates a new product."
    chunk = DocChunk(file_path="test", content=doc_text, section_header="Create Product")
    store.add_chunks([chunk])
    
    q1 = "Create a user"
    q2 = "Create a product"
    
    print(f"Doc: {doc_text}")
    print(f"Q: {q1} -> {store.search(q1, limit=1)[0][1]}")
    print(f"Q: {q2} -> {store.search(q2, limit=1)[0][1]}")

if __name__ == "__main__":
    test_simplified()
