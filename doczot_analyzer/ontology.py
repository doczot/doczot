"""RDF/OWL ontology implementation for DocZot.

This module provides a standards-compliant ontology representation of DocZot's
Surface Graph, enabling:
- Serialization to RDF formats (Turtle, JSON-LD, RDF/XML, N-Triples)
- SPARQL queries for complex analysis
- OWL reasoning for inference and validation
- Integration with semantic web tools (Protégé, Jena, Neo4j)

Based on the design in docs/ONTOLOGY_DESIGN.md
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from urllib.parse import quote

try:
    from rdflib import Graph, Namespace, Literal, URIRef, BNode
    from rdflib.namespace import RDF, RDFS, OWL, XSD, SKOS
    HAS_RDFLIB = True
except ImportError:
    HAS_RDFLIB = False

if TYPE_CHECKING:
    from doczot_analyzer.models_v2 import SurfaceGraph, TopicManifest


# =============================================================================
# NAMESPACES
# =============================================================================

if HAS_RDFLIB:
    DOCZOT = Namespace("https://doczot.io/ontology/")
    DATA = Namespace("https://doczot.io/data/")
    PROV = Namespace("http://www.w3.org/ns/prov#")
    HYDRA = Namespace("http://www.w3.org/ns/hydra/core#")


# =============================================================================
# ONTOLOGY SCHEMA (T-BOX)
# =============================================================================

ONTOLOGY_SCHEMA = """
@prefix doczot: <https://doczot.io/ontology/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

# =============================================================================
# ONTOLOGY METADATA
# =============================================================================

<https://doczot.io/ontology/> a owl:Ontology ;
    rdfs:label "DocZot Ontology" ;
    rdfs:comment "Formal ontology for API surface documentation coverage analysis." ;
    owl:versionInfo "1.0.0" .

# =============================================================================
# CLASSES
# =============================================================================

doczot:SurfaceElement a owl:Class ;
    rdfs:label "Surface Element" ;
    rdfs:comment "Any element of the API surface that may require documentation." .

doczot:Verb a owl:Class ;
    rdfs:subClassOf doczot:SurfaceElement ;
    rdfs:label "Verb" ;
    rdfs:comment "An API operation/endpoint that performs an action." .

doczot:Noun a owl:Class ;
    rdfs:subClassOf doczot:SurfaceElement ;
    rdfs:label "Noun" ;
    rdfs:comment "A domain entity that verbs operate upon." .

doczot:Concept a owl:Class ;
    rdfs:subClassOf doczot:SurfaceElement ;
    rdfs:subClassOf skos:Concept ;
    rdfs:label "Concept" ;
    rdfs:comment "An abstract idea or principle relevant to the API." .

doczot:Constraint a owl:Class ;
    rdfs:subClassOf doczot:SurfaceElement ;
    rdfs:label "Constraint" ;
    rdfs:comment "A restriction or requirement on API usage." .

doczot:AuthConstraint a owl:Class ;
    rdfs:subClassOf doczot:Constraint ;
    rdfs:label "Authentication Constraint" ;
    rdfs:comment "Requires authentication to access." .

doczot:RateLimitConstraint a owl:Class ;
    rdfs:subClassOf doczot:Constraint ;
    rdfs:label "Rate Limit Constraint" ;
    rdfs:comment "Limits the frequency of API calls." .

doczot:Topic a owl:Class ;
    rdfs:label "Documentation Topic" ;
    rdfs:comment "A unit of documentation that covers one or more surface elements." .

doczot:TopicManifest a owl:Class ;
    rdfs:label "Topic Manifest" ;
    rdfs:comment "A collection of topics representing intended or actual documentation." .

doczot:IntendedTopicManifest a owl:Class ;
    rdfs:subClassOf doczot:TopicManifest ;
    rdfs:label "Intended Topic Manifest (ITM)" ;
    rdfs:comment "Topics that SHOULD exist based on the surface graph." .

doczot:ActualTopicManifest a owl:Class ;
    rdfs:subClassOf doczot:TopicManifest ;
    rdfs:label "Actual Topic Manifest (ATM)" ;
    rdfs:comment "Topics that DO exist in current documentation." .

doczot:SurfaceGraph a owl:Class ;
    rdfs:label "Surface Graph" ;
    rdfs:comment "An immutable snapshot of the API surface at a point in time." .

# =============================================================================
# HTTP METHOD ENUMERATION
# =============================================================================

doczot:HttpMethod a owl:Class ;
    rdfs:label "HTTP Method" .

doczot:GET a doczot:HttpMethod ; rdfs:label "GET" .
doczot:POST a doczot:HttpMethod ; rdfs:label "POST" .
doczot:PUT a doczot:HttpMethod ; rdfs:label "PUT" .
doczot:DELETE a doczot:HttpMethod ; rdfs:label "DELETE" .
doczot:PATCH a doczot:HttpMethod ; rdfs:label "PATCH" .
doczot:HEAD a doczot:HttpMethod ; rdfs:label "HEAD" .
doczot:OPTIONS a doczot:HttpMethod ; rdfs:label "OPTIONS" .

# =============================================================================
# TOPIC TYPE ENUMERATION
# =============================================================================

doczot:TopicType a owl:Class ;
    rdfs:label "Topic Type" .

doczot:OnboardingTopic a doczot:TopicType ; rdfs:label "Onboarding" .
doczot:ConceptTopic a doczot:TopicType ; rdfs:label "Concept" .
doczot:TaskTopic a doczot:TopicType ; rdfs:label "Task" .
doczot:ReferenceTopic a doczot:TopicType ; rdfs:label "Reference" .
doczot:ChangesTopic a doczot:TopicType ; rdfs:label "Changes" .

# =============================================================================
# OBJECT PROPERTIES
# =============================================================================

doczot:operatesOn a owl:ObjectProperty ;
    rdfs:label "operates on" ;
    rdfs:comment "Links a verb to the noun(s) it acts upon." ;
    rdfs:domain doczot:Verb ;
    rdfs:range doczot:Noun .

doczot:partOf a owl:ObjectProperty, owl:TransitiveProperty ;
    rdfs:label "part of" ;
    rdfs:comment "Indicates compositional hierarchy between nouns." ;
    rdfs:domain doczot:Noun ;
    rdfs:range doczot:Noun ;
    owl:inverseOf doczot:hasPart .

doczot:hasPart a owl:ObjectProperty, owl:TransitiveProperty ;
    rdfs:label "has part" ;
    rdfs:domain doczot:Noun ;
    rdfs:range doczot:Noun ;
    owl:inverseOf doczot:partOf .

doczot:prerequisiteOf a owl:ObjectProperty, owl:TransitiveProperty ;
    rdfs:label "prerequisite of" ;
    rdfs:comment "Must be completed before the target operation." ;
    rdfs:domain doczot:SurfaceElement ;
    rdfs:range doczot:SurfaceElement .

doczot:constrainedBy a owl:ObjectProperty ;
    rdfs:label "constrained by" ;
    rdfs:comment "Links an element to its constraints." ;
    rdfs:domain doczot:SurfaceElement ;
    rdfs:range doczot:Constraint .

doczot:relatedTo a owl:ObjectProperty, owl:SymmetricProperty ;
    rdfs:label "related to" ;
    rdfs:comment "General semantic relationship between elements." ;
    rdfs:domain doczot:SurfaceElement ;
    rdfs:range doczot:SurfaceElement .

doczot:covers a owl:ObjectProperty ;
    rdfs:label "covers" ;
    rdfs:comment "Links a topic to the surface elements it documents." ;
    rdfs:domain doczot:Topic ;
    rdfs:range doczot:SurfaceElement ;
    owl:inverseOf doczot:coveredBy .

doczot:coveredBy a owl:ObjectProperty ;
    rdfs:label "covered by" ;
    rdfs:domain doczot:SurfaceElement ;
    rdfs:range doczot:Topic ;
    owl:inverseOf doczot:covers .

doczot:hasTopic a owl:ObjectProperty ;
    rdfs:label "has topic" ;
    rdfs:domain doczot:TopicManifest ;
    rdfs:range doczot:Topic .

doczot:parentTopic a owl:ObjectProperty, owl:TransitiveProperty ;
    rdfs:label "parent topic" ;
    rdfs:domain doczot:Topic ;
    rdfs:range doczot:Topic ;
    owl:inverseOf doczot:childTopic .

doczot:childTopic a owl:ObjectProperty ;
    rdfs:label "child topic" ;
    owl:inverseOf doczot:parentTopic .

doczot:hasElement a owl:ObjectProperty ;
    rdfs:label "has element" ;
    rdfs:domain doczot:SurfaceGraph ;
    rdfs:range doczot:SurfaceElement .

# =============================================================================
# DATATYPE PROPERTIES
# =============================================================================

doczot:name a owl:DatatypeProperty ;
    rdfs:label "name" ;
    rdfs:range xsd:string .

doczot:description a owl:DatatypeProperty ;
    rdfs:label "description" ;
    rdfs:range xsd:string .

doczot:sourceFile a owl:DatatypeProperty ;
    rdfs:label "source file" ;
    rdfs:range xsd:string .

doczot:sourceLine a owl:DatatypeProperty ;
    rdfs:label "source line" ;
    rdfs:range xsd:integer .

doczot:isUserFacing a owl:DatatypeProperty ;
    rdfs:label "is user facing" ;
    rdfs:range xsd:boolean .

doczot:isDeprecated a owl:DatatypeProperty ;
    rdfs:label "is deprecated" ;
    rdfs:range xsd:boolean .

doczot:httpMethod a owl:ObjectProperty, owl:FunctionalProperty ;
    rdfs:label "HTTP method" ;
    rdfs:domain doczot:Verb ;
    rdfs:range doczot:HttpMethod .

doczot:httpPath a owl:DatatypeProperty, owl:FunctionalProperty ;
    rdfs:label "HTTP path" ;
    rdfs:domain doczot:Verb ;
    rdfs:range xsd:string .

doczot:codeSignature a owl:DatatypeProperty ;
    rdfs:label "code signature" ;
    rdfs:range xsd:string .

doczot:rateLimit a owl:DatatypeProperty ;
    rdfs:label "rate limit" ;
    rdfs:domain doczot:RateLimitConstraint ;
    rdfs:range xsd:string .

doczot:authType a owl:DatatypeProperty ;
    rdfs:label "authentication type" ;
    rdfs:domain doczot:AuthConstraint ;
    rdfs:range xsd:string .

doczot:topicType a owl:ObjectProperty, owl:FunctionalProperty ;
    rdfs:label "topic type" ;
    rdfs:domain doczot:Topic ;
    rdfs:range doczot:TopicType .

doczot:sourceDocument a owl:DatatypeProperty ;
    rdfs:label "source document" ;
    rdfs:domain doczot:Topic ;
    rdfs:range xsd:anyURI .

doczot:coverageScore a owl:DatatypeProperty ;
    rdfs:label "coverage score" ;
    rdfs:range xsd:decimal .

doczot:agentReadinessScore a owl:DatatypeProperty ;
    rdfs:label "agent readiness score" ;
    rdfs:range xsd:decimal .

doczot:hasExamples a owl:DatatypeProperty ;
    rdfs:label "has examples" ;
    rdfs:range xsd:boolean .

doczot:hasErrorDocs a owl:DatatypeProperty ;
    rdfs:label "has error documentation" ;
    rdfs:range xsd:boolean .

doczot:scannedAt a owl:DatatypeProperty ;
    rdfs:label "scanned at" ;
    rdfs:domain doczot:SurfaceGraph ;
    rdfs:range xsd:dateTime .

doczot:productName a owl:DatatypeProperty ;
    rdfs:domain doczot:SurfaceGraph ;
    rdfs:range xsd:string .

doczot:productVersion a owl:DatatypeProperty ;
    rdfs:domain doczot:SurfaceGraph ;
    rdfs:range xsd:string .

# =============================================================================
# DISJOINTNESS AXIOMS
# =============================================================================

[] a owl:AllDisjointClasses ;
    owl:members (doczot:Verb doczot:Noun doczot:Concept doczot:Constraint) .

[] a owl:AllDisjointClasses ;
    owl:members (doczot:AuthConstraint doczot:RateLimitConstraint) .

[] a owl:AllDisjointClasses ;
    owl:members (doczot:IntendedTopicManifest doczot:ActualTopicManifest) .
"""


# =============================================================================
# ONTOLOGY CLASS
# =============================================================================

class DoczotOntology:
    """RDF/OWL ontology for DocZot surface graphs.

    Provides methods to:
    - Add surface elements (nouns, verbs, concepts, constraints)
    - Add relationships between elements
    - Add documentation topics and coverage
    - Serialize to standard RDF formats
    - Execute SPARQL queries

    Example:
        >>> onto = DoczotOntology("My API")
        >>> user_uri = onto.add_noun("user", description="A system user")
        >>> verb_uri = onto.add_verb("get_user", "GET", "/users/{id}", operates_on=["user"])
        >>> print(onto.serialize("turtle"))
    """

    def __init__(self, product_name: str, load_schema: bool = True):
        """Initialize the ontology.

        Args:
            product_name: Name of the product/API being documented
            load_schema: Whether to load the ontology schema (T-Box)
        """
        if not HAS_RDFLIB:
            raise ImportError(
                "rdflib is required for ontology support. "
                "Install with: pip install rdflib"
            )

        self.product_name = product_name
        self.product_slug = quote(product_name.lower().replace(" ", "-"), safe="")
        self.graph = Graph()
        self._bind_namespaces()

        if load_schema:
            self._load_schema()

        # Track created URIs for reference
        self._node_uris: dict[str, URIRef] = {}

    def _bind_namespaces(self) -> None:
        """Bind standard prefixes for readable output."""
        self.graph.bind("doczot", DOCZOT)
        self.graph.bind("data", DATA)
        self.graph.bind("prov", PROV)
        self.graph.bind("skos", SKOS)
        self.graph.bind("owl", OWL)
        self.graph.bind("rdfs", RDFS)
        self.graph.bind("xsd", XSD)

    def _load_schema(self) -> None:
        """Load the ontology schema (T-Box)."""
        self.graph.parse(data=ONTOLOGY_SCHEMA, format="turtle")

    def _data_uri(self, type_: str, id_: str) -> URIRef:
        """Generate a data URI for an instance.

        Args:
            type_: Type of element (noun, verb, concept, constraint, topic)
            id_: Unique identifier for the element

        Returns:
            URIRef for the element
        """
        safe_id = quote(id_.replace("/", "-").replace(":", "-").replace(" ", "-"), safe="")
        return URIRef(f"{DATA}{self.product_slug}/{type_}/{safe_id}")

    def _get_or_create_uri(self, node_id: str, type_: str, id_hint: str) -> URIRef:
        """Get existing URI or create new one for a node."""
        if node_id in self._node_uris:
            return self._node_uris[node_id]
        uri = self._data_uri(type_, id_hint)
        self._node_uris[node_id] = uri
        return uri

    # =========================================================================
    # ADD SURFACE ELEMENTS
    # =========================================================================

    def add_noun(
        self,
        name: str,
        *,
        node_id: Optional[str] = None,
        description: Optional[str] = None,
        source_file: Optional[str] = None,
        source_line: Optional[int] = None,
        is_user_facing: bool = True,
        part_of: Optional[str] = None,
    ) -> URIRef:
        """Add a noun (entity) to the ontology.

        Args:
            name: Human-readable name
            node_id: Original node ID from SurfaceGraph (for tracking)
            description: Description of the entity
            source_file: Source file where defined
            source_line: Line number in source file
            is_user_facing: Whether this is user-facing
            part_of: Name of parent noun (for compositional hierarchy)

        Returns:
            URI of the created noun
        """
        uri = self._data_uri("noun", name)
        if node_id:
            self._node_uris[node_id] = uri

        self.graph.add((uri, RDF.type, DOCZOT.Noun))
        self.graph.add((uri, DOCZOT.name, Literal(name)))
        self.graph.add((uri, DOCZOT.isUserFacing, Literal(is_user_facing)))
        self.graph.add((uri, RDFS.label, Literal(name)))

        if description:
            self.graph.add((uri, DOCZOT.description, Literal(description)))
            self.graph.add((uri, RDFS.comment, Literal(description)))
        if source_file:
            self.graph.add((uri, DOCZOT.sourceFile, Literal(source_file)))
        if source_line is not None:
            self.graph.add((uri, DOCZOT.sourceLine, Literal(source_line, datatype=XSD.integer)))
        if part_of:
            parent_uri = self._data_uri("noun", part_of)
            self.graph.add((uri, DOCZOT.partOf, parent_uri))

        return uri

    def add_verb(
        self,
        name: str,
        http_method: str,
        http_path: str,
        *,
        node_id: Optional[str] = None,
        description: Optional[str] = None,
        source_file: Optional[str] = None,
        source_line: Optional[int] = None,
        is_user_facing: bool = True,
        operates_on: Optional[list[str]] = None,
    ) -> URIRef:
        """Add a verb (endpoint) to the ontology.

        Args:
            name: Human-readable name (e.g., "get_users")
            http_method: HTTP method (GET, POST, PUT, DELETE, etc.)
            http_path: HTTP path (e.g., "/users/{id}")
            node_id: Original node ID from SurfaceGraph
            description: Description/docstring
            source_file: Source file where defined
            source_line: Line number in source file
            is_user_facing: Whether this is user-facing
            operates_on: List of noun names this verb operates on

        Returns:
            URI of the created verb
        """
        verb_id = f"{http_method}-{http_path}"
        uri = self._data_uri("verb", verb_id)
        if node_id:
            self._node_uris[node_id] = uri

        method_uri = URIRef(f"{DOCZOT}{http_method.upper()}")

        self.graph.add((uri, RDF.type, DOCZOT.Verb))
        self.graph.add((uri, DOCZOT.name, Literal(name)))
        self.graph.add((uri, DOCZOT.httpMethod, method_uri))
        self.graph.add((uri, DOCZOT.httpPath, Literal(http_path)))
        self.graph.add((uri, DOCZOT.codeSignature, Literal(f"{http_method} {http_path}")))
        self.graph.add((uri, DOCZOT.isUserFacing, Literal(is_user_facing)))
        self.graph.add((uri, RDFS.label, Literal(f"{http_method} {http_path}")))

        if description:
            self.graph.add((uri, DOCZOT.description, Literal(description)))
            self.graph.add((uri, RDFS.comment, Literal(description)))
        if source_file:
            self.graph.add((uri, DOCZOT.sourceFile, Literal(source_file)))
        if source_line is not None:
            self.graph.add((uri, DOCZOT.sourceLine, Literal(source_line, datatype=XSD.integer)))

        if operates_on:
            for noun_name in operates_on:
                noun_uri = self._data_uri("noun", noun_name)
                self.graph.add((uri, DOCZOT.operatesOn, noun_uri))

        return uri

    def add_concept(
        self,
        name: str,
        *,
        node_id: Optional[str] = None,
        description: Optional[str] = None,
        source_file: Optional[str] = None,
        source_line: Optional[int] = None,
    ) -> URIRef:
        """Add a concept to the ontology.

        Args:
            name: Human-readable name
            node_id: Original node ID from SurfaceGraph
            description: Definition of the concept
            source_file: Source file where defined
            source_line: Line number

        Returns:
            URI of the created concept
        """
        uri = self._data_uri("concept", name)
        if node_id:
            self._node_uris[node_id] = uri

        self.graph.add((uri, RDF.type, DOCZOT.Concept))
        self.graph.add((uri, RDF.type, SKOS.Concept))
        self.graph.add((uri, DOCZOT.name, Literal(name)))
        self.graph.add((uri, SKOS.prefLabel, Literal(name)))
        self.graph.add((uri, RDFS.label, Literal(name)))

        if description:
            self.graph.add((uri, DOCZOT.description, Literal(description)))
            self.graph.add((uri, SKOS.definition, Literal(description)))
            self.graph.add((uri, RDFS.comment, Literal(description)))
        if source_file:
            self.graph.add((uri, DOCZOT.sourceFile, Literal(source_file)))
        if source_line is not None:
            self.graph.add((uri, DOCZOT.sourceLine, Literal(source_line, datatype=XSD.integer)))

        return uri

    def add_constraint(
        self,
        constraint_type: str,
        name: str,
        *,
        node_id: Optional[str] = None,
        description: Optional[str] = None,
        value: Optional[str] = None,
        source_file: Optional[str] = None,
        source_line: Optional[int] = None,
    ) -> URIRef:
        """Add a constraint to the ontology.

        Args:
            constraint_type: "auth" or "rate_limit"
            name: Constraint name
            node_id: Original node ID from SurfaceGraph
            description: Description of the constraint
            value: Constraint value (e.g., "100/hour" for rate limit)
            source_file: Source file
            source_line: Line number

        Returns:
            URI of the created constraint
        """
        constraint_id = f"{constraint_type}-{name}-{source_line or 0}"
        uri = self._data_uri("constraint", constraint_id)
        if node_id:
            self._node_uris[node_id] = uri

        if constraint_type == "auth":
            self.graph.add((uri, RDF.type, DOCZOT.AuthConstraint))
            if value:
                self.graph.add((uri, DOCZOT.authType, Literal(value)))
        elif constraint_type == "rate_limit":
            self.graph.add((uri, RDF.type, DOCZOT.RateLimitConstraint))
            if value:
                self.graph.add((uri, DOCZOT.rateLimit, Literal(value)))
        else:
            self.graph.add((uri, RDF.type, DOCZOT.Constraint))

        self.graph.add((uri, DOCZOT.name, Literal(name)))
        self.graph.add((uri, RDFS.label, Literal(f"{constraint_type}: {name}")))

        if description:
            self.graph.add((uri, DOCZOT.description, Literal(description)))
            self.graph.add((uri, RDFS.comment, Literal(description)))
        if source_file:
            self.graph.add((uri, DOCZOT.sourceFile, Literal(source_file)))
        if source_line is not None:
            self.graph.add((uri, DOCZOT.sourceLine, Literal(source_line, datatype=XSD.integer)))

        return uri

    # =========================================================================
    # ADD RELATIONSHIPS
    # =========================================================================

    def add_operates_on(self, verb_uri: URIRef, noun_uri: URIRef) -> None:
        """Add an operates_on relationship."""
        self.graph.add((verb_uri, DOCZOT.operatesOn, noun_uri))

    def add_part_of(self, child_uri: URIRef, parent_uri: URIRef) -> None:
        """Add a part_of relationship (child is part of parent)."""
        self.graph.add((child_uri, DOCZOT.partOf, parent_uri))

    def add_prerequisite(self, prereq_uri: URIRef, target_uri: URIRef) -> None:
        """Add a prerequisite relationship (prereq must come before target)."""
        self.graph.add((prereq_uri, DOCZOT.prerequisiteOf, target_uri))

    def add_constrained_by(self, element_uri: URIRef, constraint_uri: URIRef) -> None:
        """Add a constrained_by relationship."""
        self.graph.add((element_uri, DOCZOT.constrainedBy, constraint_uri))

    def add_related_to(self, source_uri: URIRef, target_uri: URIRef) -> None:
        """Add a related_to relationship (symmetric)."""
        self.graph.add((source_uri, DOCZOT.relatedTo, target_uri))

    # =========================================================================
    # ADD DOCUMENTATION
    # =========================================================================

    def add_topic(
        self,
        name: str,
        topic_type: str,
        *,
        topic_id: Optional[str] = None,
        source_document: Optional[str] = None,
        coverage_score: Optional[float] = None,
        agent_readiness_score: Optional[float] = None,
        has_examples: bool = False,
        has_error_docs: bool = False,
        covers: Optional[list[str]] = None,
        parent_topic: Optional[str] = None,
    ) -> URIRef:
        """Add a documentation topic.

        Args:
            name: Topic name
            topic_type: One of: onboarding, concept, task, reference, changes
            topic_id: Original topic ID
            source_document: Path to source document
            coverage_score: 0.0-1.0 coverage score
            agent_readiness_score: 0.0-1.0 agent readiness score
            has_examples: Whether topic has examples
            has_error_docs: Whether topic has error documentation
            covers: List of node IDs this topic covers
            parent_topic: Name of parent topic

        Returns:
            URI of the created topic
        """
        uri = self._data_uri("topic", name)
        if topic_id:
            self._node_uris[topic_id] = uri

        # Map topic type to URI
        type_map = {
            "onboarding": DOCZOT.OnboardingTopic,
            "concept": DOCZOT.ConceptTopic,
            "task": DOCZOT.TaskTopic,
            "reference": DOCZOT.ReferenceTopic,
            "changes": DOCZOT.ChangesTopic,
        }
        type_uri = type_map.get(topic_type.lower(), DOCZOT.ReferenceTopic)

        self.graph.add((uri, RDF.type, DOCZOT.Topic))
        self.graph.add((uri, DOCZOT.name, Literal(name)))
        self.graph.add((uri, DOCZOT.topicType, type_uri))
        self.graph.add((uri, RDFS.label, Literal(name)))

        if source_document:
            self.graph.add((uri, DOCZOT.sourceDocument, Literal(source_document, datatype=XSD.anyURI)))
        if coverage_score is not None:
            self.graph.add((uri, DOCZOT.coverageScore, Literal(coverage_score, datatype=XSD.decimal)))
        if agent_readiness_score is not None:
            self.graph.add((uri, DOCZOT.agentReadinessScore, Literal(agent_readiness_score, datatype=XSD.decimal)))

        self.graph.add((uri, DOCZOT.hasExamples, Literal(has_examples)))
        self.graph.add((uri, DOCZOT.hasErrorDocs, Literal(has_error_docs)))

        if covers:
            for node_id in covers:
                if node_id in self._node_uris:
                    self.graph.add((uri, DOCZOT.covers, self._node_uris[node_id]))

        if parent_topic:
            parent_uri = self._data_uri("topic", parent_topic)
            self.graph.add((uri, DOCZOT.parentTopic, parent_uri))

        return uri

    def add_topic_manifest(
        self,
        manifest_type: str,
        topics: list[URIRef],
    ) -> URIRef:
        """Add a topic manifest (ITM or ATM).

        Args:
            manifest_type: "intended" or "actual"
            topics: List of topic URIs to include

        Returns:
            URI of the manifest
        """
        manifest_id = f"{manifest_type}-{datetime.now().isoformat()}"
        uri = self._data_uri("manifest", manifest_id)

        if manifest_type == "intended":
            self.graph.add((uri, RDF.type, DOCZOT.IntendedTopicManifest))
        else:
            self.graph.add((uri, RDF.type, DOCZOT.ActualTopicManifest))

        self.graph.add((uri, DOCZOT.productName, Literal(self.product_name)))
        self.graph.add((uri, RDFS.label, Literal(f"{manifest_type.title()} Topic Manifest")))

        for topic_uri in topics:
            self.graph.add((uri, DOCZOT.hasTopic, topic_uri))

        return uri

    # =========================================================================
    # ADD SURFACE GRAPH METADATA
    # =========================================================================

    def add_surface_graph_metadata(
        self,
        scanned_at: datetime,
        source_paths: list[str],
        version: Optional[str] = None,
    ) -> URIRef:
        """Add surface graph metadata.

        Args:
            scanned_at: When the scan was performed
            source_paths: Paths that were scanned
            version: Product version

        Returns:
            URI of the surface graph
        """
        graph_id = f"surface-{scanned_at.strftime('%Y%m%d-%H%M%S')}"
        uri = self._data_uri("graph", graph_id)

        self.graph.add((uri, RDF.type, DOCZOT.SurfaceGraph))
        self.graph.add((uri, DOCZOT.productName, Literal(self.product_name)))
        self.graph.add((uri, DOCZOT.scannedAt, Literal(scanned_at.isoformat(), datatype=XSD.dateTime)))
        self.graph.add((uri, RDFS.label, Literal(f"{self.product_name} Surface Graph")))

        if version:
            self.graph.add((uri, DOCZOT.productVersion, Literal(version)))

        for path in source_paths:
            self.graph.add((uri, DOCZOT.sourceFile, Literal(path)))

        # Link all elements to this graph
        for node_uri in self._node_uris.values():
            self.graph.add((uri, DOCZOT.hasElement, node_uri))

        return uri

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def serialize(self, format: str = "turtle") -> str:
        """Serialize the ontology to a string.

        Args:
            format: Output format - turtle, json-ld, xml, n3, ntriples

        Returns:
            Serialized ontology as string
        """
        return self.graph.serialize(format=format)

    def save(self, path: Path, format: str = "turtle") -> None:
        """Save the ontology to a file.

        Args:
            path: Output file path
            format: Output format
        """
        content = self.serialize(format)
        path.write_text(content)

    def load(self, path: Path, format: str = "turtle") -> None:
        """Load additional triples from a file.

        Args:
            path: Input file path
            format: Input format
        """
        self.graph.parse(path, format=format)

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_statistics(self) -> dict:
        """Get statistics about the ontology contents.

        Returns:
            Dictionary with counts of different element types
        """
        stats = {
            "total_triples": len(self.graph),
            "verbs": 0,
            "nouns": 0,
            "concepts": 0,
            "constraints": 0,
            "topics": 0,
            "relationships": {
                "operates_on": 0,
                "part_of": 0,
                "constrained_by": 0,
                "prerequisite_of": 0,
                "covers": 0,
            },
        }

        for s, p, o in self.graph:
            if p == RDF.type:
                if o == DOCZOT.Verb:
                    stats["verbs"] += 1
                elif o == DOCZOT.Noun:
                    stats["nouns"] += 1
                elif o == DOCZOT.Concept:
                    stats["concepts"] += 1
                elif o in (DOCZOT.Constraint, DOCZOT.AuthConstraint, DOCZOT.RateLimitConstraint):
                    stats["constraints"] += 1
                elif o == DOCZOT.Topic:
                    stats["topics"] += 1
            elif p == DOCZOT.operatesOn:
                stats["relationships"]["operates_on"] += 1
            elif p == DOCZOT.partOf:
                stats["relationships"]["part_of"] += 1
            elif p == DOCZOT.constrainedBy:
                stats["relationships"]["constrained_by"] += 1
            elif p == DOCZOT.prerequisiteOf:
                stats["relationships"]["prerequisite_of"] += 1
            elif p == DOCZOT.covers:
                stats["relationships"]["covers"] += 1

        return stats


# =============================================================================
# CONVERSION FROM CURRENT MODELS
# =============================================================================

def surface_graph_to_ontology(
    surface: "SurfaceGraph",
    include_schema: bool = True,
) -> DoczotOntology:
    """Convert a SurfaceGraph (current Pydantic model) to RDF/OWL ontology.

    Args:
        surface: SurfaceGraph from models_v2
        include_schema: Whether to include the ontology schema (T-Box)

    Returns:
        DoczotOntology instance with all surface elements
    """
    from doczot_analyzer.models_v2 import NodeType, EdgeType

    onto = DoczotOntology(surface.product_name, load_schema=include_schema)

    # Add nodes
    for node in surface.nodes:
        if node.type == NodeType.NOUN:
            onto.add_noun(
                name=node.name,
                node_id=node.id,
                description=node.description,
                source_file=node.source_file,
                source_line=node.source_line,
                is_user_facing=node.node_class.value == "user-facing",
            )
        elif node.type == NodeType.VERB:
            onto.add_verb(
                name=node.name,
                http_method=node.http_method or "GET",
                http_path=node.http_path or "/",
                node_id=node.id,
                description=node.description,
                source_file=node.source_file,
                source_line=node.source_line,
                is_user_facing=node.node_class.value == "user-facing",
            )
        elif node.type == NodeType.CONCEPT:
            onto.add_concept(
                name=node.name,
                node_id=node.id,
                description=node.description,
                source_file=node.source_file,
                source_line=node.source_line,
            )
        elif node.type == NodeType.CONSTRAINT:
            # Determine constraint type from name
            c_type = "auth" if "auth" in node.name.lower() else "rate_limit"

            # Extract value from description
            value = None
            if node.description:
                if "rate" in node.description.lower():
                    # Extract rate limit value like "100/hour"
                    import re
                    match = re.search(r'(\d+/\w+)', node.description)
                    if match:
                        value = match.group(1)
                elif "auth" in node.description.lower():
                    value = "jwt"  # Default auth type

            onto.add_constraint(
                constraint_type=c_type,
                name=node.name,
                node_id=node.id,
                description=node.description,
                value=value,
                source_file=node.source_file,
                source_line=node.source_line,
            )

    # Add edges
    for edge in surface.edges:
        source_uri = onto._node_uris.get(edge.source_id)
        target_uri = onto._node_uris.get(edge.target_id)

        if not source_uri or not target_uri:
            continue

        if edge.edge_type == EdgeType.OPERATES_ON:
            onto.add_operates_on(source_uri, target_uri)
        elif edge.edge_type == EdgeType.PART_OF:
            onto.add_part_of(source_uri, target_uri)
        elif edge.edge_type == EdgeType.PREREQUISITE:
            onto.add_prerequisite(source_uri, target_uri)
        elif edge.edge_type == EdgeType.CONSTRAINED_BY:
            onto.add_constrained_by(source_uri, target_uri)
        elif edge.edge_type == EdgeType.RELATED_TO:
            onto.add_related_to(source_uri, target_uri)

    # Add surface graph metadata
    onto.add_surface_graph_metadata(
        scanned_at=surface.scanned_at,
        source_paths=surface.source_paths,
        version=surface.version,
    )

    return onto


def topic_manifest_to_ontology(
    manifest: "TopicManifest",
    onto: DoczotOntology,
) -> URIRef:
    """Add a TopicManifest to an existing ontology.

    Args:
        manifest: TopicManifest from models_v2
        onto: Existing DoczotOntology to add to

    Returns:
        URI of the created manifest
    """
    from doczot_analyzer.models_v2 import ManifestType

    topic_uris = []

    for topic in manifest.topics:
        # Get quality scores if available
        quality = manifest.quality.get(topic.id)
        coverage_score = quality.coverage_score if quality else None
        agent_readiness = quality.agent_readiness_score if quality else None
        has_examples = quality.has_examples if quality else False
        has_errors = quality.has_errors != "no" if quality else False

        uri = onto.add_topic(
            name=topic.name,
            topic_type=topic.topic_type.value,
            topic_id=topic.id,
            source_document=topic.source_file,
            coverage_score=coverage_score,
            agent_readiness_score=agent_readiness,
            has_examples=has_examples,
            has_error_docs=has_errors,
            covers=topic.covers,
            parent_topic=topic.parent_id,
        )
        topic_uris.append(uri)

    manifest_type = "intended" if manifest.manifest_type == ManifestType.INTENDED else "actual"
    return onto.add_topic_manifest(manifest_type, topic_uris)


def full_analysis_to_ontology(
    surface: "SurfaceGraph",
    itm: "TopicManifest",
    atm: "TopicManifest",
) -> DoczotOntology:
    """Convert a full DocZot analysis to RDF/OWL ontology.

    Args:
        surface: Surface graph from analysis
        itm: Intended Topic Manifest
        atm: Actual Topic Manifest

    Returns:
        Complete ontology with surface, ITM, and ATM
    """
    onto = surface_graph_to_ontology(surface)
    topic_manifest_to_ontology(itm, onto)
    topic_manifest_to_ontology(atm, onto)
    return onto
