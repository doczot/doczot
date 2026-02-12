"""Doc-side entity and relationship extraction.

Extracts a structured doc-side ontology from markdown files so we can compare
"what the code defines" vs "what the docs describe."

Entities extracted:
  - Nouns/entities: Terms in headers, bold definitions, repeated references
  - Verbs/operations: Documented API operations and imperative instructions
  - Concepts: Terms with definitions (extends extract_concepts_from_docs)
  - Relationships: part_of, prerequisite, operates_on, constrained_by

The DocGraph is compared against the SystemGraph to produce a GraphComparison
that identifies covered, missing, extra, and mismatched entities.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from doczot_analyzer.docs_parser import find_markdown_files
from doczot_analyzer.models_v2 import SystemGraph, NodeType


# =============================================================================
# MODELS
# =============================================================================

class DocMention(BaseModel):
    """A mention of an entity in documentation."""
    doc_file: str
    section: Optional[str] = None
    line_number: Optional[int] = None
    snippet: str = ""


class DocEntity(BaseModel):
    """An entity extracted from documentation."""
    name: str
    entity_type: str  # "noun", "verb", "concept"
    mentions: list[DocMention] = Field(default_factory=list)
    definition: Optional[str] = None


class DocRelationship(BaseModel):
    """A relationship extracted from documentation."""
    source: str
    target: str
    rel_type: str  # "part_of", "prerequisite", "operates_on", "constrained_by"
    evidence: str  # The sentence that establishes this
    doc_file: str


class DocGraph(BaseModel):
    """A graph of entities and relationships extracted from documentation."""
    entities: list[DocEntity] = Field(default_factory=list)
    relationships: list[DocRelationship] = Field(default_factory=list)

    def entities_by_type(self, entity_type: str) -> list[DocEntity]:
        return [e for e in self.entities if e.entity_type == entity_type]

    @property
    def nouns(self) -> list[DocEntity]:
        return self.entities_by_type("noun")

    @property
    def verbs(self) -> list[DocEntity]:
        return self.entities_by_type("verb")

    @property
    def concepts(self) -> list[DocEntity]:
        return self.entities_by_type("concept")


class GraphComparison(BaseModel):
    """Comparison between code-side SystemGraph and doc-side DocGraph."""
    # Code entities covered in docs
    covered_entities: list[str] = Field(default_factory=list)
    # Code entities absent from docs
    missing_entities: list[str] = Field(default_factory=list)
    # Doc entities with no code backing
    extra_entities: list[str] = Field(default_factory=list)
    # Relationship mismatches (code says X rel Y, docs say differently)
    relationship_mismatches: list[dict] = Field(default_factory=list)
    # Summary stats
    code_entity_count: int = 0
    doc_entity_count: int = 0
    coverage_ratio: float = 0.0


# =============================================================================
# EXTRACTION PATTERNS
# =============================================================================

# Relationship patterns: (regex, rel_type, source_group, target_group)
_RELATIONSHIP_PATTERNS: list[tuple[str, str, int, int]] = [
    # "X belongs to Y", "X is part of Y"
    (r'(?:^|[.;])\s*(?:(?:a|an|the|each)\s+)?(\w+)\s+(?:belongs?\s+to|is\s+(?:a\s+)?part\s+of)\s+(?:(?:a|an|the|each)\s+)?(\w+)',
     "part_of", 1, 2),
    # "Y contains X", "Y has X"
    (r'(?:^|[.;])\s*(?:(?:a|an|the|each)\s+)?(\w+)\s+(?:contains?|has|includes?)\s+(?:(?:one\s+or\s+more|multiple|many|several|zero\s+or\s+more)\s+)?(\w+)',
     "part_of", 2, 1),
    # "X requires Y" - use word boundary after optional article
    (r'(?:^|[.;])\s*(?:(?:a|an|the|each)\s+)?(\w+)\s+requires?\s+(?:(?:a|an|the)\s+)?(\w+)',
     "prerequisite", 1, 2),
    (r'before\s+(?:you\s+)?(?:can\s+)?(\w+).*?(?:you\s+must|need\s+to|requires?)\s+(\w+)',
     "prerequisite", 1, 2),
    # "X uses Y", "X operates on Y"
    (r'(?:^|[.;])\s*(?:(?:a|an|the|each)\s+)?(\w+)\s+(?:uses?|operates?\s+on|works?\s+with)\s+(?:(?:a|an|the)\s+)?(\w+)',
     "operates_on", 1, 2),
    # "X is limited to Y", "X has a limit of Y"
    (r'(?:^|[.;:,])\s*(?:(?:a|an|the|each)\s+)?(\w+)\s+(?:is\s+limited\s+to|has\s+a\s+limit\s+of|is\s+(?:restricted|constrained)\s+(?:to|by))\s+(.+?)(?:[.;]|$)',
     "constrained_by", 1, 2),
]

# Imperative verb patterns for detecting documented operations
_IMPERATIVE_PATTERNS = re.compile(
    r'(?:^|\n)\s*(?:[-*]|(?:\d+[.)]))?\s*'
    r'(create|delete|update|remove|add|modify|configure|set\s+up|retrieve|get|list|fetch|upload|download|import|export|enable|disable|activate|deactivate|assign|revoke|invite|approve|reject|reset|cancel|submit|publish|archive)'
    r'\s+(?:a\s+|an\s+|the\s+|your\s+)?(\w+)',
    re.IGNORECASE
)

# HTTP method patterns in docs
_HTTP_PATTERN = re.compile(
    r'\b(GET|POST|PUT|DELETE|PATCH)\s+(/[a-zA-Z0-9/_\-{}:]+)',
    re.IGNORECASE
)

# Terms that are too generic to be entities
_SKIP_TERMS = {
    'the', 'this', 'that', 'each', 'every', 'some', 'any', 'all',
    'you', 'your', 'they', 'them', 'it', 'its', 'we', 'our',
    'example', 'section', 'page', 'documentation', 'document',
    'note', 'warning', 'tip', 'important', 'table', 'list', 'field',
    'value', 'type', 'name', 'string', 'number', 'boolean', 'integer',
    'object', 'array', 'data', 'information', 'details', 'following',
    'above', 'below', 'here', 'there', 'step', 'process', 'way',
    'time', 'case', 'order', 'request', 'response', 'error', 'result',
    'file', 'directory', 'path', 'code', 'command', 'option', 'parameter',
}


# =============================================================================
# EXTRACTION FUNCTIONS
# =============================================================================

def extract_doc_graph(repo_path: str, graph: SystemGraph) -> DocGraph:
    """Extract a doc-side ontology from markdown files.

    Finds all markdown files in the repo and extracts entities, relationships,
    and concepts. Cross-references against the code graph's nouns for coverage.

    Args:
        repo_path: Path to the repository
        graph: The code-side SystemGraph for cross-referencing

    Returns:
        DocGraph with extracted entities and relationships
    """
    repo_path = str(Path(repo_path).resolve())

    # Build set of known code entity names for cross-referencing
    code_nouns = {n.name.lower() for n in graph.nodes if n.type == NodeType.NOUN}
    code_verbs = set()
    for n in graph.nodes:
        if n.type == NodeType.VERB and n.http_method and n.http_path:
            code_verbs.add((n.http_method, n.http_path))

    # Find markdown files
    md_files = find_markdown_files(repo_path)

    entities: dict[str, DocEntity] = {}  # key = lowercase name
    relationships: list[DocRelationship] = []

    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            continue

        try:
            rel_path = str(Path(md_file).relative_to(repo_path))
        except ValueError:
            rel_path = md_file

        _extract_from_file(content, rel_path, code_nouns, entities, relationships)

    return DocGraph(
        entities=list(entities.values()),
        relationships=relationships,
    )


def _extract_from_file(
    content: str,
    file_path: str,
    code_nouns: set[str],
    entities: dict[str, DocEntity],
    relationships: list[DocRelationship],
) -> None:
    """Extract entities and relationships from a single markdown file."""
    lines = content.split('\n')
    current_section = ""

    for line_num, line in enumerate(lines, start=1):
        # Track section headers
        if line.startswith('#'):
            current_section = line.lstrip('#').strip()

            # Headers themselves may name entities
            _try_add_noun_from_header(
                current_section, file_path, line_num, code_nouns, entities
            )
            continue

        # Extract bold definitions: **term**: definition or **term** - definition
        _extract_bold_definitions(
            line, file_path, current_section, line_num, entities
        )

        # Extract HTTP endpoint references as verb entities
        _extract_http_verbs(line, file_path, current_section, line_num, entities)

        # Extract imperative instructions as verb entities
        _extract_imperative_verbs(
            line, file_path, current_section, line_num, entities
        )

    # Extract relationships from full content (need sentence context)
    _extract_relationships(content, file_path, code_nouns, entities, relationships)

    # Extract entity mentions by scanning for known code nouns
    _extract_noun_mentions(content, file_path, code_nouns, entities)


def _try_add_noun_from_header(
    header: str,
    file_path: str,
    line_num: int,
    code_nouns: set[str],
    entities: dict[str, DocEntity],
) -> None:
    """Check if a header names a known code entity."""
    # Extract words from header, check against code nouns
    words = re.findall(r'\b[a-zA-Z]\w+\b', header.lower())
    for word in words:
        if word in code_nouns and word not in _SKIP_TERMS:
            _add_entity(entities, word, "noun", DocMention(
                doc_file=file_path,
                section=header,
                line_number=line_num,
                snippet=header,
            ))


def _extract_bold_definitions(
    line: str,
    file_path: str,
    section: str,
    line_num: int,
    entities: dict[str, DocEntity],
) -> None:
    """Extract entities from bold term definitions."""
    # **term**: definition
    pattern = r'\*\*([A-Za-z]\w+(?:\s+\w+)?)\*\*\s*[:–\-]\s*(.+)'
    for match in re.finditer(pattern, line):
        term = match.group(1).strip().lower()
        definition = match.group(2).strip()
        if term not in _SKIP_TERMS and len(term) >= 3:
            ent = _add_entity(entities, term, "concept", DocMention(
                doc_file=file_path,
                section=section,
                line_number=line_num,
                snippet=line.strip()[:200],
            ))
            if not ent.definition:
                ent.definition = definition[:200]


def _extract_http_verbs(
    line: str,
    file_path: str,
    section: str,
    line_num: int,
    entities: dict[str, DocEntity],
) -> None:
    """Extract HTTP endpoint references as verb entities."""
    for match in _HTTP_PATTERN.finditer(line):
        method = match.group(1).upper()
        path = match.group(2).rstrip('.,;:')
        name = f"{method} {path}"
        _add_entity(entities, name.lower(), "verb", DocMention(
            doc_file=file_path,
            section=section,
            line_number=line_num,
            snippet=line.strip()[:200],
        ))


def _extract_imperative_verbs(
    line: str,
    file_path: str,
    section: str,
    line_num: int,
    entities: dict[str, DocEntity],
) -> None:
    """Extract imperative verb + noun patterns as verb entities."""
    for match in _IMPERATIVE_PATTERNS.finditer(line):
        action = match.group(1).lower().strip()
        target = match.group(2).lower().strip()
        if target not in _SKIP_TERMS and len(target) >= 3:
            name = f"{action} {target}"
            _add_entity(entities, name, "verb", DocMention(
                doc_file=file_path,
                section=section,
                line_number=line_num,
                snippet=line.strip()[:200],
            ))


def _extract_noun_mentions(
    content: str,
    file_path: str,
    code_nouns: set[str],
    entities: dict[str, DocEntity],
) -> None:
    """Scan content for mentions of known code nouns."""
    content_lower = content.lower()
    for noun in code_nouns:
        if noun in _SKIP_TERMS:
            continue
        # Count occurrences - only add if mentioned multiple times
        # (single mention might be incidental)
        count = len(re.findall(r'\b' + re.escape(noun) + r's?\b', content_lower))
        if count >= 2:
            # Add as entity if not already present
            if noun not in entities:
                _add_entity(entities, noun, "noun", DocMention(
                    doc_file=file_path,
                    snippet=f"Mentioned {count} times in {file_path}",
                ))
            else:
                # Add a mention to existing entity
                entities[noun].mentions.append(DocMention(
                    doc_file=file_path,
                    snippet=f"Mentioned {count} times in {file_path}",
                ))


def _singularize(word: str) -> str:
    """Simple singularize: strip trailing 's' for basic plural forms."""
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("ses") or word.endswith("xes") or word.endswith("zes"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _is_known(word: str, code_nouns: set[str], entities: dict[str, DocEntity]) -> bool:
    """Check if a word (or its singular form) is a known entity."""
    if word in code_nouns or word in entities:
        return True
    singular = _singularize(word)
    return singular in code_nouns or singular in entities


def _extract_relationships(
    content: str,
    file_path: str,
    code_nouns: set[str],
    entities: dict[str, DocEntity],
    relationships: list[DocRelationship],
) -> None:
    """Extract relationships from natural language patterns."""
    content_lower = content.lower()

    for pattern_str, rel_type, src_group, tgt_group in _RELATIONSHIP_PATTERNS:
        for match in re.finditer(pattern_str, content_lower, re.IGNORECASE | re.MULTILINE):
            source_raw = match.group(src_group).strip().lower()
            target_raw = match.group(tgt_group).strip().lower()

            # Normalize source to singular form
            source = _singularize(source_raw)

            if source in _SKIP_TERMS or len(source) < 3:
                continue

            # For constrained_by, target is a constraint description, not an entity
            if rel_type == "constrained_by":
                target = target_raw.strip()
                # Only require source to be known
                if not _is_known(source, code_nouns, entities):
                    continue
            else:
                # Take only the first word of multi-word targets
                target_word = target_raw.split()[0] if target_raw else ""
                target = _singularize(target_word)

                if target in _SKIP_TERMS or len(target) < 3:
                    continue

                # At least one side must be a known entity
                source_known = _is_known(source, code_nouns, entities)
                target_known = _is_known(target, code_nouns, entities)
                if not (source_known or target_known):
                    continue

            evidence = match.group(0).strip()[:200]
            relationships.append(DocRelationship(
                source=source,
                target=target,
                rel_type=rel_type,
                evidence=evidence,
                doc_file=file_path,
            ))


def _add_entity(
    entities: dict[str, DocEntity],
    name: str,
    entity_type: str,
    mention: DocMention,
) -> DocEntity:
    """Add or update an entity in the entities dict."""
    key = name.lower()
    if key not in entities:
        entities[key] = DocEntity(
            name=name,
            entity_type=entity_type,
            mentions=[mention],
        )
    else:
        entities[key].mentions.append(mention)
    return entities[key]


# =============================================================================
# GRAPH COMPARISON
# =============================================================================

def compare_graphs(code_graph: SystemGraph, doc_graph: DocGraph) -> GraphComparison:
    """Compare code-side SystemGraph against doc-side DocGraph.

    Identifies:
    - Covered: code entities well-documented in docs
    - Missing: code entities absent from docs
    - Extra: doc entities with no code backing (orphan docs)
    - Mismatches: relationship disagreements

    Args:
        code_graph: The SystemGraph from code scanning
        doc_graph: The DocGraph from doc extraction

    Returns:
        GraphComparison with coverage analysis
    """
    # Build lookup sets
    code_noun_names = {n.name.lower() for n in code_graph.nouns}
    code_verb_sigs = set()
    code_verb_names = set()
    for v in code_graph.verbs:
        if v.http_method and v.http_path:
            code_verb_sigs.add(f"{v.http_method.lower()} {v.http_path.lower()}")
        code_verb_names.add(v.name.lower())

    doc_noun_names = {e.name.lower() for e in doc_graph.nouns}
    doc_verb_names = {e.name.lower() for e in doc_graph.verbs}
    doc_concept_names = {e.name.lower() for e in doc_graph.concepts}

    # Covered: code entities found in docs
    covered = set()
    for noun in code_noun_names:
        if noun in doc_noun_names or noun in doc_concept_names:
            covered.add(noun)
    for sig in code_verb_sigs:
        if sig in doc_verb_names:
            covered.add(sig)

    # Missing: code entities not in docs
    missing_nouns = code_noun_names - doc_noun_names - doc_concept_names
    missing_verbs = code_verb_sigs - doc_verb_names

    # Extra: doc entities not in code
    extra_nouns = doc_noun_names - code_noun_names
    extra_concepts = {c for c in doc_concept_names if c not in code_noun_names}

    # Relationship mismatches
    mismatches = _find_relationship_mismatches(code_graph, doc_graph)

    all_code = code_noun_names | code_verb_sigs
    total_code = len(all_code) if all_code else 1

    return GraphComparison(
        covered_entities=sorted(covered),
        missing_entities=sorted(missing_nouns | missing_verbs),
        extra_entities=sorted(extra_nouns | extra_concepts),
        relationship_mismatches=mismatches,
        code_entity_count=len(all_code),
        doc_entity_count=len(doc_noun_names | doc_verb_names | doc_concept_names),
        coverage_ratio=round(len(covered) / total_code, 3) if total_code else 0.0,
    )


def _find_relationship_mismatches(
    code_graph: SystemGraph,
    doc_graph: DocGraph,
) -> list[dict]:
    """Find cases where docs describe different relationships than code."""
    mismatches = []

    # Build code relationship map: (source, target) -> edge_type
    code_rels: dict[tuple[str, str], str] = {}
    for edge in code_graph.edges:
        src_node = code_graph.get_node(edge.source_id)
        tgt_node = code_graph.get_node(edge.target_id)
        if src_node and tgt_node:
            key = (src_node.name.lower(), tgt_node.name.lower())
            code_rels[key] = edge.edge_type.value

    # Check doc relationships against code
    for rel in doc_graph.relationships:
        key = (rel.source, rel.target)
        if key in code_rels and code_rels[key] != rel.rel_type:
            mismatches.append({
                "source": rel.source,
                "target": rel.target,
                "code_rel": code_rels[key],
                "doc_rel": rel.rel_type,
                "evidence": rel.evidence,
                "doc_file": rel.doc_file,
            })

    return mismatches
