"""DocZot v2 Data Models - Four Layer Architecture.

This module defines the core data structures for documentation coverage analysis:

Layer 1: SYSTEM GRAPH (auto-scanned)
    Graph of code entities, endpoints, and relationships.
    Immutable snapshot of the codebase at a point in time.

Layer 2: COVERAGE CHECKLIST (the plan)
    The checklist of required documentation topics based on the System Graph.
    Auto-suggested from graph, then human-curated.

Layer 3: CONTENT INVENTORY (the reality)
    The discovered catalog of existing documentation assets.
    Auto-parsed from actual documentation, scored for quality.

Layer 4: DRIFT REPORT (computed: Checklist - Inventory)
    The divergence between Code State (System Graph) and Documentation State.
    Missing topics, incomplete coverage, quality scores. Drives the sprint plan.

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │  SYSTEM GRAPH (immutable scan)                                  │
    │  Nodes: verbs, nouns, concepts, constraints                     │
    │  Edges: operates_on, part_of, related_to, constrained_by        │
    └─────────────────────────────────────────────────────────────────┘
                              ↓ grouped into
    ┌─────────────────────────────────────────────────────────────────┐
    │  COVERAGE CHECKLIST (the plan)                                  │
    │  Topics covering graph elements                                 │
    │  "User Management" covers [POST /users, GET /users, user noun]  │
    └─────────────────────────────────────────────────────────────────┘
                              ↓ compared against
    ┌─────────────────────────────────────────────────────────────────┐
    │  CONTENT INVENTORY (the reality)                                │
    │  Topics discovered from existing documentation                  │
    │  "Users API" found in docs/api/users.md                         │
    └─────────────────────────────────────────────────────────────────┘
                              ↓ produces
    ┌─────────────────────────────────────────────────────────────────┐
    │  DRIFT REPORT                                                   │
    │  Documentation drift, coverage %, quality scores, sprint plan   │
    └─────────────────────────────────────────────────────────────────┘

Terminology Mapping (internal → industry standard):
    SurfaceGraph → SystemGraph
    ITM (TopicManifest) → CoverageChecklist
    ATM (TopicManifest) → ContentInventory
    GapReport → DriftReport
    Coverage → Documentation Coverage
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
    """Types of nodes in the system graph."""
    NOUN = "noun"           # Entities: User, Project, Invoice
    VERB = "verb"           # Actions: create, delete, configure
    CONCEPT = "concept"     # Ideas: authentication, rate limiting
    CONSTRAINT = "constraint"  # Permissions, rate limits, prerequisites


class NodeClass(str, Enum):
    """Classification of nodes for coverage calculation."""
    USER_FACING = "user-facing"
    INTERNAL = "internal"
    META = "meta"
    DEPRECATED = "deprecated"


class EdgeType(str, Enum):
    """Types of relationships between system graph nodes."""
    OPERATES_ON = "operates_on"         # verb -> noun
    PART_OF = "part_of"                 # noun -> noun
    RELATED_TO = "related_to"           # any -> any
    PREREQUISITE = "prerequisite"       # concept -> concept, verb -> verb
    CONSTRAINED_BY = "constrained_by"   # verb -> constraint


class TopicType(str, Enum):
    """Types of documentation topics."""
    ONBOARDING = "onboarding"   # Getting started, quick starts
    CONCEPT = "concept"         # Explanatory content
    TASK = "task"               # How-tos, journeys (varying length)
    REFERENCE = "reference"     # API/SDK reference
    CHANGES = "changes"         # Roadmap, releases, deprecations


class ManifestType(str, Enum):
    """Type of topic manifest: Coverage Matrix (plan) or Content Inventory (reality)."""
    INTENDED = "intended"  # Coverage Checklist - the plan
    ACTUAL = "actual"      # Content Inventory - the reality
    # Aliases for new terminology
    COVERAGE_MATRIX = "intended"  # Alias
    INVENTORY = "actual"  # Alias


class ConfidenceLevel(str, Enum):
    """Confidence levels for automated detection."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =============================================================================
# LAYER 1: KNOWLEDGE GRAPH (formerly Surface Graph)
# =============================================================================

class SystemNode(BaseModel):
    """A node in the software system graph.

    Represents a semantic element from the codebase: an endpoint, entity, or concept.
    """
    id: str                          # e.g., "verb:POST:/users", "noun:user"
    type: NodeType
    name: str                        # Human-readable: "create_user", "user"
    description: Optional[str] = None

    # Classification
    node_class: NodeClass = NodeClass.USER_FACING

    # Source location in code
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    code_signature: Optional[str] = None  # e.g., "POST /users/{id}"

    # For verbs: HTTP method info
    http_method: Optional[str] = None
    http_path: Optional[str] = None

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SystemNode):
            return self.id == other.id
        return False


class SystemEdge(BaseModel):
    """A relationship between two system graph nodes."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class SystemGraph(BaseModel):
    """Layer 1: System Graph - semantic map of code.

    Immutable snapshot of all endpoints, entities, concepts, and their
    relationships discovered in the codebase.
    """
    # Metadata
    product_name: str
    version: Optional[str] = None
    scanned_at: datetime = Field(default_factory=datetime.now)
    source_paths: list[str] = Field(default_factory=list)

    # Graph data
    nodes: list[SystemNode] = Field(default_factory=list)
    edges: list[SystemEdge] = Field(default_factory=list)

    # ==========================================================================
    # GRAPH ACCESSORS
    # ==========================================================================

    def get_node(self, node_id: str) -> Optional[SystemNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def nodes_by_type(self, node_type: NodeType) -> list[SystemNode]:
        """Get all nodes of a specific type."""
        return [n for n in self.nodes if n.type == node_type]

    @property
    def nouns(self) -> list[SystemNode]:
        return self.nodes_by_type(NodeType.NOUN)

    @property
    def verbs(self) -> list[SystemNode]:
        return self.nodes_by_type(NodeType.VERB)

    @property
    def concepts(self) -> list[SystemNode]:
        return self.nodes_by_type(NodeType.CONCEPT)

    @property
    def constraints(self) -> list[SystemNode]:
        return self.nodes_by_type(NodeType.CONSTRAINT)

    def verbs_for_noun(self, noun_id: str) -> list[SystemNode]:
        """Get all verbs that operate on a noun."""
        verb_ids = [
            e.source_id for e in self.edges
            if e.target_id == noun_id and e.edge_type == EdgeType.OPERATES_ON
        ]
        return [n for n in self.nodes if n.id in verb_ids]

    def noun_for_verb(self, verb_id: str) -> Optional[SystemNode]:
        """Get the primary noun a verb operates on."""
        for edge in self.edges:
            if edge.source_id == verb_id and edge.edge_type == EdgeType.OPERATES_ON:
                return self.get_node(edge.target_id)
        return None

    def orphan_verbs(self) -> list[SystemNode]:
        """Get verbs not connected to any noun."""
        connected_verb_ids = {
            e.source_id for e in self.edges
            if e.edge_type == EdgeType.OPERATES_ON
        }
        return [v for v in self.verbs if v.id not in connected_verb_ids]

    def user_facing_nodes(self) -> list[SystemNode]:
        """Get nodes that should be documented."""
        return [n for n in self.nodes if n.node_class == NodeClass.USER_FACING]

    # ==========================================================================
    # NETWORKX CONVERSION
    # ==========================================================================

    def to_networkx(self) -> Any:
        """Convert to NetworkX graph for visualization/analysis."""
        if not HAS_NETWORKX:
            raise ImportError("networkx required: pip install networkx")

        G = nx.DiGraph()
        for node in self.nodes:
            G.add_node(node.id, **node.model_dump())
        for edge in self.edges:
            G.add_edge(edge.source_id, edge.target_id,
                      edge_type=edge.edge_type.value)
        return G


# =============================================================================
# LAYER 2 & 3: CONTENT COVERAGE MATRIX / CONTENT INVENTORY
# =============================================================================

class MatchEvidence(BaseModel):
    """Evidence for why a surface node was matched to a doc topic.

    Captures the reasoning behind coverage matches so reviewers can
    validate whether matches are correct or spurious.
    """
    node_id: str
    strategy: Literal["direct_reference", "semantic"]
    confidence: float  # 0.0-1.0
    doc_file: str
    doc_section: Optional[str] = None
    doc_snippet: str = ""  # First ~200 chars of matching content
    match_detail: str = ""  # e.g. "GET /users/ found in text" or "similarity: 0.42"


class Topic(BaseModel):
    """A documentation topic that covers system graph elements.

    Topics are the logical groupings that organize documentation.
    A single topic might cover multiple graph nodes.
    """
    id: str
    name: str                        # "User Management", "Authentication"
    topic_type: TopicType

    # What surface elements does this topic cover?
    covers: list[str] = Field(default_factory=list)  # Surface node IDs

    # Match evidence: why each node was matched to this topic
    match_evidence: list[MatchEvidence] = Field(default_factory=list)

    # Hierarchy (arbitrary depth, but keep flat when possible)
    parent_id: Optional[str] = None
    children: list[str] = Field(default_factory=list)  # Child topic IDs

    # For task-based topics
    task_scope: Optional[Literal["quick", "journey"]] = None

    # Source (for ATM - where was this topic found?)
    source_file: Optional[str] = None
    source_line: Optional[int] = None

    # Curation metadata
    auto_generated: bool = True
    curated_by: Optional[str] = None
    curated_at: Optional[datetime] = None
    priority: Optional[int] = None  # User-set priority for ITM


class TopicQuality(BaseModel):
    """Quality assessment for an actual topic (ATM only)."""
    # Technical completeness
    has_parameters: Literal["yes", "partial", "no"] = "no"
    has_returns: Literal["yes", "partial", "no"] = "no"
    has_errors: Literal["yes", "partial", "no"] = "no"
    has_warnings: bool = False

    # Semantic completeness
    has_description: bool = False
    has_use_cases: bool = False
    has_examples: bool = False

    # Constraint coverage (v3)
    has_auth_requirements: Literal["yes", "partial", "no"] = "no"
    has_rate_limits: Literal["yes", "partial", "no"] = "no"
    has_prerequisites: Literal["yes", "partial", "no"] = "no"

    # Agent navigability (v3)
    has_machine_readable_spec: bool = False
    terminology_consistent: bool = False

    # Overall scores
    coverage_score: float = 0.0  # 0.0 - 1.0
    constraint_score: float = 0.0  # 0.0 - 1.0 (v3)
    agent_readiness_score: float = 0.0  # 0.0 - 1.0 (v3)


class TopicManifest(BaseModel):
    """Layer 2/3: Topic organization - Coverage Checklist or Content Inventory.

    Coverage Checklist (INTENDED): The plan - topics that SHOULD exist
    Content Inventory (ACTUAL): The reality - topics that DO exist in docs
    """
    # Identity
    manifest_type: ManifestType
    graph_id: str              # Links to which SystemGraph this covers

    # Metadata
    product_name: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Topics
    topics: list[Topic] = Field(default_factory=list)

    # For ATM: quality scores per topic
    quality: dict[str, TopicQuality] = Field(default_factory=dict)

    # ==========================================================================
    # TOPIC ACCESSORS
    # ==========================================================================

    def get_topic(self, topic_id: str) -> Optional[Topic]:
        """Get a topic by ID."""
        for topic in self.topics:
            if topic.id == topic_id:
                return topic
        return None

    def topics_by_type(self, topic_type: TopicType) -> list[Topic]:
        """Get all topics of a specific type."""
        return [t for t in self.topics if t.topic_type == topic_type]

    def root_topics(self) -> list[Topic]:
        """Get top-level topics (no parent)."""
        return [t for t in self.topics if t.parent_id is None]

    def children_of(self, topic_id: str) -> list[Topic]:
        """Get child topics of a topic."""
        return [t for t in self.topics if t.parent_id == topic_id]

    def covered_surface_ids(self) -> set[str]:
        """Get all surface node IDs covered by any topic."""
        covered = set()
        for topic in self.topics:
            covered.update(topic.covers)
        return covered

    def uncovered_node_ids(self, graph: SystemGraph) -> list[str]:
        """Get system graph node IDs not covered by any topic."""
        covered = self.covered_surface_ids()
        return [n.id for n in graph.user_facing_nodes() if n.id not in covered]

    def topics_covering(self, surface_id: str) -> list[Topic]:
        """Get all topics that cover a specific surface node."""
        return [t for t in self.topics if surface_id in t.covers]


# =============================================================================
# LAYER 4: DRIFT REPORT (formerly Gap Report)
# =============================================================================

class DriftItem(BaseModel):
    """A drift item between Coverage Matrix and Content Inventory."""
    matrix_topic_id: str       # Topic from Coverage Checklist
    matrix_topic_name: str
    inventory_topic_id: Optional[str] = None  # Matched inventory topic, if any

    # Coverage status
    status: Literal["missing", "partial", "complete", "extra"]

    # What's drifted/missing?
    missing_node_ids: list[str] = Field(default_factory=list)

    # Quality issues (if inventory topic exists)
    quality_issues: list[str] = Field(default_factory=list)

    # Sprint plan action
    action: str = ""
    priority: int = 0


class DriftReport(BaseModel):
    """Layer 4: Documentation Drift Report.

    Measures the divergence between Code State (System Graph) and
    Documentation State (Content Inventory). Drives the sprint plan.
    """
    # Links
    graph_id: str              # System Graph ID
    matrix_id: str             # Coverage Checklist ID
    inventory_id: str          # Content Inventory ID

    # Metadata
    generated_at: datetime = Field(default_factory=datetime.now)
    product_name: str

    # Drift items
    drift_items: list[DriftItem] = Field(default_factory=list)

    # Extra topics in inventory not in matrix (potential undocumented features)
    extra_topics: list[str] = Field(default_factory=list)

    # ==========================================================================
    # STATISTICS
    # ==========================================================================

    def coverage_stats(self) -> dict:
        """Get documentation coverage statistics."""
        total = len(self.drift_items)
        if total == 0:
            return {"coverage_percentage": 0.0, "total": 0}

        complete = sum(1 for d in self.drift_items if d.status == "complete")
        partial = sum(1 for d in self.drift_items if d.status == "partial")
        missing = sum(1 for d in self.drift_items if d.status == "missing")

        return {
            "total_topics": total,
            "complete": complete,
            "partial": partial,
            "missing": missing,
            "extra": len(self.extra_topics),
            "coverage_percentage": round((complete + partial * 0.5) / total * 100, 1),
        }

    def sprint_plan(self) -> list[dict]:
        """Generate prioritized sprint plan to fix drift."""
        plan = []
        for item in sorted(self.drift_items, key=lambda d: d.priority, reverse=True):
            if item.status in ("missing", "partial"):
                plan.append({
                    "topic": item.matrix_topic_name,
                    "status": item.status,
                    "action": item.action,
                    "missing_items": len(item.missing_node_ids),
                    "quality_issues": item.quality_issues,
                    "priority": item.priority,
                })
        return plan


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def generate_default_itm(graph: SystemGraph) -> TopicManifest:
    """Generate default Coverage Checklist from a System Graph.

    Default strategy: Type-first hierarchical structure.
    - Reference > API > [Entity] > [Endpoint topics]
    - Concept > Entity > [Entity concept topics]
    """
    topics = []
    topic_id_counter = 0

    def next_id() -> str:
        nonlocal topic_id_counter
        topic_id_counter += 1
        return f"topic_{topic_id_counter}"

    def verb_to_title(verb: SystemNode) -> str:
        """Generate a readable title for an endpoint."""
        method = verb.http_method or "CALL"
        # Extract resource from path
        if verb.http_path:
            parts = [p for p in verb.http_path.split('/') if p and not p.startswith('{')]
            resource = parts[-1] if parts else "resource"
            # Check if path has ID parameter
            has_id = '{' in verb.http_path
            if method == "GET" and not has_id:
                return f"List {resource}"
            elif method == "GET" and has_id:
                return f"Get {resource}"
            elif method == "POST":
                return f"Create {resource}"
            elif method == "PUT" or method == "PATCH":
                return f"Update {resource}"
            elif method == "DELETE":
                return f"Delete {resource}"
        return verb.name.replace("_", " ").title()

    # ==========================================================================
    # REFERENCE > API section
    # ==========================================================================
    reference_id = next_id()
    api_id = next_id()
    api_entity_ids = []

    # Create entity groups under API
    for noun in graph.nouns:
        related_verbs = graph.verbs_for_noun(noun.id)
        entity_topic_id = next_id()
        api_entity_ids.append(entity_topic_id)
        endpoint_ids = []

        # Create sub-topic for each endpoint
        for verb in related_verbs:
            endpoint_topic_id = next_id()
            endpoint_ids.append(endpoint_topic_id)

            endpoint_topic = Topic(
                id=endpoint_topic_id,
                name=verb_to_title(verb),
                topic_type=TopicType.REFERENCE,
                covers=[verb.id],
                parent_id=entity_topic_id,
                auto_generated=True,
            )
            topics.append(endpoint_topic)

        # Create entity API topic
        entity_topic = Topic(
            id=entity_topic_id,
            name=noun.name.replace("_", " ").title(),
            topic_type=TopicType.REFERENCE,
            covers=[],  # Container only
            parent_id=api_id,
            children=endpoint_ids,
            auto_generated=True,
        )
        topics.append(entity_topic)

    # Handle orphan verbs - group by theme under API
    orphans = graph.orphan_verbs()
    if orphans:
        themes: dict[str, list[SystemNode]] = {}
        for verb in orphans:
            if verb.http_path:
                parts = [p for p in verb.http_path.split('/') if p and not p.startswith('{')]
                theme = parts[0] if parts else "general"
            else:
                theme = "general"
            if theme not in themes:
                themes[theme] = []
            themes[theme].append(verb)

        for theme, verbs in themes.items():
            theme_topic_id = next_id()
            api_entity_ids.append(theme_topic_id)
            endpoint_ids = []

            for verb in verbs:
                endpoint_topic_id = next_id()
                endpoint_ids.append(endpoint_topic_id)
                endpoint_topic = Topic(
                    id=endpoint_topic_id,
                    name=verb_to_title(verb),
                    topic_type=TopicType.REFERENCE,
                    covers=[verb.id],
                    parent_id=theme_topic_id,
                    auto_generated=True,
                )
                topics.append(endpoint_topic)

            theme_topic = Topic(
                id=theme_topic_id,
                name=theme.replace("_", " ").title(),
                topic_type=TopicType.REFERENCE,
                covers=[],
                parent_id=api_id,
                children=endpoint_ids,
                auto_generated=True,
            )
            topics.append(theme_topic)

    # Create API container topic
    api_topic = Topic(
        id=api_id,
        name="API",
        topic_type=TopicType.REFERENCE,
        covers=[],
        parent_id=reference_id,
        children=api_entity_ids,
        auto_generated=True,
    )
    topics.append(api_topic)

    # Create Reference root topic
    reference_topic = Topic(
        id=reference_id,
        name="Reference",
        topic_type=TopicType.REFERENCE,
        covers=[],
        children=[api_id],
        auto_generated=True,
    )
    topics.append(reference_topic)

    # ==========================================================================
    # CONCEPT > Entity section
    # ==========================================================================
    concept_id = next_id()
    entity_section_id = next_id()
    entity_concept_ids = []

    # Create concept topic for each entity (noun)
    for noun in graph.nouns:
        entity_concept_id = next_id()
        entity_concept_ids.append(entity_concept_id)

        entity_concept = Topic(
            id=entity_concept_id,
            name=noun.name.replace("_", " ").title(),
            topic_type=TopicType.CONCEPT,
            covers=[noun.id],  # Concept covers the noun
            parent_id=entity_section_id,
            auto_generated=True,
        )
        topics.append(entity_concept)

    # Create Entity container topic
    entity_section = Topic(
        id=entity_section_id,
        name="Entity",
        topic_type=TopicType.CONCEPT,
        covers=[],
        parent_id=concept_id,
        children=entity_concept_ids,
        auto_generated=True,
    )
    topics.append(entity_section)

    # Create Concept root topic
    concept_topic = Topic(
        id=concept_id,
        name="Concept",
        topic_type=TopicType.CONCEPT,
        covers=[],
        children=[entity_section_id],
        auto_generated=True,
    )
    topics.append(concept_topic)

    # 3. Concept topics for standalone concepts
    for concept in graph.concepts:
        topic = Topic(
            id=next_id(),
            name=concept.name.replace("_", " ").title(),
            topic_type=TopicType.CONCEPT,
            covers=[concept.id],
            auto_generated=True,
        )
        topics.append(topic)

    # ==========================================================================
    # TASK (How-to) section - infer common journeys
    # ==========================================================================
    task_id = next_id()
    howto_ids = []

    # Helper to find verbs by path pattern
    def find_verbs_by_pattern(patterns: list[str]) -> list[str]:
        """Find verb IDs matching path patterns."""
        matches = []
        for verb in graph.verbs:
            if verb.http_path:
                for pattern in patterns:
                    if pattern in verb.http_path.lower():
                        matches.append(verb.id)
                        break
        return matches

    # Detect auth flow: signup, login, token
    auth_verbs = find_verbs_by_pattern(['signup', 'login', 'access-token', 'register'])
    if len(auth_verbs) >= 2:
        howto_id = next_id()
        howto_ids.append(howto_id)
        # Auth flows operate on users, so include user noun if present
        user_noun = next((n for n in graph.nouns if n.name == 'user'), None)
        auth_covers = ([user_noun.id] if user_noun else []) + auth_verbs
        topics.append(Topic(
            id=howto_id,
            name="How to authenticate",
            topic_type=TopicType.TASK,
            covers=auth_covers,
            parent_id=task_id,
            auto_generated=True,
        ))

    # Detect account management: me endpoints
    me_verbs = find_verbs_by_pattern(['/me', '/self', '/current'])
    if me_verbs:
        howto_id = next_id()
        howto_ids.append(howto_id)
        topics.append(Topic(
            id=howto_id,
            name="How to manage your account",
            topic_type=TopicType.TASK,
            covers=me_verbs,
            parent_id=task_id,
            auto_generated=True,
        ))

    # Detect password recovery flow
    password_verbs = find_verbs_by_pattern(['password-recovery', 'reset-password', 'forgot'])
    if password_verbs:
        howto_id = next_id()
        howto_ids.append(howto_id)
        topics.append(Topic(
            id=howto_id,
            name="How to recover your password",
            topic_type=TopicType.TASK,
            covers=password_verbs,
            parent_id=task_id,
            auto_generated=True,
        ))

    # Detect CRUD flows for each entity (if has create + list/get)
    for noun in graph.nouns:
        verbs = graph.verbs_for_noun(noun.id)
        methods = {v.http_method for v in verbs if v.http_method}
        # Only suggest CRUD how-to if entity has meaningful operations
        if 'POST' in methods and ('GET' in methods or 'PUT' in methods):
            entity_name = noun.name.replace("_", " ").title()
            # Skip utility entities
            if noun.name.lower() not in ['util', 'utils', 'health', 'test']:
                howto_id = next_id()
                howto_ids.append(howto_id)
                topics.append(Topic(
                    id=howto_id,
                    name=f"How to work with {entity_name}s",
                    topic_type=TopicType.TASK,
                    covers=[noun.id] + [v.id for v in verbs],  # Include the noun!
                    parent_id=task_id,
                    auto_generated=True,
                ))

    # Create Task root topic if we found any how-tos
    if howto_ids:
        task_topic = Topic(
            id=task_id,
            name="Task",
            topic_type=TopicType.TASK,
            covers=[],
            children=howto_ids,
            auto_generated=True,
        )
        topics.append(task_topic)

    return TopicManifest(
        manifest_type=ManifestType.INTENDED,
        graph_id=f"{graph.product_name}:{graph.scanned_at.isoformat()}",
        product_name=graph.product_name,
        topics=topics,
    )


def compute_drift_report(
    graph: SystemGraph,
    matrix: TopicManifest,
    inventory: TopicManifest,
) -> DriftReport:
    """Compute documentation drift between Coverage Matrix and Content Inventory.

    Matches matrix topics to inventory topics and identifies drift.
    """
    drift_items = []
    matched_inventory_ids = set()

    for matrix_topic in matrix.topics:
        # Skip structural parent topics that don't cover anything directly
        # These are just organizational hierarchy (e.g., "Reference", "API", "Entity")
        if not matrix_topic.covers and matrix_topic.children:
            continue
        # Find matching inventory topic (by name similarity or coverage overlap)
        best_match = None
        best_overlap = 0

        for inv_topic in inventory.topics:
            # Check coverage overlap
            matrix_covers = set(matrix_topic.covers)
            inv_covers = set(inv_topic.covers)
            overlap = len(matrix_covers & inv_covers)

            if overlap > best_overlap:
                best_overlap = overlap
                best_match = inv_topic

        # Determine drift status
        if best_match and best_overlap > 0:
            matched_inventory_ids.add(best_match.id)
            matrix_covers = set(matrix_topic.covers)
            inv_covers = set(best_match.covers)
            missing = matrix_covers - inv_covers

            if not missing:
                status = "complete"
                action = ""
            else:
                status = "partial"
                action = f"Add coverage for {len(missing)} missing elements"

            # Check quality
            quality_issues = []
            if best_match.id in inventory.quality:
                q = inventory.quality[best_match.id]
                if q.has_errors == "no":
                    quality_issues.append("missing error docs")
                if not q.has_examples:
                    quality_issues.append("missing examples")
                if not q.has_use_cases:
                    quality_issues.append("missing use cases")
                # v3: Constraint coverage gaps
                # Check if covered verbs have constraints that aren't documented
                covered_verbs = [nid for nid in best_match.covers if nid.startswith("verb:")]
                has_auth_constraint = False
                has_rate_constraint = False
                for verb_id in covered_verbs:
                    for edge in graph.edges:
                        if edge.source_id == verb_id and edge.edge_type == EdgeType.CONSTRAINED_BY:
                            target = next((n for n in graph.nodes if n.id == edge.target_id), None)
                            if target and "auth" in target.name:
                                has_auth_constraint = True
                            if target and "rate_limit" in target.name:
                                has_rate_constraint = True
                if has_auth_constraint and q.has_auth_requirements == "no":
                    quality_issues.append("auth-protected endpoint but no auth docs")
                if has_rate_constraint and q.has_rate_limits == "no":
                    quality_issues.append("rate-limited endpoint but no rate limit docs")
                # Terminology consistency
                if not q.terminology_consistent:
                    quality_issues.append("inconsistent terminology with codebase")

            item = DriftItem(
                matrix_topic_id=matrix_topic.id,
                matrix_topic_name=matrix_topic.name,
                inventory_topic_id=best_match.id,
                status=status,
                missing_node_ids=list(missing),
                quality_issues=quality_issues,
                action=action,
                priority=matrix_topic.priority or 0,
            )
        else:
            item = DriftItem(
                matrix_topic_id=matrix_topic.id,
                matrix_topic_name=matrix_topic.name,
                status="missing",
                missing_node_ids=matrix_topic.covers,
                action=f"Create new {matrix_topic.topic_type.value} topic: {matrix_topic.name}",
                priority=matrix_topic.priority or 0,
            )

        drift_items.append(item)

    # Find extra inventory topics not in matrix (potential undocumented features)
    extra = [t.id for t in inventory.topics if t.id not in matched_inventory_ids]

    return DriftReport(
        graph_id=graph.product_name,
        matrix_id=matrix.graph_id,
        inventory_id=inventory.graph_id,
        product_name=graph.product_name,
        drift_items=drift_items,
        extra_topics=extra,
    )


# =============================================================================
# BACKWARD COMPATIBILITY ALIASES
# These aliases maintain compatibility with code using old terminology.
# New code should use: SystemGraph, SystemNode, SystemEdge,
#                      DriftReport, DriftItem, compute_drift_report
# =============================================================================

# Layer 1: Surface Graph → System Graph
SurfaceGraph = SystemGraph
SurfaceNode = SystemNode
SurfaceEdge = SystemEdge

# Layer 4: Gap Report → Drift Report
GapReport = DriftReport
TopicGap = DriftItem
compute_gap_report = compute_drift_report

# Type aliases for clarity
CoverageChecklist = TopicManifest       # When manifest_type == INTENDED (the plan)
ContentInventory = TopicManifest        # When manifest_type == ACTUAL (the reality)

# Also support legacy name
ContentCoverageMatrix = TopicManifest   # Legacy alias

# Additional aliases for Knowledge Graph terminology (for users preferring that)
KnowledgeGraph = SystemGraph
KnowledgeNode = SystemNode
KnowledgeEdge = SystemEdge
