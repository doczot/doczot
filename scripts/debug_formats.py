"""Test different signature formats."""
from doczot_analyzer.vector_store import LocalVectorStore
from doczot_analyzer.models import DocChunk

def test_formats():
    store = LocalVectorStore()
    doc_text = "Auth > Logout: Users can sign out to clear their credentials."
    chunk = DocChunk(file_path="test", content=doc_text, section_header="Logout")
    store.add_chunks([chunk])
    
    queries = [
        "A DELETE request to /session/terminate. End current session",
        "Delete session terminate. End current session",
        "Terminate the current session.",
        "API endpoint to end session and terminate.",
        "Action: Terminate Session. Path: /session/terminate"
    ]
    
    print(f"Doc: {doc_text}")
    for q in queries:
        results = store.search(q, limit=1)
        print(f"Query: {q}")
        print(f"Score: {results[0][1]}")
        print("-" * 20)

if __name__ == "__main__":
    test_formats()
