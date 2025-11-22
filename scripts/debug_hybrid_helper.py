    print("-" * 20)
    # Synonym
    doc_text = "Warehouse Management > Stock Control: To revise the count of items in the warehouse, use the adjustment route."
    chunk = DocChunk(file_path="test", content=doc_text, section_header="Stock Control")
    store = LocalVectorStore()
    store.add_chunks([chunk])
    
    q = "Update stock levels. Method: POST /inventory/adjust"
    print(f"Doc: {doc_text}")
    print(f"Q: {q} -> {store.search(q, limit=1)[0][1]}")
