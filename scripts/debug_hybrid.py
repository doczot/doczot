"""Test hybrid signature."""
from doczot_analyzer.vector_store import LocalVectorStore
from doczot_analyzer.models import DocChunk

def test_hybrid():
    store = LocalVectorStore()
    
    # Adversarial
    doc_text = "Products > Create Product: POST /products Creates a new product."
    chunk = DocChunk(file_path="test", content=doc_text, section_header="Create Product")
    store.add_chunks([chunk])
    
    q1 = "Create a user. Method: POST /users"
    q2 = "Create a product. Method: POST /products"
    
    print(f"Doc: {doc_text}")
    print(f"Q: {q1} -> {store.search(q1, limit=1)[0][1]}")
    print(f"Q: {q2} -> {store.search(q2, limit=1)[0][1]}")

if __name__ == "__main__":
    test_hybrid()
    print("-" * 20)
    # Synonym
    doc_text = "Warehouse Management > Stock Control: To revise the count of items in the warehouse, use the adjustment route."
    chunk = DocChunk(file_path="test", content=doc_text, section_header="Stock Control")
    store = LocalVectorStore()
    store.add_chunks([chunk])
    
    q = "Update stock levels. Method: POST /inventory/adjust"
    print(f"Doc: {doc_text}")
    print(f"Q: {q} -> {store.search(q, limit=1)[0][1]}")
    print("-" * 20)
    # Synonym with params
    doc_text = "Warehouse Management > Stock Control: To revise the count of items in the warehouse, use the adjustment route."
    chunk = DocChunk(file_path="test", content=doc_text, section_header="Stock Control")
    store = LocalVectorStore()
    store.add_chunks([chunk])
    
    q = "Update stock levels. Method: POST /inventory/adjust. Parameters: sku, quantity"
    print(f"Doc: {doc_text}")
    print(f"Q: {q} -> {store.search(q, limit=1)[0][1]}")
