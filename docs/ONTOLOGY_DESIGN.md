# DocZot Ontology Design: Standards-Compliant Implementation

## Executive Summary

This document specifies a formal ontology for DocZot's Surface Graph, replacing the current proprietary Pydantic/JSON model with a standards-compliant RDF/OWL implementation that enables automated reasoning, interoperability, and integration with the semantic web ecosystem.

---

## 1. Ontology Overview

### 1.1 Namespace and IRI Strategy

```
Base IRI:        https://doczot.io/ontology/
Prefix:          doczot:
Version IRI:     https://doczot.io/ontology/v1/

Instance IRIs:   https://doczot.io/data/{product}/{type}/{id}
Example:         https://doczot.io/data/my-api/verb/GET-users
```

### 1.2 Imported Ontologies

| Prefix | Ontology | Purpose |
|--------|----------|---------|
| `schema:` | Schema.org | SoftwareApplication, API, documentation |
| `hydra:` | Hydra | API operations, HTTP methods |
| `oa:` | Web Annotation | Documentation coverage annotations |
| `prov:` | PROV-O | Provenance of scans and analysis |
| `skos:` | SKOS | Concept hierarchies and definitions |

---

## 2. Class Hierarchy (T-Box)

### 2.1 Core Classes

```turtle
@prefix doczot: <https://doczot.io/ontology/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# =============================================================================
# TOP-LEVEL CLASSES
# =============================================================================

doczot:SurfaceElement a owl:Class ;
    rdfs:label "Surface Element" ;
    rdfs:comment "Any element of the API surface that may require documentation." ;
    owl:disjointUnionOf (doczot:Verb doczot:Noun doczot:Concept doczot:Constraint) .

doczot:Verb a owl:Class ;
    rdfs:subClassOf doczot:SurfaceElement ;
    rdfs:label "Verb" ;
    rdfs:comment "An API operation/endpoint that performs an action." ;
    owl:equivalentClass [
        a owl:Restriction ;
        owl:onProperty doczot:httpMethod ;
        owl:someValuesFrom doczot:HttpMethod
    ] .

doczot:Noun a owl:Class ;
    rdfs:subClassOf doczot:SurfaceElement ;
    rdfs:label "Noun" ;
    rdfs:comment "A domain entity that verbs operate upon." .

doczot:Concept a owl:Class ;
    rdfs:subClassOf doczot:SurfaceElement ;
    rdfs:label "Concept" ;
    rdfs:comment "An abstract idea or principle relevant to the API." ;
    rdfs:subClassOf skos:Concept .

doczot:Constraint a owl:Class ;
    rdfs:subClassOf doczot:SurfaceElement ;
    rdfs:label "Constraint" ;
    rdfs:comment "A restriction or requirement on API usage." ;
    owl:disjointUnionOf (doczot:AuthConstraint doczot:RateLimitConstraint doczot:PrerequisiteConstraint) .

# =============================================================================
# CONSTRAINT SUBCLASSES
# =============================================================================

doczot:AuthConstraint a owl:Class ;
    rdfs:subClassOf doczot:Constraint ;
    rdfs:label "Authentication Constraint" ;
    rdfs:comment "Requires authentication to access." .

doczot:RateLimitConstraint a owl:Class ;
    rdfs:subClassOf doczot:Constraint ;
    rdfs:label "Rate Limit Constraint" ;
    rdfs:comment "Limits the frequency of API calls." .

doczot:PrerequisiteConstraint a owl:Class ;
    rdfs:subClassOf doczot:Constraint ;
    rdfs:label "Prerequisite Constraint" ;
    rdfs:comment "Requires another operation to be performed first." .

# =============================================================================
# DOCUMENTATION CLASSES
# =============================================================================

doczot:Topic a owl:Class ;
    rdfs:label "Documentation Topic" ;
    rdfs:comment "A unit of documentation that covers one or more surface elements." .

doczot:TopicManifest a owl:Class ;
    rdfs:label "Topic Manifest" ;
    rdfs:comment "A collection of topics representing intended or actual documentation." ;
    owl:disjointUnionOf (doczot:IntendedTopicManifest doczot:ActualTopicManifest) .

doczot:IntendedTopicManifest a owl:Class ;
    rdfs:subClassOf doczot:TopicManifest ;
    rdfs:label "Intended Topic Manifest (ITM)" ;
    rdfs:comment "Topics that SHOULD exist based on the surface graph." .

doczot:ActualTopicManifest a owl:Class ;
    rdfs:subClassOf doczot:TopicManifest ;
    rdfs:label "Actual Topic Manifest (ATM)" ;
    rdfs:comment "Topics that DO exist in current documentation." .

doczot:Gap a owl:Class ;
    rdfs:label "Documentation Gap" ;
    rdfs:comment "A discrepancy between intended and actual documentation." .

# =============================================================================
# ANALYSIS CLASSES
# =============================================================================

doczot:SurfaceGraph a owl:Class ;
    rdfs:label "Surface Graph" ;
    rdfs:comment "An immutable snapshot of the API surface at a point in time." ;
    rdfs:subClassOf prov:Entity .

doczot:Scan a owl:Class ;
    rdfs:label "Scan" ;
    rdfs:comment "An analysis activity that produces a surface graph." ;
    rdfs:subClassOf prov:Activity .
```

### 2.2 HTTP Method Enumeration

```turtle
doczot:HttpMethod a owl:Class ;
    rdfs:label "HTTP Method" ;
    owl:equivalentClass [
        a owl:Class ;
        owl:oneOf (doczot:GET doczot:POST doczot:PUT doczot:DELETE doczot:PATCH doczot:HEAD doczot:OPTIONS)
    ] .

doczot:GET a doczot:HttpMethod ; rdfs:label "GET" .
doczot:POST a doczot:HttpMethod ; rdfs:label "POST" .
doczot:PUT a doczot:HttpMethod ; rdfs:label "PUT" .
doczot:DELETE a doczot:HttpMethod ; rdfs:label "DELETE" .
doczot:PATCH a doczot:HttpMethod ; rdfs:label "PATCH" .
doczot:HEAD a doczot:HttpMethod ; rdfs:label "HEAD" .
doczot:OPTIONS a doczot:HttpMethod ; rdfs:label "OPTIONS" .
```

### 2.3 Topic Type Enumeration

```turtle
doczot:TopicType a owl:Class ;
    owl:equivalentClass [
        a owl:Class ;
        owl:oneOf (doczot:OnboardingTopic doczot:ConceptTopic doczot:TaskTopic doczot:ReferenceTopic doczot:ChangesTopic)
    ] .

doczot:OnboardingTopic a doczot:TopicType ; rdfs:label "Onboarding" ; rdfs:comment "Getting started guides" .
doczot:ConceptTopic a doczot:TopicType ; rdfs:label "Concept" ; rdfs:comment "Explanatory content" .
doczot:TaskTopic a doczot:TopicType ; rdfs:label "Task" ; rdfs:comment "How-to guides" .
doczot:ReferenceTopic a doczot:TopicType ; rdfs:label "Reference" ; rdfs:comment "API reference" .
doczot:ChangesTopic a doczot:TopicType ; rdfs:label "Changes" ; rdfs:comment "Changelog, deprecations" .
```

---

## 3. Property Definitions (T-Box)

### 3.1 Object Properties (Relationships)

```turtle
# =============================================================================
# CORE RELATIONSHIPS
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

# =============================================================================
# DOCUMENTATION RELATIONSHIPS
# =============================================================================

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

# =============================================================================
# PROVENANCE RELATIONSHIPS
# =============================================================================

doczot:producedBy a owl:ObjectProperty ;
    rdfs:subPropertyOf prov:wasGeneratedBy ;
    rdfs:domain doczot:SurfaceGraph ;
    rdfs:range doczot:Scan .

doczot:scannedFrom a owl:ObjectProperty ;
    rdfs:label "scanned from" ;
    rdfs:domain doczot:SurfaceGraph ;
    rdfs:range xsd:anyURI ;
    rdfs:comment "The source repository or path that was scanned." .
```

### 3.2 Datatype Properties (Attributes)

```turtle
# =============================================================================
# SURFACE ELEMENT PROPERTIES
# =============================================================================

doczot:name a owl:DatatypeProperty ;
    rdfs:label "name" ;
    rdfs:domain doczot:SurfaceElement ;
    rdfs:range xsd:string .

doczot:description a owl:DatatypeProperty ;
    rdfs:label "description" ;
    rdfs:domain doczot:SurfaceElement ;
    rdfs:range xsd:string .

doczot:sourceFile a owl:DatatypeProperty ;
    rdfs:label "source file" ;
    rdfs:domain doczot:SurfaceElement ;
    rdfs:range xsd:string .

doczot:sourceLine a owl:DatatypeProperty ;
    rdfs:label "source line" ;
    rdfs:domain doczot:SurfaceElement ;
    rdfs:range xsd:integer .

doczot:isUserFacing a owl:DatatypeProperty ;
    rdfs:label "is user facing" ;
    rdfs:domain doczot:SurfaceElement ;
    rdfs:range xsd:boolean .

doczot:isDeprecated a owl:DatatypeProperty ;
    rdfs:label "is deprecated" ;
    rdfs:domain doczot:SurfaceElement ;
    rdfs:range xsd:boolean .

# =============================================================================
# VERB-SPECIFIC PROPERTIES
# =============================================================================

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
    rdfs:domain doczot:Verb ;
    rdfs:range xsd:string ;
    rdfs:comment "Human-readable signature like 'GET /users/{id}'" .

# =============================================================================
# CONSTRAINT PROPERTIES
# =============================================================================

doczot:rateLimit a owl:DatatypeProperty ;
    rdfs:label "rate limit" ;
    rdfs:domain doczot:RateLimitConstraint ;
    rdfs:range xsd:string ;
    rdfs:comment "Rate limit specification like '100/hour'" .

doczot:authType a owl:DatatypeProperty ;
    rdfs:label "authentication type" ;
    rdfs:domain doczot:AuthConstraint ;
    rdfs:range xsd:string ;
    rdfs:comment "Type of auth required, e.g., 'jwt', 'api_key'" .

# =============================================================================
# TOPIC PROPERTIES
# =============================================================================

doczot:topicType a owl:ObjectProperty, owl:FunctionalProperty ;
    rdfs:label "topic type" ;
    rdfs:domain doczot:Topic ;
    rdfs:range doczot:TopicType .

doczot:sourceDocument a owl:DatatypeProperty ;
    rdfs:label "source document" ;
    rdfs:domain doczot:Topic ;
    rdfs:range xsd:anyURI .

# =============================================================================
# QUALITY METRICS
# =============================================================================

doczot:coverageScore a owl:DatatypeProperty ;
    rdfs:label "coverage score" ;
    rdfs:domain doczot:Topic ;
    rdfs:range xsd:decimal ;
    rdfs:comment "0.0 to 1.0 coverage completeness" .

doczot:agentReadinessScore a owl:DatatypeProperty ;
    rdfs:label "agent readiness score" ;
    rdfs:domain doczot:Topic ;
    rdfs:range xsd:decimal ;
    rdfs:comment "0.0 to 1.0 suitability for AI agent consumption" .

doczot:hasExamples a owl:DatatypeProperty ;
    rdfs:label "has examples" ;
    rdfs:domain doczot:Topic ;
    rdfs:range xsd:boolean .

doczot:hasErrorDocs a owl:DatatypeProperty ;
    rdfs:label "has error documentation" ;
    rdfs:domain doczot:Topic ;
    rdfs:range xsd:boolean .

# =============================================================================
# SCAN/PROVENANCE PROPERTIES
# =============================================================================

doczot:scannedAt a owl:DatatypeProperty ;
    rdfs:subPropertyOf prov:generatedAtTime ;
    rdfs:domain doczot:SurfaceGraph ;
    rdfs:range xsd:dateTime .

doczot:productName a owl:DatatypeProperty ;
    rdfs:domain doczot:SurfaceGraph ;
    rdfs:range xsd:string .

doczot:productVersion a owl:DatatypeProperty ;
    rdfs:domain doczot:SurfaceGraph ;
    rdfs:range xsd:string .
```

---

## 4. Axioms and Rules (Reasoning)

### 4.1 Class Axioms

```turtle
# =============================================================================
# DISJOINTNESS
# =============================================================================

# Surface element types are mutually exclusive
[] a owl:AllDisjointClasses ;
    owl:members (doczot:Verb doczot:Noun doczot:Concept doczot:Constraint) .

# Constraint types are mutually exclusive
[] a owl:AllDisjointClasses ;
    owl:members (doczot:AuthConstraint doczot:RateLimitConstraint doczot:PrerequisiteConstraint) .

# Manifest types are mutually exclusive
[] a owl:AllDisjointClasses ;
    owl:members (doczot:IntendedTopicManifest doczot:ActualTopicManifest) .

# =============================================================================
# CARDINALITY CONSTRAINTS
# =============================================================================

# Every Verb must have exactly one HTTP method
doczot:Verb rdfs:subClassOf [
    a owl:Restriction ;
    owl:onProperty doczot:httpMethod ;
    owl:cardinality 1
] .

# Every Verb must have exactly one HTTP path
doczot:Verb rdfs:subClassOf [
    a owl:Restriction ;
    owl:onProperty doczot:httpPath ;
    owl:cardinality 1
] .

# Every RateLimitConstraint must have a rate limit value
doczot:RateLimitConstraint rdfs:subClassOf [
    a owl:Restriction ;
    owl:onProperty doczot:rateLimit ;
    owl:minCardinality 1
] .

# =============================================================================
# CLOSURE AXIOMS
# =============================================================================

# A Verb operates on at least one Noun (closed world for well-formed APIs)
# Note: This is optional and depends on modeling philosophy
# doczot:Verb rdfs:subClassOf [
#     a owl:Restriction ;
#     owl:onProperty doczot:operatesOn ;
#     owl:minCardinality 1
# ] .
```

### 4.2 SWRL Rules (Advanced Reasoning)

```
# =============================================================================
# INFERRED RELATIONSHIPS
# =============================================================================

# Rule: If verb V is constrained by auth constraint C,
#       and verb L is the login endpoint,
#       then L is a prerequisite of V
doczot:Verb(?v) ^ doczot:constrainedBy(?v, ?c) ^ doczot:AuthConstraint(?c) ^
doczot:Verb(?l) ^ doczot:httpPath(?l, "/auth/login")
    -> doczot:prerequisiteOf(?l, ?v)

# Rule: If noun A is part of noun B, and verb V operates on A,
#       then V also implicitly relates to B
doczot:Verb(?v) ^ doczot:operatesOn(?v, ?a) ^ doczot:partOf(?a, ?b)
    -> doczot:relatedTo(?v, ?b)

# Rule: If a topic covers all elements that another topic covers,
#       the first subsumes the second
# (This would require a more complex rule or custom reasoner extension)

# =============================================================================
# COVERAGE INFERENCE
# =============================================================================

# Rule: A surface element is documented if it is covered by at least one ATM topic
doczot:SurfaceElement(?e) ^ doczot:coveredBy(?e, ?t) ^ doczot:hasTopic(?m, ?t) ^
doczot:ActualTopicManifest(?m)
    -> doczot:isDocumented(?e, true)

# Rule: A surface element has a gap if it's in ITM but not ATM
# (Requires negation-as-failure, typically done in SPARQL or code)
```

---

## 5. Instance Data (A-Box) Example

### 5.1 Surface Graph Instance

```turtle
@prefix doczot: <https://doczot.io/ontology/> .
@prefix data: <https://doczot.io/data/simple-test-api/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# =============================================================================
# SURFACE GRAPH
# =============================================================================

data:surface-2026-01-20 a doczot:SurfaceGraph ;
    doczot:productName "Simple Test API" ;
    doczot:scannedAt "2026-01-20T14:19:14Z"^^xsd:dateTime ;
    doczot:scannedFrom "file:///tmp/simple_test_app" .

# =============================================================================
# NOUNS
# =============================================================================

data:noun-user a doczot:Noun ;
    doczot:name "user" ;
    doczot:isUserFacing true .

data:noun-item a doczot:Noun ;
    doczot:name "item" ;
    doczot:isUserFacing true .

data:noun-project a doczot:Noun ;
    doczot:name "project" ;
    doczot:isUserFacing true ;
    doczot:partOf data:noun-user .  # project belongs to user

# =============================================================================
# VERBS
# =============================================================================

data:verb-get-users-me a doczot:Verb ;
    doczot:name "get_me" ;
    doczot:httpMethod doczot:GET ;
    doczot:httpPath "/users/me" ;
    doczot:codeSignature "GET /users/me" ;
    doczot:sourceFile "main.py" ;
    doczot:sourceLine 70 ;
    doczot:isUserFacing true ;
    doczot:operatesOn data:noun-user ;
    doczot:constrainedBy data:constraint-auth-get-users-me .

data:verb-get-items a doczot:Verb ;
    doczot:name "get_items" ;
    doczot:httpMethod doczot:GET ;
    doczot:httpPath "/items" ;
    doczot:codeSignature "GET /items" ;
    doczot:sourceFile "main.py" ;
    doczot:sourceLine 106 ;
    doczot:isUserFacing true ;
    doczot:operatesOn data:noun-item ;
    doczot:constrainedBy data:constraint-rate-get-items .

data:verb-post-auth-login a doczot:Verb ;
    doczot:name "login" ;
    doczot:httpMethod doczot:POST ;
    doczot:httpPath "/auth/login" ;
    doczot:codeSignature "POST /auth/login" ;
    doczot:sourceFile "main.py" ;
    doczot:sourceLine 193 ;
    doczot:isUserFacing true .

data:verb-get-user-projects a doczot:Verb ;
    doczot:name "get_projects" ;
    doczot:httpMethod doczot:GET ;
    doczot:httpPath "/users/{user_id}/projects" ;
    doczot:codeSignature "GET /users/{user_id}/projects" ;
    doczot:sourceFile "main.py" ;
    doczot:sourceLine 136 ;
    doczot:isUserFacing true ;
    doczot:operatesOn data:noun-project, data:noun-user ;
    doczot:constrainedBy data:constraint-auth-get-user-projects .

# =============================================================================
# CONSTRAINTS
# =============================================================================

data:constraint-auth-get-users-me a doczot:AuthConstraint ;
    doczot:name "auth_required" ;
    doczot:description "Authentication required: get_current_user" ;
    doczot:authType "jwt" ;
    doczot:sourceFile "main.py" ;
    doczot:sourceLine 70 .

data:constraint-auth-get-user-projects a doczot:AuthConstraint ;
    doczot:name "auth_required" ;
    doczot:description "Authentication required: get_current_user" ;
    doczot:authType "jwt" ;
    doczot:sourceFile "main.py" ;
    doczot:sourceLine 136 .

data:constraint-rate-get-items a doczot:RateLimitConstraint ;
    doczot:name "rate_limit" ;
    doczot:description "Rate limited to 100/hour" ;
    doczot:rateLimit "100/hour" ;
    doczot:sourceFile "main.py" ;
    doczot:sourceLine 106 .

# =============================================================================
# CONCEPTS
# =============================================================================

data:concept-authentication a doczot:Concept ;
    doczot:name "authentication" ;
    doczot:description "Authentication is performed via JWT tokens." ;
    doczot:sourceFile "README.md" .

data:concept-rate-limiting a doczot:Concept ;
    doczot:name "rate limiting" ;
    doczot:description "Rate limiting protects the API from abuse." ;
    doczot:sourceFile "README.md" .

# =============================================================================
# INFERRED RELATIONSHIPS (would be computed by reasoner)
# =============================================================================

# Because project partOf user (transitive), and verb operates on project,
# the reasoner can infer relatedTo relationships

# Because verb-get-users-me has AuthConstraint,
# the reasoner infers: verb-post-auth-login prerequisiteOf verb-get-users-me
```

### 5.2 Documentation Instance

```turtle
# =============================================================================
# ACTUAL TOPIC MANIFEST (ATM)
# =============================================================================

data:atm-2026-01-20 a doczot:ActualTopicManifest ;
    doczot:productName "Simple Test API" ;
    doczot:hasTopic data:topic-readme .

data:topic-readme a doczot:Topic ;
    doczot:name "README" ;
    doczot:topicType doczot:ReferenceTopic ;
    doczot:sourceDocument "file:///tmp/simple_test_app/README.md" ;
    doczot:coverageScore 0.2 ;
    doczot:agentReadinessScore 0.6 ;
    doczot:hasExamples false ;
    doczot:hasErrorDocs false ;
    doczot:covers data:verb-get-users-me,
                  data:verb-get-items,
                  data:verb-post-auth-login,
                  data:verb-get-user-projects,
                  data:noun-user,
                  data:noun-item,
                  data:noun-project,
                  data:concept-authentication,
                  data:concept-rate-limiting .
```

---

## 6. SPARQL Query Examples

### 6.1 Find Undocumented Endpoints

```sparql
PREFIX doczot: <https://doczot.io/ontology/>

SELECT ?verb ?path ?method
WHERE {
    ?verb a doczot:Verb ;
          doczot:httpPath ?path ;
          doczot:httpMethod ?method ;
          doczot:isUserFacing true .

    FILTER NOT EXISTS {
        ?topic doczot:covers ?verb .
        ?atm doczot:hasTopic ?topic .
        ?atm a doczot:ActualTopicManifest .
    }
}
ORDER BY ?path
```

### 6.2 Find All Auth-Protected Endpoints

```sparql
PREFIX doczot: <https://doczot.io/ontology/>

SELECT ?verb ?path ?authType
WHERE {
    ?verb a doczot:Verb ;
          doczot:httpPath ?path ;
          doczot:constrainedBy ?constraint .

    ?constraint a doczot:AuthConstraint ;
                doczot:authType ?authType .
}
```

### 6.3 Find Noun Hierarchy

```sparql
PREFIX doczot: <https://doczot.io/ontology/>

SELECT ?child ?parent
WHERE {
    ?child doczot:partOf+ ?parent .  # + for transitive closure
}
```

### 6.4 Calculate Coverage Statistics

```sparql
PREFIX doczot: <https://doczot.io/ontology/>

SELECT
    (COUNT(DISTINCT ?documented) AS ?documentedCount)
    (COUNT(DISTINCT ?all) AS ?totalCount)
    (COUNT(DISTINCT ?documented) * 100.0 / COUNT(DISTINCT ?all) AS ?coveragePercent)
WHERE {
    ?all a doczot:SurfaceElement ;
         doczot:isUserFacing true .

    OPTIONAL {
        ?topic doczot:covers ?all .
        ?atm doczot:hasTopic ?topic .
        ?atm a doczot:ActualTopicManifest .
        BIND(?all AS ?documented)
    }
}
```

### 6.5 Find Prerequisites for an Endpoint

```sparql
PREFIX doczot: <https://doczot.io/ontology/>

SELECT ?prereq ?prereqPath
WHERE {
    ?target doczot:httpPath "/users/me" .
    ?prereq doczot:prerequisiteOf ?target ;
            doczot:httpPath ?prereqPath .
}
```

### 6.6 Find All Elements Related to a Noun

```sparql
PREFIX doczot: <https://doczot.io/ontology/>

SELECT ?element ?elementType ?relationship
WHERE {
    ?noun doczot:name "user" .

    {
        ?element doczot:operatesOn ?noun .
        BIND("operates_on" AS ?relationship)
        BIND("verb" AS ?elementType)
    }
    UNION
    {
        ?element doczot:partOf ?noun .
        BIND("part_of" AS ?relationship)
        BIND("noun" AS ?elementType)
    }
    UNION
    {
        ?noun doczot:partOf ?element .
        BIND("has_part" AS ?relationship)
        BIND("noun" AS ?elementType)
    }
}
```

---

## 7. Python Implementation

### 7.1 Dependencies

```toml
# pyproject.toml additions
[project.dependencies]
rdflib = ">=7.0.0"
owlready2 = ">=0.46"
sparqlwrapper = ">=2.0.0"  # for remote SPARQL endpoints
```

### 7.2 Core Implementation

```python
"""doczot_analyzer/ontology.py - RDF/OWL ontology implementation."""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterator
from urllib.parse import quote

from rdflib import Graph, Namespace, Literal, URIRef, BNode
from rdflib.namespace import RDF, RDFS, OWL, XSD, SKOS
from owlready2 import get_ontology, Thing, ObjectProperty, DataProperty

# =============================================================================
# NAMESPACES
# =============================================================================

DOCZOT = Namespace("https://doczot.io/ontology/")
DATA = Namespace("https://doczot.io/data/")
PROV = Namespace("http://www.w3.org/ns/prov#")
HYDRA = Namespace("http://www.w3.org/ns/hydra/core#")

# =============================================================================
# ONTOLOGY GRAPH
# =============================================================================

class DoczotOntology:
    """RDF/OWL ontology for DocZot surface graphs."""

    def __init__(self, product_name: str):
        self.product_name = product_name
        self.product_slug = quote(product_name.lower().replace(" ", "-"))
        self.graph = Graph()
        self._bind_namespaces()

    def _bind_namespaces(self) -> None:
        """Bind standard prefixes."""
        self.graph.bind("doczot", DOCZOT)
        self.graph.bind("data", DATA)
        self.graph.bind("prov", PROV)
        self.graph.bind("skos", SKOS)
        self.graph.bind("hydra", HYDRA)

    def _data_uri(self, type_: str, id_: str) -> URIRef:
        """Generate a data URI for an instance."""
        safe_id = quote(id_.replace("/", "-").replace(":", "-"))
        return URIRef(f"{DATA}{self.product_slug}/{type_}/{safe_id}")

    # =========================================================================
    # ADD SURFACE ELEMENTS
    # =========================================================================

    def add_noun(
        self,
        name: str,
        description: Optional[str] = None,
        source_file: Optional[str] = None,
        source_line: Optional[int] = None,
        is_user_facing: bool = True,
        part_of: Optional[str] = None,
    ) -> URIRef:
        """Add a noun (entity) to the ontology."""
        uri = self._data_uri("noun", name)

        self.graph.add((uri, RDF.type, DOCZOT.Noun))
        self.graph.add((uri, DOCZOT.name, Literal(name)))
        self.graph.add((uri, DOCZOT.isUserFacing, Literal(is_user_facing)))

        if description:
            self.graph.add((uri, DOCZOT.description, Literal(description)))
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
        description: Optional[str] = None,
        source_file: Optional[str] = None,
        source_line: Optional[int] = None,
        is_user_facing: bool = True,
        operates_on: Optional[list[str]] = None,
    ) -> URIRef:
        """Add a verb (endpoint) to the ontology."""
        # Create unique ID from method + path
        verb_id = f"{http_method}-{http_path}"
        uri = self._data_uri("verb", verb_id)

        # Get HTTP method URI
        method_uri = URIRef(f"{DOCZOT}{http_method}")

        self.graph.add((uri, RDF.type, DOCZOT.Verb))
        self.graph.add((uri, DOCZOT.name, Literal(name)))
        self.graph.add((uri, DOCZOT.httpMethod, method_uri))
        self.graph.add((uri, DOCZOT.httpPath, Literal(http_path)))
        self.graph.add((uri, DOCZOT.codeSignature, Literal(f"{http_method} {http_path}")))
        self.graph.add((uri, DOCZOT.isUserFacing, Literal(is_user_facing)))

        if description:
            self.graph.add((uri, DOCZOT.description, Literal(description)))
        if source_file:
            self.graph.add((uri, DOCZOT.sourceFile, Literal(source_file)))
        if source_line is not None:
            self.graph.add((uri, DOCZOT.sourceLine, Literal(source_line, datatype=XSD.integer)))

        if operates_on:
            for noun_name in operates_on:
                noun_uri = self._data_uri("noun", noun_name)
                self.graph.add((uri, DOCZOT.operatesOn, noun_uri))

        return uri

    def add_constraint(
        self,
        constraint_type: str,  # "auth" or "rate_limit"
        name: str,
        description: str,
        constrains: URIRef,
        value: Optional[str] = None,
        source_file: Optional[str] = None,
        source_line: Optional[int] = None,
    ) -> URIRef:
        """Add a constraint to the ontology."""
        constraint_id = f"{constraint_type}-{name}-{constrains.split('/')[-1]}"
        uri = self._data_uri("constraint", constraint_id)

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
        self.graph.add((uri, DOCZOT.description, Literal(description)))
        self.graph.add((constrains, DOCZOT.constrainedBy, uri))

        if source_file:
            self.graph.add((uri, DOCZOT.sourceFile, Literal(source_file)))
        if source_line is not None:
            self.graph.add((uri, DOCZOT.sourceLine, Literal(source_line, datatype=XSD.integer)))

        return uri

    def add_concept(
        self,
        name: str,
        description: Optional[str] = None,
        source_file: Optional[str] = None,
    ) -> URIRef:
        """Add a concept to the ontology."""
        uri = self._data_uri("concept", name)

        self.graph.add((uri, RDF.type, DOCZOT.Concept))
        self.graph.add((uri, RDF.type, SKOS.Concept))  # Also a SKOS concept
        self.graph.add((uri, DOCZOT.name, Literal(name)))
        self.graph.add((uri, SKOS.prefLabel, Literal(name)))

        if description:
            self.graph.add((uri, DOCZOT.description, Literal(description)))
            self.graph.add((uri, SKOS.definition, Literal(description)))
        if source_file:
            self.graph.add((uri, DOCZOT.sourceFile, Literal(source_file)))

        return uri

    # =========================================================================
    # ADD RELATIONSHIPS
    # =========================================================================

    def add_prerequisite(self, source: URIRef, target: URIRef) -> None:
        """Add a prerequisite relationship."""
        self.graph.add((source, DOCZOT.prerequisiteOf, target))

    def add_related(self, source: URIRef, target: URIRef) -> None:
        """Add a related_to relationship."""
        self.graph.add((source, DOCZOT.relatedTo, target))

    # =========================================================================
    # QUERYING
    # =========================================================================

    def query(self, sparql: str) -> list[dict]:
        """Execute a SPARQL query and return results as dicts."""
        results = self.graph.query(sparql)
        return [dict(zip(results.vars, row)) for row in results]

    def get_undocumented_verbs(self) -> list[dict]:
        """Find all verbs not covered by any ATM topic."""
        return self.query("""
            PREFIX doczot: <https://doczot.io/ontology/>

            SELECT ?verb ?path ?method
            WHERE {
                ?verb a doczot:Verb ;
                      doczot:httpPath ?path ;
                      doczot:httpMethod ?method ;
                      doczot:isUserFacing true .

                FILTER NOT EXISTS {
                    ?topic doczot:covers ?verb .
                    ?atm doczot:hasTopic ?topic .
                    ?atm a doczot:ActualTopicManifest .
                }
            }
            ORDER BY ?path
        """)

    def get_coverage_stats(self) -> dict:
        """Calculate coverage statistics."""
        results = self.query("""
            PREFIX doczot: <https://doczot.io/ontology/>

            SELECT
                (COUNT(DISTINCT ?all) AS ?total)
                (COUNT(DISTINCT ?documented) AS ?covered)
            WHERE {
                ?all a doczot:SurfaceElement ;
                     doczot:isUserFacing true .

                OPTIONAL {
                    ?topic doczot:covers ?all .
                    ?atm doczot:hasTopic ?topic .
                    ?atm a doczot:ActualTopicManifest .
                    BIND(?all AS ?documented)
                }
            }
        """)

        if results:
            total = int(results[0]["total"])
            covered = int(results[0]["covered"])
            return {
                "total": total,
                "covered": covered,
                "coverage_percent": (covered / total * 100) if total > 0 else 0,
            }
        return {"total": 0, "covered": 0, "coverage_percent": 0}

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def serialize(self, format: str = "turtle") -> str:
        """Serialize the ontology to a string.

        Formats: turtle, xml, json-ld, n3, ntriples
        """
        return self.graph.serialize(format=format)

    def save(self, path: Path, format: str = "turtle") -> None:
        """Save the ontology to a file."""
        path.write_text(self.serialize(format))

    def load(self, path: Path, format: str = "turtle") -> None:
        """Load an ontology from a file."""
        self.graph.parse(path, format=format)

    # =========================================================================
    # REASONING
    # =========================================================================

    def run_reasoner(self) -> None:
        """Run OWL reasoning to infer additional triples.

        Uses owlready2 for reasoning.
        """
        from owlready2 import default_world, sync_reasoner_pellet

        # Export to temp file for owlready2
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ttl", delete=False) as f:
            f.write(self.serialize("turtle").encode())
            temp_path = f.name

        # Load into owlready2 and reason
        onto = get_ontology(f"file://{temp_path}").load()
        sync_reasoner_pellet(infer_property_values=True, infer_data_property_values=True)

        # Export back and reload
        onto.save(temp_path, format="rdfxml")
        self.graph.parse(temp_path, format="xml")

        # Cleanup
        Path(temp_path).unlink()


# =============================================================================
# CONVERSION FROM CURRENT MODELS
# =============================================================================

def surface_graph_to_ontology(surface: "SurfaceGraph") -> DoczotOntology:
    """Convert a SurfaceGraph (current model) to RDF/OWL ontology."""
    from doczot_analyzer.models_v2 import NodeType, EdgeType

    onto = DoczotOntology(surface.product_name)

    # Track URIs for edge creation
    node_uris: dict[str, URIRef] = {}

    # Add nodes
    for node in surface.nodes:
        if node.type == NodeType.NOUN:
            uri = onto.add_noun(
                name=node.name,
                description=node.description,
                source_file=node.source_file,
                source_line=node.source_line,
            )
        elif node.type == NodeType.VERB:
            uri = onto.add_verb(
                name=node.name,
                http_method=node.http_method or "GET",
                http_path=node.http_path or "/",
                description=node.description,
                source_file=node.source_file,
                source_line=node.source_line,
            )
        elif node.type == NodeType.CONCEPT:
            uri = onto.add_concept(
                name=node.name,
                description=node.description,
                source_file=node.source_file,
            )
        elif node.type == NodeType.CONSTRAINT:
            # Constraints are added via edges, skip for now
            continue
        else:
            continue

        node_uris[node.id] = uri

    # Add edges
    for edge in surface.edges:
        source_uri = node_uris.get(edge.source_id)
        target_uri = node_uris.get(edge.target_id)

        if not source_uri or not target_uri:
            continue

        if edge.edge_type == EdgeType.OPERATES_ON:
            onto.graph.add((source_uri, DOCZOT.operatesOn, target_uri))
        elif edge.edge_type == EdgeType.PART_OF:
            onto.graph.add((source_uri, DOCZOT.partOf, target_uri))
        elif edge.edge_type == EdgeType.PREREQUISITE:
            onto.add_prerequisite(source_uri, target_uri)
        elif edge.edge_type == EdgeType.CONSTRAINED_BY:
            # Find the constraint node and add it properly
            constraint_node = next((n for n in surface.nodes if n.id == edge.target_id), None)
            if constraint_node:
                c_type = "auth" if "auth" in constraint_node.name else "rate_limit"
                onto.add_constraint(
                    constraint_type=c_type,
                    name=constraint_node.name,
                    description=constraint_node.description or "",
                    constrains=source_uri,
                    source_file=constraint_node.source_file,
                    source_line=constraint_node.source_line,
                )
        elif edge.edge_type == EdgeType.RELATED_TO:
            onto.add_related(source_uri, target_uri)

    return onto
```

### 7.3 CLI Integration

```python
# Addition to cli_v2.py

@click.command()
@click.argument('repo_path', required=False)
@click.option('--name', help='Product name')
@click.option('--format', type=click.Choice(['turtle', 'json-ld', 'xml', 'ntriples']), default='turtle')
@click.option('--output', '-o', help='Output file')
@click.option('--reason', is_flag=True, help='Run OWL reasoner')
def export_ontology(repo_path: str, name: str, format: str, output: str, reason: bool):
    """Export surface graph as RDF/OWL ontology."""
    from doczot_analyzer.ontology import surface_graph_to_ontology

    repo_path = repo_path or "."
    surface, _, _, _ = analyze_repository(repo_path, name)

    onto = surface_graph_to_ontology(surface)

    if reason:
        click.echo("Running OWL reasoner...")
        onto.run_reasoner()

    serialized = onto.serialize(format)

    if output:
        Path(output).write_text(serialized)
        click.echo(f"Ontology saved to: {output}")
    else:
        click.echo(serialized)
```

---

## 8. Integration Points

### 8.1 Export Formats

| Format | Use Case | Command |
|--------|----------|---------|
| Turtle | Human-readable, version control | `--format turtle` |
| JSON-LD | Web APIs, JavaScript | `--format json-ld` |
| RDF/XML | Legacy tools, OWL editors | `--format xml` |
| N-Triples | Bulk loading, streaming | `--format ntriples` |

### 8.2 Tool Integration

| Tool | Purpose | How |
|------|---------|-----|
| **Protégé** | Visual ontology editing | Load .ttl or .owl file |
| **Apache Jena** | SPARQL endpoint | Load into Fuseki |
| **Neo4j** | Graph visualization | Use neosemantics (n10s) |
| **GraphDB** | Enterprise triplestore | Direct import |

### 8.3 Reasoning Capabilities

With OWL reasoning enabled:

1. **Transitive inference**: If A partOf B and B partOf C → A partOf C
2. **Inverse inference**: If A partOf B → B hasPart A
3. **Symmetric inference**: If A relatedTo B → B relatedTo A
4. **Prerequisite chains**: Auth-protected → login prerequisite
5. **Consistency checking**: Detect invalid combinations

---

## 9. Migration Path

### Phase 1: Add Export (Non-breaking)
- Implement `ontology.py`
- Add `export-ontology` CLI command
- Keep existing Pydantic models as primary

### Phase 2: Parallel Storage
- Store both JSON and RDF
- Use RDF for queries requiring reasoning
- Maintain backward compatibility

### Phase 3: Full Migration (Optional)
- Replace SQLite with triplestore
- Use SPARQL as primary query interface
- Deprecate custom query methods

---

## 10. Benefits of This Implementation

1. **Interoperability**: Standard formats enable tool ecosystem integration
2. **Reasoning**: Automated inference discovers implicit relationships
3. **Validation**: Reasoners detect inconsistencies automatically
4. **Extensibility**: OWL allows adding new classes/properties without breaking
5. **Querying**: SPARQL provides powerful, declarative queries
6. **Linked Data**: IRIs enable linking to external ontologies
7. **Documentation**: Self-describing via rdfs:label and rdfs:comment
8. **Future-proof**: W3C standards with broad industry adoption
