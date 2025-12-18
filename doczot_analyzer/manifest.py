"""Topic Manifest models for DocZot.

This module defines the core data structures for:
- ITM (Intended Topic Manifest): What SHOULD be documented (product surface)
- ATM (Actual Topic Manifest): What IS documented (coverage + quality)

The manifest uses a graph structure where:
- Nodes represent documentable topics (nouns, verbs, concepts)
- Edges represent relationships between topics
- Coverage data captures documentation quality per topic

Architecture:
    Product Surface (ITM)     Documentation (ATM)
    ┌─────────────────┐       ┌─────────────────┐
    │  TopicNode      │       │  ContentPiece   │
    │  (noun/verb/    │◄─────►│  (reference/    │
    │   concept)      │       │   recipe/etc)   │
    └─────────────────┘       └─────────────────┘
            │                         │
            │    TopicCoverage        │
            └────────┬────────────────┘
                     │
              ┌──────▼──────┐
              │ QualityScore│
              │ - technical │
              │ - semantic  │
              │ - style     │
              └─────────────┘
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional, Literal, Any
from pydantic import BaseModel, Field

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False


# =============================================================================
# ENUMS
# =============================================================================

class NodeType(str, Enum):
    """Types of nodes in the product surface graph.

    These represent the "what" of a product - the things users interact with.
    """
    NOUN = "noun"       # Entities: User, Project, Invoice, Document
    VERB = "verb"       # Actions: create, delete, configure, export, share
    CONCEPT = "concept" # Ideas requiring explanation: authentication, rate limiting, permissions


class NodeClass(str, Enum):
    """Classification of nodes for coverage calculation.

    Internal and meta nodes are tracked but excluded from coverage percentages.
    """
    USER_FACING = "user-facing"  # Normal API endpoints, features users interact with
    INTERNAL = "internal"        # Helper endpoints, health checks, metrics
    META = "meta"                # Documentation endpoints (/docs, /redoc, /openapi.json)
    DEPRECATED = "deprecated"    # Marked for removal, may or may not need docs


class NodeSource(str, Enum):
    """How a node was discovered."""
    AUTO_API = "auto_api"           # Extracted from API code (FastAPI decorators, etc.)
    AUTO_UI = "auto_ui"             # Extracted from UI components (buttons, forms, etc.)
    AUTO_OPENAPI = "auto_openapi"   # Imported from OpenAPI/Swagger spec
    AUTO_POSTMAN = "auto_postman"   # Imported from Postman collection
    MANUAL = "manual"               # Human-curated entry
    LLM_INFERRED = "llm_inferred"   # LLM identified from analyzing docs/code


class EdgeType(str, Enum):
    """Types of relationships between topic nodes."""
    OPERATES_ON = "operates_on"         # verb -> noun: "create" operates_on "User"
    PART_OF = "part_of"                 # noun -> noun: "Profile" part_of "User"
    PREREQUISITE_FOR = "prerequisite"   # concept -> concept: "auth" prerequisite for "permissions"
    RELATED_TO = "related_to"           # Any -> Any: loose association
    MODIFIES = "modifies"               # verb -> noun: "update" modifies "User"
    RETURNS = "returns"                 # verb -> noun: "list" returns "User[]"


class ContentType(str, Enum):
    """Types of documentation content."""
    REFERENCE = "reference"       # API/SDK reference docs (parameters, returns, errors)
    RECIPE = "recipe"             # Short how-to for single task
    COOKBOOK = "cookbook"         # E2E scenario, multi-step guide
    TUTORIAL = "tutorial"         # Learning-oriented walkthrough
    EXPLANATION = "explanation"   # Conceptual/background information
    CHANGELOG = "changelog"       # Version history, breaking changes


class DocCategory(str, Enum):
    """Source category of documentation."""
    CODE_DOCSTRING = "code-docstring"           # Inline docstrings in code
    AUTO_GENERATED = "auto-generated-reference" # From type hints, OpenAPI auto-gen
    MARKDOWN = "markdown"                       # Written markdown documentation
    EXTERNAL = "external"                       # Confluence, Notion, external wiki
    NONE = "none"                               # No documentation found


class ConfidenceLevel(str, Enum):
    """Confidence levels for ratings."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CompletenessLevel(str, Enum):
    """Completeness levels for documentation dimensions."""
    COMPLETE = "complete"   # Fully documented
    PARTIAL = "partial"     # Some coverage, gaps exist
    MISSING = "missing"     # Not documented


# =============================================================================
# QUALITY SCORING
# =============================================================================

class ScoreWithConfidence(BaseModel):
    """A quality score with associated confidence.

    Used for technical, semantic, and style scores. Each score has its own
    confidence level indicating how certain the rater (human or LLM) is.
    """
    level: CompletenessLevel = CompletenessLevel.MISSING
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    notes: Optional[str] = None


class TechnicalScore(BaseModel):
    """Technical/reference documentation quality.

    Measures whether the "what" is documented:
    - Parameters, arguments, inputs
    - Return values, outputs
    - Error codes, exceptions
    - Warnings for destructive/side-effect actions
    """
    has_parameters_docs: Literal["yes", "partial", "no"] = "no"
    has_return_docs: Literal["yes", "partial", "no"] = "no"
    has_error_docs: Literal["yes", "partial", "no"] = "no"
    has_warnings: bool = False  # Destructive actions, side effects flagged?

    # Overall score with confidence
    overall: ScoreWithConfidence = Field(default_factory=ScoreWithConfidence)

    def compute_overall(self) -> CompletenessLevel:
        """Compute overall technical score from components."""
        scores = [self.has_parameters_docs, self.has_return_docs, self.has_error_docs]
        if all(s == "yes" for s in scores) and self.has_warnings:
            return CompletenessLevel.COMPLETE
        elif all(s == "no" for s in scores):
            return CompletenessLevel.MISSING
        else:
            return CompletenessLevel.PARTIAL


class SemanticScore(BaseModel):
    """Semantic/conceptual documentation quality.

    Measures whether the "why/when/how" is documented:
    - What this does (description beyond just the signature)
    - When to use it (use cases)
    - When NOT to use it (anti-patterns, alternatives)
    - How it relates to other concepts
    """
    has_description: bool = False       # Beyond just function signature
    has_use_cases: bool = False         # When to use this
    has_anti_patterns: bool = False     # When NOT to use, gotchas
    has_context: bool = False           # How it relates to other features

    # Overall score with confidence
    overall: ScoreWithConfidence = Field(default_factory=ScoreWithConfidence)


class StyleScore(BaseModel):
    """Style and brand voice quality.

    Measures adherence to style guidelines:
    - Generic: Grammar, clarity, consistency, tone
    - Custom: Brand voice, terminology, formatting (paid feature)

    This is extensible for future brand voice customization.
    """
    # Generic style (free tier)
    grammar_quality: Optional[Literal["good", "acceptable", "poor"]] = None
    clarity: Optional[Literal["clear", "acceptable", "unclear"]] = None
    consistency: Optional[Literal["consistent", "inconsistent"]] = None

    # Custom brand voice (paid tier - placeholder for future)
    brand_voice_adherence: Optional[float] = None  # 0.0-1.0, None if not configured
    custom_rules_violations: list[str] = Field(default_factory=list)

    # Overall score with confidence
    overall: ScoreWithConfidence = Field(default_factory=ScoreWithConfidence)


class ExampleCoverage(BaseModel):
    """Example/sample code coverage."""
    has_generic_example: bool = False   # Auto-generated schema example (Swagger)
    has_use_case_example: bool = False  # Curated, realistic example
    has_error_example: bool = False     # Example of error handling
    example_is_runnable: bool = False   # Can be copy-pasted and run


class QualityScore(BaseModel):
    """Complete quality assessment for a topic's documentation.

    Combines all scoring dimensions with their individual confidences.
    """
    technical: TechnicalScore = Field(default_factory=TechnicalScore)
    semantic: SemanticScore = Field(default_factory=SemanticScore)
    style: StyleScore = Field(default_factory=StyleScore)
    examples: ExampleCoverage = Field(default_factory=ExampleCoverage)

    def summary(self) -> dict[str, str]:
        """Get a summary of quality scores."""
        return {
            "technical": self.technical.overall.level.value,
            "semantic": self.semantic.overall.level.value,
            "style": self.style.overall.level.value if self.style.overall.level else "not_scored",
        }


# =============================================================================
# TOPIC COVERAGE
# =============================================================================

class TopicCoverage(BaseModel):
    """Documentation coverage for a single topic node.

    This is the ATM data attached to each ITM node. It captures:
    - Whether documentation exists
    - Where it's located
    - Quality scores across all dimensions
    - Confidence in the discovery and scoring
    """
    # Basic coverage
    is_documented: bool = False
    category: DocCategory = DocCategory.NONE
    doc_locations: list[str] = Field(default_factory=list)  # file:line or URLs
    matched_content_preview: Optional[str] = None  # First N chars of matched doc

    # Discovery confidence: How confident that we found the right docs for this topic?
    # This is about the ATM→ITM mapping accuracy
    discovery_confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    discovery_method: Optional[Literal["exact", "vector", "llm", "manual"]] = None
    discovery_score: Optional[float] = None  # 0.0-1.0 similarity/match score

    # Quality scores (each has its own confidence)
    quality: QualityScore = Field(default_factory=QualityScore)

    # Review status
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None


# =============================================================================
# TOPIC NODES AND EDGES
# =============================================================================

class TopicNode(BaseModel):
    """A node in the product surface graph (ITM).

    Represents a documentable "thing" - an entity, action, or concept
    that users need to understand to use the product.
    """
    id: str  # Unique identifier, e.g., "user_noun", "create_verb", "auth_concept"
    type: NodeType
    name: str  # Human-readable: "User", "create", "authentication"
    description: Optional[str] = None

    # Classification
    node_class: NodeClass = NodeClass.USER_FACING
    is_excluded: bool = False  # Excluded from coverage calculations
    exclusion_reason: Optional[str] = None

    # Provenance
    source: NodeSource = NodeSource.MANUAL
    source_location: Optional[str] = None  # file:line, URL, or "manual"
    discovered_at: datetime = Field(default_factory=datetime.now)

    # For noun/verb nodes extracted from code
    code_signature: Optional[str] = None  # e.g., "POST /users/{user_id}/projects"

    # Manual curation
    is_verified: bool = False  # Human has confirmed this node is correct
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TopicNode):
            return self.id == other.id
        return False


class TopicEdge(BaseModel):
    """A relationship between two topic nodes."""
    source_id: str
    target_id: str
    relationship: EdgeType

    # Provenance
    source: NodeSource = NodeSource.MANUAL
    discovered_at: datetime = Field(default_factory=datetime.now)

    # Confidence
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    is_verified: bool = False


# =============================================================================
# CONTENT PIECES
# =============================================================================

class ContentPiece(BaseModel):
    """A piece of documentation content.

    Represents actual documentation (not the product surface). Content pieces
    cover one or more topic nodes and can be of various types.
    """
    id: str
    type: ContentType
    title: str
    location: str  # file:line or URL
    content_preview: Optional[str] = None  # First N chars

    # Which topic nodes does this content cover?
    covers_nodes: list[str] = Field(default_factory=list)  # node IDs

    # Metadata
    word_count: Optional[int] = None
    last_modified: Optional[datetime] = None

    # Quality (can be scored per content piece too)
    quality: Optional[QualityScore] = None


# =============================================================================
# THE MANIFEST
# =============================================================================

class TopicManifest(BaseModel):
    """Complete topic manifest combining ITM and ATM.

    The manifest contains:
    - Product surface (ITM): nodes + edges defining what SHOULD be documented
    - Documentation (ATM): content pieces + coverage data showing what IS documented

    This is the central data structure for DocZot analysis.
    """
    # Metadata
    product_name: str
    version: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.now)
    sources_analyzed: list[str] = Field(default_factory=list)

    # Product surface (ITM)
    nodes: list[TopicNode] = Field(default_factory=list)
    edges: list[TopicEdge] = Field(default_factory=list)

    # Documentation content (ATM)
    content: list[ContentPiece] = Field(default_factory=list)

    # Coverage data: node_id -> TopicCoverage
    coverage: dict[str, TopicCoverage] = Field(default_factory=dict)

    # ==========================================================================
    # GRAPH OPERATIONS
    # ==========================================================================

    def to_networkx(self) -> Any:
        """Convert to NetworkX DiGraph for graph operations.

        Raises:
            ImportError: If networkx is not installed
        """
        if not HAS_NETWORKX:
            raise ImportError("networkx is required for graph operations. Install with: pip install networkx")

        G = nx.DiGraph()

        for node in self.nodes:
            G.add_node(
                node.id,
                type=node.type.value,
                name=node.name,
                node_class=node.node_class.value,
                is_excluded=node.is_excluded,
            )

        for edge in self.edges:
            G.add_edge(
                edge.source_id,
                edge.target_id,
                relationship=edge.relationship.value,
            )

        return G

    @classmethod
    def from_networkx(cls, G: Any, metadata: dict) -> TopicManifest:
        """Create manifest from NetworkX graph.

        Args:
            G: NetworkX DiGraph
            metadata: Dict with product_name, version, etc.
        """
        nodes = []
        for node_id, attrs in G.nodes(data=True):
            nodes.append(TopicNode(
                id=node_id,
                type=NodeType(attrs.get("type", "noun")),
                name=attrs.get("name", node_id),
                node_class=NodeClass(attrs.get("node_class", "user-facing")),
                is_excluded=attrs.get("is_excluded", False),
            ))

        edges = []
        for src, tgt, attrs in G.edges(data=True):
            edges.append(TopicEdge(
                source_id=src,
                target_id=tgt,
                relationship=EdgeType(attrs.get("relationship", "related_to")),
            ))

        return cls(nodes=nodes, edges=edges, **metadata)

    # ==========================================================================
    # ANALYSIS HELPERS
    # ==========================================================================

    def get_node(self, node_id: str) -> Optional[TopicNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_coverage(self, node_id: str) -> TopicCoverage:
        """Get coverage for a node, returning empty coverage if not found."""
        return self.coverage.get(node_id, TopicCoverage())

    def user_facing_nodes(self) -> list[TopicNode]:
        """Get nodes that should be counted in coverage %."""
        return [n for n in self.nodes if n.node_class == NodeClass.USER_FACING and not n.is_excluded]

    def internal_nodes(self) -> list[TopicNode]:
        """Get internal/meta nodes (excluded from coverage %)."""
        return [n for n in self.nodes if n.node_class in (NodeClass.INTERNAL, NodeClass.META)]

    def undocumented_nodes(self) -> list[TopicNode]:
        """Get user-facing nodes without documentation."""
        return [
            n for n in self.user_facing_nodes()
            if not self.get_coverage(n.id).is_documented
        ]

    def nodes_missing_errors(self) -> list[TopicNode]:
        """Get nodes where error documentation is missing."""
        return [
            n for n in self.user_facing_nodes()
            if self.get_coverage(n.id).quality.technical.has_error_docs == "no"
        ]

    def nodes_missing_warnings(self) -> list[TopicNode]:
        """Get nodes where warnings for destructive actions are missing."""
        return [
            n for n in self.user_facing_nodes()
            if not self.get_coverage(n.id).quality.technical.has_warnings
            and n.type == NodeType.VERB  # Only verbs typically need warnings
        ]

    def nodes_missing_examples(self) -> list[TopicNode]:
        """Get nodes without curated examples."""
        return [
            n for n in self.user_facing_nodes()
            if not self.get_coverage(n.id).quality.examples.has_use_case_example
        ]

    def low_semantic_quality_nodes(self) -> list[TopicNode]:
        """Get nodes with missing or partial semantic documentation."""
        return [
            n for n in self.user_facing_nodes()
            if self.get_coverage(n.id).quality.semantic.overall.level in (
                CompletenessLevel.MISSING, CompletenessLevel.PARTIAL
            )
        ]

    # ==========================================================================
    # STATISTICS
    # ==========================================================================

    def coverage_stats(self) -> dict:
        """Get coverage statistics summary."""
        user_facing = self.user_facing_nodes()
        total = len(user_facing)

        if total == 0:
            return {
                "total_topics": 0,
                "documented": 0,
                "undocumented": 0,
                "coverage_percentage": 0.0,
                "internal_topics": len(self.internal_nodes()),
            }

        documented = sum(1 for n in user_facing if self.get_coverage(n.id).is_documented)

        return {
            "total_topics": total,
            "documented": documented,
            "undocumented": total - documented,
            "coverage_percentage": round((documented / total) * 100, 1),
            "internal_topics": len(self.internal_nodes()),
            "by_type": {
                t.value: len([n for n in user_facing if n.type == t])
                for t in NodeType
            },
        }

    def quality_stats(self) -> dict:
        """Get quality statistics across all documented topics."""
        user_facing = self.user_facing_nodes()
        documented = [n for n in user_facing if self.get_coverage(n.id).is_documented]

        if not documented:
            return {"message": "No documented topics to analyze"}

        return {
            "total_documented": len(documented),
            "missing_error_docs": len(self.nodes_missing_errors()),
            "missing_warnings": len(self.nodes_missing_warnings()),
            "missing_examples": len(self.nodes_missing_examples()),
            "low_semantic_quality": len(self.low_semantic_quality_nodes()),
            "technical_complete": sum(
                1 for n in documented
                if self.get_coverage(n.id).quality.technical.overall.level == CompletenessLevel.COMPLETE
            ),
            "semantic_complete": sum(
                1 for n in documented
                if self.get_coverage(n.id).quality.semantic.overall.level == CompletenessLevel.COMPLETE
            ),
        }

    def sprint_plan(self) -> dict[str, list[dict]]:
        """Generate an actionable sprint plan from coverage gaps.

        Returns a dict organized by action type, each containing a list of
        specific tasks with file:line references.
        """
        plan = {
            "add_error_documentation": [],
            "add_warnings": [],
            "add_examples": [],
            "improve_semantic_docs": [],
            "document_undocumented": [],
        }

        for node in self.undocumented_nodes():
            plan["document_undocumented"].append({
                "node_id": node.id,
                "name": node.name,
                "type": node.type.value,
                "location": node.source_location,
                "action": f"Add documentation for {node.type.value}: {node.name}",
            })

        for node in self.nodes_missing_errors():
            cov = self.get_coverage(node.id)
            if cov.is_documented:  # Only if already documented
                plan["add_error_documentation"].append({
                    "node_id": node.id,
                    "name": node.name,
                    "location": node.source_location,
                    "action": f"Add error response documentation",
                })

        for node in self.nodes_missing_warnings():
            cov = self.get_coverage(node.id)
            if cov.is_documented:
                plan["add_warnings"].append({
                    "node_id": node.id,
                    "name": node.name,
                    "location": node.source_location,
                    "action": f"Add warning about destructive/side-effect action",
                })

        for node in self.nodes_missing_examples():
            cov = self.get_coverage(node.id)
            if cov.is_documented:
                plan["add_examples"].append({
                    "node_id": node.id,
                    "name": node.name,
                    "location": node.source_location,
                    "action": f"Add curated example with realistic data",
                })

        for node in self.low_semantic_quality_nodes():
            cov = self.get_coverage(node.id)
            if cov.is_documented:
                plan["improve_semantic_docs"].append({
                    "node_id": node.id,
                    "name": node.name,
                    "location": node.source_location,
                    "action": f"Add why/when/how explanation",
                })

        # Remove empty categories
        return {k: v for k, v in plan.items() if v}
