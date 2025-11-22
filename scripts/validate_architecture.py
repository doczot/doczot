"""Validate the semantic architecture against the Golden Dataset.

Runs the matcher against the synthetic test cases and reports accuracy.
"""
import json
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from doczot_analyzer.models import Endpoint, DocReference, DocChunk
from doczot_analyzer.matcher import Matcher
from doczot_analyzer.vector_store import LocalVectorStore
from doczot_analyzer.scanner import _generate_semantic_signature
from doczot_analyzer.docs_parser import parse_markdown_chunks
import ast

def validate():
    # Load dataset
    try:
        with open("golden_dataset.json", "r") as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print("Error: golden_dataset.json not found. Run generate_golden_dataset.py first.")
        return

    # Initialize components
    vector_store = LocalVectorStore()
    matcher = Matcher(vector_store)
    
    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "by_category": {}
    }
    
    print(f"Running validation on {len(dataset)} test cases...")
    print("-" * 60)
    
    for case in dataset:
        case_id = case["id"]
        category = case["category"]
        expected = case["expected_match"]
        
        # Construct Endpoint object
        ep_data = case["endpoint"]
        
        # Mock AST node for signature generation (simplified)
        # In a real scenario, we'd parse actual code
        # Here we just manually construct the signature for testing
        # Format: "{docstring}. Method: {method} {path}. Parameters: {params}."
        semantic_sig = f"{ep_data['docstring']}. Method: {ep_data['method']} {ep_data['path']}"
        if ep_data['params']:
             semantic_sig += f". Parameters: {', '.join(ep_data['params'])}"
        
        endpoint = Endpoint(
            method=ep_data["method"],
            path=ep_data["path"],
            function_name="test_func",
            file_path="test.py",
            line_number=1,
            docstring=ep_data["docstring"],
            semantic_signature=semantic_sig
        )
        
        # Parse documentation into chunks using the actual parser logic
        chunks = parse_markdown_chunks(case["documentation"], "docs.md")
        
        # Use the most relevant chunk for the test (simplified)
        # In reality, we'd index all chunks. Here we just take the one that likely contains the text.
        # For the golden dataset, usually there's one main chunk of interest.
        # We'll just use all chunks found.
        
        # Reset vector store for each test case to isolate them
        matcher.vector_store = LocalVectorStore() 
        
        # Run Analysis
        # We pass the chunk as both a reference (for exact match check) and a chunk (for vector)
        
        # Mock DocReference for exact match check
        ref = DocReference(
            file_path="docs.md",
            content=case["documentation"],
            mentioned_paths=[], 
            mentioned_methods=[]
        )
        if ep_data["path"] in case["documentation"]:
            ref.mentioned_paths.append(ep_data["path"])
            ref.mentioned_methods.append(ep_data["method"])
            
        report = matcher.analyze(
            endpoints=[endpoint],
            doc_references=[ref],
            doc_chunks=chunks
        )
        
        result_ep = report.endpoints[0]
        is_match = result_ep.is_documented
        
        # Check result
        passed = (is_match == expected)
        
        results["total"] += 1
        if passed:
            results["passed"] += 1
            status = "PASS"
        else:
            results["failed"] += 1
            status = "FAIL"
            
        # Update category stats
        if category not in results["by_category"]:
            results["by_category"][category] = {"total": 0, "passed": 0}
        results["by_category"][category]["total"] += 1
        if passed:
            results["by_category"][category]["passed"] += 1
            
        print(f"[{status}] {case_id} ({category}): Expected={expected}, Got={is_match} (Method: {result_ep.analysis_method}, Score: {result_ep.confidence_score})")
        if not passed and result_ep.confidence_score is None:
             # Check what the score actually was by peeking into the store
             res = matcher.vector_store.search(endpoint.semantic_signature, limit=1)
             if res:
                 print(f"   -> Actual Score was: {res[0][1]}")

    print("-" * 60)
    print(f"Total Accuracy: {results['passed']}/{results['total']} ({results['passed']/results['total']*100:.1f}%)")
    
    print("\nCategory Breakdown:")
    for cat, stats in results["by_category"].items():
        acc = stats["passed"] / stats["total"] * 100
        print(f"  {cat}: {stats['passed']}/{stats['total']} ({acc:.1f}%)")

if __name__ == "__main__":
    validate()
