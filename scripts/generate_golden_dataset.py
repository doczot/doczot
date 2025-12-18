"""Generate synthetic test cases for the Golden Dataset.

This script creates a JSON dataset of endpoint/documentation pairs
specifically designed to test semantic matching capabilities.
"""
import json
import os
from typing import List, Dict

def generate_dataset(output_path: str = "golden_dataset.json"):
    dataset = [
        # Category 1: Exact Matches (Baseline)
        {
            "id": "exact_001",
            "category": "exact",
            "endpoint": {
                "method": "GET",
                "path": "/users/{id}",
                "docstring": "Get user by ID",
                "params": ["id"]
            },
            "documentation": "# User API\n\n## Get User\n\n`GET /users/{id}`\n\nRetrieves a user.",
            "expected_match": True
        },
        
        # Category 2: Synonym Divergence (The Core Test)
        {
            "id": "synonym_001",
            "category": "synonym",
            "endpoint": {
                "method": "POST",
                "path": "/inventory/adjust",
                "docstring": "Update stock levels",
                "params": ["sku", "quantity"]
            },
            "documentation": "# Warehouse Management\n\n## Stock Control\n\nTo revise the count of items in the warehouse, use the adjustment route.",
            "expected_match": True
        },
        {
            "id": "synonym_002",
            "category": "synonym",
            "endpoint": {
                "method": "DELETE",
                "path": "/session/terminate",
                "docstring": "End current session",
                "params": []
            },
            "documentation": "# Auth\n\n## Logout\n\nUsers can sign out to clear their credentials.",
            "expected_match": True
        },
        
        # Category 3: Structural Implication
        {
            "id": "struct_001",
            "category": "structural",
            "endpoint": {
                "method": "GET",
                "path": "/api/v1/billing/invoices",
                "docstring": "List invoices",
                "params": []
            },
            "documentation": "# Billing API\n\n## Invoices\n\nThis section allows you to list all past bills.",
            "expected_match": True
        },
        
        # Category 4: Adversarial/Distractor
        {
            "id": "adv_001",
            "category": "adversarial",
            "endpoint": {
                "method": "POST",
                "path": "/users",
                "docstring": "Create a user",
                "params": []
            },
            "documentation": "# Products\n\n## Create Product\n\nPOST /products\n\nCreates a new product.",
            "expected_match": False
        }
    ]
    
    with open(output_path, 'w') as f:
        json.dump(dataset, f, indent=2)
        
    print(f"Generated {len(dataset)} test cases in {output_path}")

if __name__ == "__main__":
    generate_dataset()
