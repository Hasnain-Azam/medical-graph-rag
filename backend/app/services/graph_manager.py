"""
Graph Manager — all Neo4j interactions.

Responsibilities:
  - Manage the Neo4j driver lifecycle (connect / close)
  - Set up vector index on startup
  - MERGE entity nodes with embeddings (deduplication by ID)
  - MERGE relationships between entities
  - Vector similarity search to find semantically relevant entities
  - Subgraph expansion (N hops around seed nodes)
  - Full graph retrieval for dashboard overview
"""
import logging
from typing import Any

from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable

from app.config import get_settings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────────
VECTOR_INDEX_NAME = "entity_embeddings"


class GraphManager:
    """Thread-safe Neo4j driver wrapper with medical graph operations."""

    def __init__(self):
        self._driver: Driver | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────────
    def connect(self) -> None:
        settings = get_settings()
        try:
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_username, settings.neo4j_password),
            )
            self._driver.verify_connectivity()
            logger.info("✅ Connected to Neo4j successfully.")
            self._setup_indexes()
        except ServiceUnavailable as e:
            logger.error(f"❌ Cannot connect to Neo4j: {e}")
            raise

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            logger.info("Neo4j driver closed.")

    def is_connected(self) -> bool:
        try:
            if self._driver:
                self._driver.verify_connectivity()
                return True
        except Exception:
            pass
        return False

    # ── Index Setup ────────────────────────────────────────────────────────────────
    def _setup_indexes(self) -> None:
        """Create vector index and uniqueness constraint on first run."""
        settings = get_settings()

        with self._driver.session() as session:
            # Uniqueness constraint on entity ID
            session.run("""
                CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
                FOR (e:Entity) REQUIRE e.id IS UNIQUE
            """)

            # Vector index for semantic similarity search (Neo4j 5.x native)
            session.run(f"""
                CREATE VECTOR INDEX {VECTOR_INDEX_NAME} IF NOT EXISTS
                FOR (e:Entity) ON (e.embedding)
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {settings.openai_embedding_dimensions},
                        `vector.similarity_function`: 'cosine'
                    }}
                }}
            """)

        logger.info("Neo4j indexes are ready.")

    # ── Write Operations ───────────────────────────────────────────────────────────
    def upsert_entity(self, entity: dict, embedding: list[float]) -> None:
        """
        MERGE entity node (no duplicates if same document is re-processed).
        Sets all properties and the embedding vector.
        """
        with self._driver.session() as session:
            session.run(
                """
                MERGE (e:Entity {id: $id})
                SET e.name        = $name,
                    e.type        = $type,
                    e.description = $description,
                    e.embedding   = $embedding,
                    e.properties  = $properties
                WITH e
                CALL apoc.create.addLabels(e, [$type]) YIELD node
                RETURN node
                """,
                id=entity["id"],
                name=entity["name"],
                type=entity["type"],
                description=entity["description"],
                embedding=embedding,
                properties=str(entity.get("properties", {})),
            )

    def upsert_entity_simple(self, entity: dict, embedding: list[float]) -> None:
        """
        MERGE entity node without APOC (works on vanilla Neo4j 5.x).
        Uses dynamic labels via separate queries.
        """
        with self._driver.session() as session:
            # 1. Upsert the base node with :Entity label
            session.run(
                """
                MERGE (e:Entity {id: $id})
                SET e.name        = $name,
                    e.type        = $type,
                    e.description = $description,
                    e.embedding   = $embedding,
                    e.properties  = $properties
                """,
                id=entity["id"],
                name=entity["name"],
                type=entity["type"],
                description=entity["description"],
                embedding=embedding,
                properties=str(entity.get("properties", {})),
            )

    def upsert_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """
        MERGE a directed relationship between two Entity nodes.
        Only creates if both source and target exist.
        """
        # Cypher doesn't allow parameterized relationship types — use f-string safely
        # (rel_type is validated upstream from a closed enum)
        safe_type = rel_type.upper().replace(" ", "_")
        query = f"""
            MATCH (src:Entity {{id: $source_id}})
            MATCH (tgt:Entity {{id: $target_id}})
            MERGE (src)-[r:{safe_type}]->(tgt)
            SET r.properties = $properties
        """
        with self._driver.session() as session:
            session.run(
                query,
                source_id=source_id,
                target_id=target_id,
                properties=str(properties or {}),
            )

    # ── Read Operations ────────────────────────────────────────────────────────────
    def vector_similarity_search(
        self, query_embedding: list[float], top_k: int = 5
    ) -> list[dict]:
        """
        Find the top-k entity nodes most similar to the query embedding.
        Uses the native Neo4j vector index.
        """
        with self._driver.session() as session:
            result = session.run(
                f"""
                CALL db.index.vector.queryNodes('{VECTOR_INDEX_NAME}', $top_k, $embedding)
                YIELD node, score
                WHERE score > 0.4
                RETURN node.id   AS id,
                       node.name AS name,
                       node.type AS type,
                       node.description AS description,
                       score
                ORDER BY score DESC
                """,
                top_k=top_k,
                embedding=query_embedding,
            )
            return [dict(record) for record in result]

    def expand_subgraph(
        self, seed_node_ids: list[str], hops: int = 2
    ) -> tuple[list[dict], list[dict]]:
        """
        Expand a subgraph N hops around the given seed node IDs.
        Returns (nodes, relationships) as plain dicts ready for JSON serialization.
        """
        if not seed_node_ids:
            return [], []

        with self._driver.session() as session:
            result = session.run(
                f"""
                MATCH path = (seed:Entity)-[*0..{hops}]-(neighbor:Entity)
                WHERE seed.id IN $seed_ids
                WITH nodes(path) AS ns, relationships(path) AS rs
                UNWIND ns AS n
                WITH COLLECT(DISTINCT n) AS all_nodes, rs
                UNWIND rs AS r
                WITH all_nodes, COLLECT(DISTINCT r) AS all_rels
                RETURN all_nodes, all_rels
                """,
                seed_ids=seed_node_ids,
            )

            record = result.single()
            if not record:
                # Fallback: return just the seed nodes
                return self._fetch_nodes_by_ids(seed_node_ids), []

            raw_nodes = record["all_nodes"]
            raw_rels = record["all_rels"]

        nodes = [
            {
                "id": n["id"],
                "name": n["name"],
                "type": n["type"],
                "description": n.get("description", ""),
                "properties": {},
            }
            for n in raw_nodes
            if n.get("id")
        ]

        links = [
            {
                "source": r.start_node["id"],
                "target": r.end_node["id"],
                "type": r.type,
                "properties": {},
            }
            for r in raw_rels
            if r.start_node.get("id") and r.end_node.get("id")
        ]

        return nodes, links

    def _fetch_nodes_by_ids(self, node_ids: list[str]) -> list[dict]:
        """Fetch node data for a list of IDs."""
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity) WHERE e.id IN $ids
                RETURN e.id AS id, e.name AS name, e.type AS type,
                       e.description AS description
                """,
                ids=node_ids,
            )
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "type": r["type"],
                    "description": r.get("description", ""),
                    "properties": {},
                }
                for r in result
            ]

    def get_full_graph(self) -> tuple[list[dict], list[dict]]:
        """
        Return the entire graph (capped at 200 nodes for performance).
        Used by the dashboard overview panel.
        """
        with self._driver.session() as session:
            node_result = session.run(
                """
                MATCH (e:Entity)
                RETURN e.id AS id, e.name AS name, e.type AS type,
                       e.description AS description
                LIMIT 200
                """
            )
            nodes = [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "type": r["type"],
                    "description": r.get("description", ""),
                    "properties": {},
                }
                for r in node_result
            ]

            rel_result = session.run(
                """
                MATCH (src:Entity)-[r]->(tgt:Entity)
                RETURN src.id AS source, tgt.id AS target, type(r) AS type
                LIMIT 500
                """
            )
            links = [
                {"source": r["source"], "target": r["target"], "type": r["type"], "properties": {}}
                for r in rel_result
            ]

        return nodes, links

    def get_graph_stats(self) -> dict:
        """Return counts of nodes/relationships broken down by type."""
        with self._driver.session() as session:
            total_nodes = session.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]
            total_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]

            node_types_result = session.run(
                "MATCH (e:Entity) RETURN e.type AS type, count(e) AS c"
            )
            node_types = {r["type"]: r["c"] for r in node_types_result}

            rel_types_result = session.run(
                "MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS c"
            )
            rel_types = {r["type"]: r["c"] for r in rel_types_result}

        return {
            "total_nodes": total_nodes,
            "total_relationships": total_rels,
            "node_types": node_types,
            "relationship_types": rel_types,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────────
graph_manager = GraphManager()
