"""Run DocZot analyzer on a target repository."""
import sys
import os
import argparse
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doczot_analyzer.scanner import scan_directory
from doczot_analyzer.docs_parser import scan_documentation, parse_markdown_chunks
from doczot_analyzer.matcher import Matcher
from doczot_analyzer.vector_store import LocalVectorStore
from doczot_analyzer.models import DocChunk

def run_analysis(repo_path: str):
    print(f"Analyzing repository: {repo_path}")
    
    # 1. Scan Code
    print("Scanning code for endpoints...")
    endpoints = scan_directory(repo_path)
    print(f"Found {len(endpoints)} endpoints.")
    
    # 2. Parse Documentation
    print("Scanning documentation...")
    # Get references (for exact match)
    doc_references = scan_documentation(repo_path)
    print(f"Found {len(doc_references)} documentation references.")
    
    # Get chunks (for vector match)
    print("Generating documentation chunks...")
    doc_chunks = []
    # Find all markdown files again to chunk them
    # (Reusing find_markdown_files logic would be better, but for now we just re-scan)
    from doczot_analyzer.docs_parser import find_markdown_files
    md_files = find_markdown_files(repo_path)
    print(f"Found {len(md_files)} markdown files: {md_files}")
    
    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Relative path for display
            try:
                rel_path = str(Path(md_file).relative_to(repo_path))
            except ValueError:
                rel_path = md_file
                
            chunks = parse_markdown_chunks(content, rel_path)
            doc_chunks.extend(chunks)
        except Exception as e:
            print(f"Error processing {md_file}: {e}")
            
    print(f"Generated {len(doc_chunks)} semantic chunks.")
    
    # 3. Run Matcher
    print("Running semantic matcher...")
    # Initialize vector store with mpnet
    vector_store = LocalVectorStore(model_name="all-mpnet-base-v2")
    matcher = Matcher(vector_store)
    
    report = matcher.analyze(endpoints, doc_references, doc_chunks)
    
    # 4. Print Results
    print("\n" + "="*60)
    print("ANALYSIS RESULTS")
    print("="*60)
    print(str(report))
    print("-" * 60)
    
    print("\nDocumented Endpoints:")
    for ep in report.documented_endpoint_list:
        method_str = f"[{ep.analysis_method}]".ljust(10)
        score_str = f"{ep.confidence_score:.2f}" if ep.confidence_score else "N/A"
        print(f"{method_str} {ep.method} {ep.path} (Score: {score_str})")
        
        # Peek at the match if it's vector
        if ep.analysis_method == "vector":
             res = matcher.vector_store.search(ep.semantic_signature, limit=1)
             if res:
                 print(f"   -> Matched Chunk: {res[0][0].content[:100]}...")
                 print(f"   -> From File: {res[0][0].file_path}")
        
    print("\nUndocumented Endpoints:")
    for ep in report.undocumented_endpoint_list:
        print(f"[MISSING]  {ep.method} {ep.path}")
        # Print signature to see why it missed
        # print(f"           Sig: {ep.semantic_signature}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run DocZot on a repo")
    parser.add_argument("repo_path", help="Path to the repository to analyze")
    args = parser.parse_args()
    
    run_analysis(args.repo_path)
