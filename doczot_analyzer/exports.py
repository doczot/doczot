"""Agent-oriented export formats for DocZot.

Generates output formats designed for AI agent consumption:
- MCP resource definitions (Model Context Protocol)
- llms.txt (AI crawler consumption)
- JSON-LD (lightweight, no rdflib dependency)
"""

import json
from datetime import datetime
from typing import Optional

from doczot_analyzer.models_v2 import (
    SystemGraph,
    SystemNode,
    NodeType,
    EdgeType,
    TopicManifest,
)


# =============================================================================
# MCP RESOURCE DEFINITION EXPORT
# =============================================================================

def export_mcp_resources(graph: SystemGraph) -> dict:
    """Generate MCP server resource and tool definitions from a system graph.

    Produces a JSON structure compatible with the Model Context Protocol,
    describing the software's entities as resources and its operations as tools.

    Args:
        graph: The system graph to export

    Returns:
        Dict with 'resources' (entities) and 'tools' (operations)
    """
    resources = []
    for noun in graph.nouns:
        resources.append({
            "uri": f"doczot://{graph.product_name}/entity/{noun.name}",
            "name": noun.name,
            "description": noun.description or f"The {noun.name} entity",
            "mimeType": "text/plain",
        })

    tools = []
    for verb in graph.verbs:
        # Build input schema from verb's connected nouns
        properties = {}
        required = []

        # Extract path parameters
        if verb.http_path:
            import re
            params = re.findall(r'\{(\w+)\}', verb.http_path)
            for param in params:
                properties[param] = {"type": "string", "description": f"Path parameter: {param}"}
                required.append(param)

        tool_def = {
            "name": verb.name,
            "description": _build_tool_description(verb, graph),
            "inputSchema": {
                "type": "object",
                "properties": properties,
            },
        }
        if required:
            tool_def["inputSchema"]["required"] = required

        tools.append(tool_def)

    return {
        "resources": resources,
        "tools": tools,
    }


def _build_tool_description(verb: SystemNode, graph: SystemGraph) -> str:
    """Build a description string for a tool from a verb node."""
    parts = []
    if verb.http_method and verb.http_path:
        parts.append(f"{verb.http_method} {verb.http_path}")
    if verb.description:
        parts.append(verb.description)

    # Add constraint info
    for edge in graph.edges:
        if edge.source_id == verb.id and edge.edge_type == EdgeType.CONSTRAINED_BY:
            constraint = graph.get_node(edge.target_id)
            if constraint and constraint.description:
                parts.append(f"[{constraint.description}]")

    return ". ".join(parts) if parts else verb.name


# =============================================================================
# LLMS.TXT GENERATION
# =============================================================================

def export_llms_txt(
    graph: SystemGraph,
    itm: Optional[TopicManifest] = None,
) -> str:
    """Generate llms.txt for AI crawler consumption.

    Produces a structured text file describing the software product's
    entities, operations, constraints, and concepts in a format optimized
    for LLM understanding.

    Args:
        graph: The system graph to export
        itm: Optional coverage checklist for topic organization

    Returns:
        llms.txt content as a string
    """
    lines = [
        f"# {graph.product_name}",
        "",
    ]

    # Product description from ITM if available
    if itm and itm.topics:
        onboarding = [t for t in itm.topics if t.topic_type.value == "onboarding"]
        if onboarding:
            lines.extend([
                "## Overview",
                "",
                f"This product has {len(graph.nouns)} entities, "
                f"{len(graph.verbs)} operations, "
                f"and {len(graph.constraints)} constraints.",
                "",
            ])

    # Entities section
    if graph.nouns:
        lines.extend(["## Entities", ""])
        for noun in sorted(graph.nouns, key=lambda n: n.name):
            desc = noun.description or f"A {noun.name} in the system"
            lines.append(f"- **{noun.name}**: {desc}")

            # Show part_of relationships
            for edge in graph.edges:
                if edge.source_id == noun.id and edge.edge_type == EdgeType.PART_OF:
                    parent = graph.get_node(edge.target_id)
                    if parent:
                        lines.append(f"  - Part of: {parent.name}")
        lines.append("")

    # Operations section, grouped by entity
    if graph.verbs:
        lines.extend(["## Operations", ""])
        for noun in sorted(graph.nouns, key=lambda n: n.name):
            verbs = graph.verbs_for_noun(noun.id)
            if verbs:
                lines.append(f"### {noun.name}")
                for verb in verbs:
                    method = verb.http_method or ""
                    path = verb.http_path or ""
                    desc = ""
                    if verb.description:
                        desc = f" - {verb.description}"
                    lines.append(f"- {method} {path}{desc}")
                lines.append("")

        # Show orphan verbs (not connected to any entity)
        orphans = graph.orphan_verbs()
        if orphans:
            lines.append("### Other operations")
            for verb in orphans:
                method = verb.http_method or ""
                path = verb.http_path or ""
                lines.append(f"- {method} {path}")
            lines.append("")

    # Constraints section
    if graph.constraints:
        lines.extend(["## Constraints", ""])
        for constraint in graph.constraints:
            desc = constraint.description or constraint.name
            lines.append(f"- {desc}")
        lines.append("")

    # Concepts section
    if graph.concepts:
        lines.extend(["## Concepts", ""])
        for concept in sorted(graph.concepts, key=lambda c: c.name):
            desc = concept.description or concept.name
            lines.append(f"- **{concept.name}**: {desc}")
        lines.append("")

    return "\n".join(lines)


# =============================================================================
# JSON-LD EXPORT (LIGHTWEIGHT, NO RDFLIB)
# =============================================================================

def export_jsonld(graph: SystemGraph) -> dict:
    """Generate a JSON-LD representation of the system graph.

    Produces a lightweight JSON-LD document without requiring rdflib,
    using schema.org vocabulary where applicable.

    Args:
        graph: The system graph to export

    Returns:
        JSON-LD document as a dict
    """
    base_uri = f"https://doczot.dev/{graph.product_name}"

    context = {
        "@vocab": "https://doczot.dev/ontology/",
        "schema": "https://schema.org/",
        "name": "schema:name",
        "description": "schema:description",
        "dateCreated": "schema:dateCreated",
        "hasPart": "schema:hasPart",
        "SoftwareApplication": "schema:SoftwareApplication",
    }

    nodes = []
    for node in graph.nodes:
        node_data = {
            "@id": f"{base_uri}/{node.type.value}/{node.name}",
            "@type": _node_type_to_jsonld(node.type),
            "name": node.name,
        }
        if node.description:
            node_data["description"] = node.description
        if node.http_method:
            node_data["httpMethod"] = node.http_method
        if node.http_path:
            node_data["httpPath"] = node.http_path
        if node.source_file:
            node_data["sourceFile"] = node.source_file
        if node.source_line:
            node_data["sourceLine"] = node.source_line

        # Add relationships
        relationships = []
        for edge in graph.edges:
            if edge.source_id == node.id:
                target = graph.get_node(edge.target_id)
                if target:
                    relationships.append({
                        "@type": edge.edge_type.value,
                        "target": f"{base_uri}/{target.type.value}/{target.name}",
                    })
        if relationships:
            node_data["relationships"] = relationships

        nodes.append(node_data)

    return {
        "@context": context,
        "@id": base_uri,
        "@type": "SoftwareApplication",
        "name": graph.product_name,
        "dateCreated": graph.scanned_at.isoformat(),
        "nodes": nodes,
    }


def _node_type_to_jsonld(node_type: NodeType) -> str:
    """Map DocZot node types to JSON-LD types."""
    mapping = {
        NodeType.VERB: "APIOperation",
        NodeType.NOUN: "Entity",
        NodeType.CONCEPT: "Concept",
        NodeType.CONSTRAINT: "Constraint",
    }
    return mapping.get(node_type, "Thing")
