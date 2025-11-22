"""Harvest high-confidence matches from a repo into the golden dataset."""
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doczot_analyzer.scanner import scan_directory
from doczot_analyzer.docs_parser import find_markdown_files, parse_markdown_chunks, scan_documentation
from doczot_analyzer.vector_store import LocalVectorStore
from doczot_analyzer.matcher import Matcher

def harvest(repo_path: str, golden_file: str = "golden_dataset.json"):
    print(f"Harvesting from: {repo_path}")
    
    # 1. Analyze
    endpoints = scan_directory(repo_path)
    doc_references = scan_documentation(repo_path)
    
    md_files = find_markdown_files(repo_path)
    doc_chunks = []
    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
            try:
                rel_path = str(Path(md_file).relative_to(repo_path))
            except ValueError:
                rel_path = md_file
            doc_chunks.extend(parse_markdown_chunks(content, rel_path))
        except Exception:
            pass
            
    vector_store = LocalVectorStore(model_name="all-mpnet-base-v2")
    matcher = Matcher(vector_store)
    report = matcher.analyze(endpoints, doc_references, doc_chunks)
    
    # 2. Load existing dataset
    if os.path.exists(golden_file):
        with open(golden_file, 'r') as f:
            dataset = json.load(f)
    else:
        dataset = []
        
    # 3. Add new cases
    new_count = 0
    for ep in report.documented_endpoint_list:
        if ep.analysis_method == "vector" and ep.confidence_score > 0.55:
            # Find the matching chunk text
            res = matcher.vector_store.search(ep.semantic_signature, limit=1)
            if not res:
                continue
            
            chunk_text = res[0][0].content
            
            # Create test case
            case = {
                "id": f"harvested_{ep.method}_{ep.path.replace('/', '_')}",
                "category": "harvested",
                "endpoint": {
                    "method": ep.method,
                    "path": ep.path,
                    "docstring": ep.docstring,
                    "params": [p.name for p in ep.parameters]
                },
                "documentation": chunk_text,
                "expected_match": True,
                "source_repo": repo_path
            }
            
            # Check for duplicates
            if not any(c["id"] == case["id"] for c in dataset):
                dataset.append(case)
                new_count += 1
                print(f"Added: {case['id']}")
                
    # 4. Save
    with open(golden_file, 'w') as f:
        json.dump(dataset, f, indent=2)
        
    print(f"Harvested {new_count} new test cases.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("repo_path")
    args = parser.parse_args()
    harvest(args.repo_path)
