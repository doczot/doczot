"""DocZot v2 Data Models - Four Layer Architecture.

This module defines the core data structures for documentation coverage analysis:

Layer 1: SURFACE GRAPH (auto-scanned)
    Raw product elements from code: endpoints, entities, concepts
    Immutable snapshot of the codebase at a point in time

Layer 2: TOPIC MANIFEST - ITM (Intended)
    The PLAN: Topics that SHOULD exist, covering surface elements
    Auto-suggested from surface, then human-curated

Layer 3: TOPIC MANIFEST - ATM (Actual)
    The REALITY: Topics that DO exist, discovered from docs
    Auto-parsed from actual documentation

Layer 4: GAP REPORT (computed: ITM - ATM)
    Missing topics, incomplete coverage, quality scores
    Drives the sprint plan

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │  SURFACE GRAPH (immutable scan)                                 │
    │  Nodes: verbs, nouns, concepts                                  │
    │  Edges: operates_on, part_of, related_to                        │
    └─────────────────────────────────────────────────────────────────┘
                              ↓ grouped into
    ┌─────────────────────────────────────────────────────────────────┐
    │  ITM - INTENDED TOPIC MANIFEST                                  │
    │  Topics covering surface elements                               │
    │  "User Management" covers [POST /users, GET /users, user noun]  │
    └─────────────────────────────────────────────────────────────────┘
                              ↓ compared against
    ┌─────────────────────────────────────────────────────────────────┐
    │  ATM - ACTUAL TOPIC MANIFEST                                    │
    │  Topics discovered from existing documentation                  │
    │  "Users API" found in docs/api/users.md                         │
    └─────────────────────────────────────────────────────────────────┘
                              ↓ produces
    ┌─────────────────────────────────────────────────────────────────┐
    │  GAP REPORT                                                     │
    │  Missing topics, coverage %, quality scores, sprint plan        │
    └─────────────────────────────────────────────────────────────────┘
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
    """Types of nodes in the product surface graph."""
    NOUN = "noun"       # Entities: User, Project, Invoice
    VERB = "verb"       # Actions: create, delete, configure
    CONCEPT = "concept" # Ideas: authentication, rate limiting


class NodeClass(str, Enum):
    """Classification of nodes for coverage calculation."""
    USER_FACING = "user-facing"
    INTERNAL = "internal"
    META = "meta"
    DEPRECATED = "deprecated"


class EdgeType(str, Enum):
    """Types of relationships between surface nodes."""
    OPERATES_ON = "operates_on"     # verb -> noun
    PART_OF = "part_of"             # noun -> noun
    RELATED_TO = "related_to"       # any -> any
    PREREQUISITE = "prerequisite"   # concept -> concept


class TopicType(str, Enum):
    """Types of documentation topics."""
    ONBOARDING = "onboarding"   # Getting started, quick starts
    CONCEPT = "concept"         # Explanatory content
    TASK = "task"               # How-tos, journeys (varying length)
    REFERENCE = "reference"     # API/SDK reference
    CHANGES = "changes"         # Roadmap, releases, deprecations


class ManifestType(str, Enum):
    """Whether a topic manifest is intended or actual."""
    INTENDED = "intended"  # ITM - the plan
    ACTUAL = "actual"      # ATM - the reality


class ConfidenceLevel(str, Enum):
    """Confidence levels for automated detection."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =============================================================================
# LAYER 1: SURFACE GRAPH
# =============================================================================

class SurfaceNode(BaseModel):
    """A node in the product surface graph.

    Represents a raw element from the codebase: an endpoint, entity, or concept.
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
        if isinstance(other, SurfaceNode):
            return self.id == other.id
        return False


class SurfaceEdge(BaseModel):
    """A relationship between two surface nodes."""
    source_id: str
    target_id: str
    edge_type: EdgeType
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM


class SurfaceGraph(BaseModel):
    """Layer 1: The product surface - raw scan of code.

    Immutable snapshot of all endpoints, entities, and concepts
    discovered in the codebase.
    """
    # Metadata
    product_name: str
    version: Optional[str] = None
    scanned_at: datetime = Field(default_factory=datetime.now)
    source_paths: list[str] = Field(default_factory=list)

    # Graph data
    nodes: list[SurfaceNode] = Field(default_factory=list)
    edges: list[SurfaceEdge] = Field(default_factory=list)

    # ==========================================================================
    # GRAPH ACCESSORS
    # ==========================================================================

    def get_node(self, node_id: str) -> Optional[SurfaceNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def nodes_by_type(self, node_type: NodeType) -> list[SurfaceNode]:
        """Get all nodes of a specific type."""
        return [n for n in self.nodes if n.type == node_type]

    @property
    def nouns(self) -> list[SurfaceNode]:
        return self.nodes_by_type(NodeType.NOUN)

    @property
    def verbs(self) -> list[SurfaceNode]:
        return self.nodes_by_type(NodeType.VERB)

    @property
    def concepts(self) -> list[SurfaceNode]:
        return self.nodes_by_type(NodeType.CONCEPT)

    def verbs_for_noun(self, noun_id: str) -> list[SurfaceNode]:
        """Get all verbs that operate on a noun."""
        verb_ids = [
            e.source_id for e in self.edges
            if e.target_id == noun_id and e.edge_type == EdgeType.OPERATES_ON
        ]
        return [n for n in self.nodes if n.id in verb_ids]

    def noun_for_verb(self, verb_id: str) -> Optional[SurfaceNode]:
        """Get the primary noun a verb operates on."""
        for edge in self.edges:
            if edge.source_id == verb_id and edge.edge_type == EdgeType.OPERATES_ON:
                return self.get_node(edge.target_id)
        return None

    def orphan_verbs(self) -> list[SurfaceNode]:
        """Get verbs not connected to any noun."""
        connected_verb_ids = {
            e.source_id for e in self.edges
            if e.edge_type == EdgeType.OPERATES_ON
        }
        return [v for v in self.verbs if v.id not in connected_verb_ids]

    def user_facing_nodes(self) -> list[SurfaceNode]:
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
# LAYER 2 & 3: TOPIC MANIFEST (ITM and ATM)
# =============================================================================

class Topic(BaseModel):
    """A documentation topic that covers surface elements.

    Topics are the logical groupings that organize documentation.
    A single topic might cover multiple surface nodes.
    """
    id: str
    name: str                        # "User Management", "Authentication"
    topic_type: TopicType

    # What surface elements does this topic cover?
    covers: list[str] = Field(default_factory=list)  # Surface node IDs

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

    # Overall score
    coverage_score: float = 0.0  # 0.0 - 1.0


class TopicManifest(BaseModel):
    """Layer 2/3: Topic organization - either intended (ITM) or actual (ATM).

    ITM: The plan - topics that SHOULD exist
    ATM: The reality - topics that DO exist in docs
    """
    # Identity
    manifest_type: ManifestType
    surface_id: str              # Links to which SurfaceGraph this covers

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

    def uncovered_surface_ids(self, surface: SurfaceGraph) -> list[str]:
        """Get surface node IDs not covered by any topic."""
        covered = self.covered_surface_ids()
        return [n.id for n in surface.user_facing_nodes() if n.id not in covered]

    def topics_covering(self, surface_id: str) -> list[Topic]:
        """Get all topics that cover a specific surface node."""
        return [t for t in self.topics if surface_id in t.covers]


# =============================================================================
# LAYER 4: GAP REPORT
# =============================================================================

class TopicGap(BaseModel):
    """A gap between an ITM topic and ATM coverage."""
    itm_topic_id: str
    itm_topic_name: str
    atm_topic_id: Optional[str] = None  # Matched ATM topic, if any

    # Coverage status
    status: Literal["missing", "partial", "complete", "extra"]

    # What's missing?
    missing_surface_ids: list[str] = Field(default_factory=list)

    # Quality gaps (if ATM topic exists)
    quality_gaps: list[str] = Field(default_factory=list)

    # Sprint plan action
    action: str = ""
    priority: int = 0


class GapReport(BaseModel):
    """Layer 4: Computed gap between ITM and ATM.

    This drives the sprint plan and coverage metrics.
    """
    # Links
    surface_id: str
    itm_id: str
    atm_id: str

    # Metadata
    generated_at: datetime = Field(default_factory=datetime.now)
    product_name: str

    # Gaps
    gaps: list[TopicGap] = Field(default_factory=list)

    # Extra topics in ATM not in ITM (potential undocumented features)
    extra_topics: list[str] = Field(default_factory=list)

    # ==========================================================================
    # STATISTICS
    # ==========================================================================

    def coverage_stats(self) -> dict:
        """Get overall coverage statistics."""
        total = len(self.gaps)
        if total == 0:
            return {"coverage_percentage": 0.0, "total": 0}

        complete = sum(1 for g in self.gaps if g.status == "complete")
        partial = sum(1 for g in self.gaps if g.status == "partial")
        missing = sum(1 for g in self.gaps if g.status == "missing")

        return {
            "total_topics": total,
            "complete": complete,
            "partial": partial,
            "missing": missing,
            "extra": len(self.extra_topics),
            "coverage_percentage": round((complete + partial * 0.5) / total * 100, 1),
        }

    def sprint_plan(self) -> list[dict]:
        """Generate prioritized sprint plan."""
        plan = []
        for gap in sorted(self.gaps, key=lambda g: g.priority, reverse=True):
            if gap.status in ("missing", "partial"):
                plan.append({
                    "topic": gap.itm_topic_name,
                    "status": gap.status,
                    "action": gap.action,
                    "missing_items": len(gap.missing_surface_ids),
                    "quality_gaps": gap.quality_gaps,
                    "priority": gap.priority,
                })
        return plan


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def generate_default_itm(surface: SurfaceGraph) -> TopicManifest:
    """Generate default ITM from a surface graph.

    Default strategy: One reference topic per noun (entity-centric).
    Orphan verbs are grouped by theme.
    """
    topics = []
    topic_id_counter = 0

    def next_id() -> str:
        nonlocal topic_id_counter
        topic_id_counter += 1
        return f"topic_{topic_id_counter}"

    # 1. Reference topic per noun
    for noun in surface.nouns:
        related_verbs = surface.verbs_for_noun(noun.id)

        topic = Topic(
            id=next_id(),
            name=noun.name.replace("_", " ").title(),
            topic_type=TopicType.REFERENCE,
            covers=[noun.id] + [v.id for v in related_verbs],
            auto_generated=True,
        )
        topics.append(topic)

    # 2. Group orphan verbs by theme
    orphans = surface.orphan_verbs()
    if orphans:
        # Simple clustering: group by path prefix
        themes: dict[str, list[SurfaceNode]] = {}
        for verb in orphans:
            # Extract theme from path (e.g., /auth/login -> "auth")
            if verb.http_path:
                parts = [p for p in verb.http_path.split('/') if p and not p.startswith('{')]
                theme = parts[0] if parts else "general"
            else:
                theme = "general"

            if theme not in themes:
                themes[theme] = []
            themes[theme].append(verb)

        for theme, verbs in themes.items():
            topic = Topic(
                id=next_id(),
                name=theme.replace("_", " ").title(),
                topic_type=TopicType.REFERENCE,
                covers=[v.id for v in verbs],
                auto_generated=True,
            )
            topics.append(topic)

    # 3. Concept topics for standalone concepts
    for concept in surface.concepts:
        topic = Topic(
            id=next_id(),
            name=concept.name.replace("_", " ").title(),
            topic_type=TopicType.CONCEPT,
            covers=[concept.id],
            auto_generated=True,
        )
        topics.append(topic)

    return TopicManifest(
        manifest_type=ManifestType.INTENDED,
        surface_id=f"{surface.product_name}:{surface.scanned_at.isoformat()}",
        product_name=surface.product_name,
        topics=topics,
    )


def compute_gap_report(
    surface: SurfaceGraph,
    itm: TopicManifest,
    atm: TopicManifest,
) -> GapReport:
    """Compute the gap between ITM and ATM.

    Matches ITM topics to ATM topics and identifies coverage gaps.
    """
    gaps = []
    matched_atm_ids = set()

    for itm_topic in itm.topics:
        # Find matching ATM topic (by name similarity or coverage overlap)
        best_match = None
        best_overlap = 0

        for atm_topic in atm.topics:
            # Check coverage overlap
            itm_covers = set(itm_topic.covers)
            atm_covers = set(atm_topic.covers)
            overlap = len(itm_covers & atm_covers)

            if overlap > best_overlap:
                best_overlap = overlap
                best_match = atm_topic

        # Determine gap status
        if best_match and best_overlap > 0:
            matched_atm_ids.add(best_match.id)
            itm_covers = set(itm_topic.covers)
            atm_covers = set(best_match.covers)
            missing = itm_covers - atm_covers

            if not missing:
                status = "complete"
                action = ""
            else:
                status = "partial"
                action = f"Add coverage for {len(missing)} missing elements"

            # Check quality
            quality_gaps = []
            if best_match.id in atm.quality:
                q = atm.quality[best_match.id]
                if q.has_errors == "no":
                    quality_gaps.append("missing error docs")
                if not q.has_examples:
                    quality_gaps.append("missing examples")
                if not q.has_use_cases:
                    quality_gaps.append("missing use cases")

            gap = TopicGap(
                itm_topic_id=itm_topic.id,
                itm_topic_name=itm_topic.name,
                atm_topic_id=best_match.id,
                status=status,
                missing_surface_ids=list(missing),
                quality_gaps=quality_gaps,
                action=action,
                priority=itm_topic.priority or 0,
            )
        else:
            gap = TopicGap(
                itm_topic_id=itm_topic.id,
                itm_topic_name=itm_topic.name,
                status="missing",
                missing_surface_ids=itm_topic.covers,
                action=f"Create new {itm_topic.topic_type.value} topic: {itm_topic.name}",
                priority=itm_topic.priority or 0,
            )

        gaps.append(gap)

    # Find extra ATM topics not in ITM
    extra = [t.id for t in atm.topics if t.id not in matched_atm_ids]

    return GapReport(
        surface_id=surface.product_name,
        itm_id=itm.surface_id,
        atm_id=atm.surface_id,
        product_name=surface.product_name,
        gaps=gaps,
        extra_topics=extra,
    )
