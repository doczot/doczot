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
