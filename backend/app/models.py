"""
Pydantic models for all API request/response schemas.
These define the contract between the frontend and backend.
"""
from pydantic import BaseModel, Field
from typing import Any, Optional
from enum import Enum


# ── Entity Types ──────────────────────────────────────────────────────────────────
class EntityType(str, Enum):
    DISEASE = "Disease"
    DRUG = "Drug"
    GENE = "Gene"
    SYMPTOM = "Symptom"
    TREATMENT_PROTOCOL = "TreatmentProtocol"
    BLOOD_TEST = "BloodTest"


# ── Relationship Types ────────────────────────────────────────────────────────────
class RelationshipType(str, Enum):
    TREATS = "TREATS"
    CAUSES = "CAUSES"
    INHIBITS = "INHIBITS"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    DIAGNOSES = "DIAGNOSES"
    MEASURES = "MEASURES"
    PART_OF = "PART_OF"
    INDICATES = "INDICATES"
    PRESCRIBED_FOR = "PRESCRIBED_FOR"
    MONITORS = "MONITORS"


# ── Core Graph Elements ───────────────────────────────────────────────────────────
class Entity(BaseModel):
    """A node in the knowledge graph."""
    id: str = Field(..., description="Unique hash-based identifier")
    name: str = Field(..., description="Human-readable entity name")
    type: str = Field(..., description="Entity type (Disease, Drug, etc.)")
    description: str = Field(default="", description="Brief description from LLM")
    properties: dict[str, Any] = Field(default_factory=dict)


class Relationship(BaseModel):
    """A directed edge between two graph nodes."""
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    type: str = Field(..., description="Relationship type (TREATS, CAUSES, etc.)")
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphData(BaseModel):
    """Sub-graph data structure used for frontend visualization."""
    nodes: list[Entity]
    links: list[Relationship]


# ── API Request/Response Models ──────────────────────────────────────────────────
class UploadResponse(BaseModel):
    message: str
    filename: str
    entities_extracted: int
    relationships_extracted: int
    chunks_processed: int


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)


class ChatResponse(BaseModel):
    answer: str
    subgraph: GraphData
    sources: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    neo4j_connected: bool
    environment: str


class GraphStatsResponse(BaseModel):
    total_nodes: int
    total_relationships: int
    node_types: dict[str, int]
    relationship_types: dict[str, int]
    graph: GraphData
