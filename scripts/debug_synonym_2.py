"""Debug synonym_002."""
from doczot_analyzer.vector_store import LocalVectorStore
from doczot_analyzer.models import DocChunk

def debug_synonym_2():
    store = LocalVectorStore()
    doc_text = "Auth > Logout: Users can sign out to clear their credentials."
    chunk = DocChunk(file_path="test", content=doc_text, section_header="Logout")
    store.add_chunks([chunk])
    
    q = "End current session. Method: DELETE /session/terminate"
    
    print(f"Doc: {doc_text}")
    print(f"Q: {q} -> {store.search(q, limit=1)[0][1]}")

if __name__ == "__main__":
    debug_synonym_2()
