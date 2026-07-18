"""
Enterprise Knowledge Graph Engine.

Builds and queries an auditable trade relationship graph for the Dawlat AI
Procurement & Global Trade Intelligence Platform.

The graph connects:
- buyers and suppliers;
- products and product categories;
- countries, cities, ports and trade routes;
- opportunities, RFQs, quotations and landed-cost scenarios;
- shipments, warehouses and logistics partners;
- certificates, compliance records, risks and trust evidence;
- workflows, recommendations and learned performance.

The current implementation uses SQLite-backed nodes and edges so it works with
the existing platform. The public API is provider-neutral and can later be
adapted to Neo4j, Amazon Neptune, Azure Cosmos DB, PostgreSQL/Apache AGE or
another graph database without changing business modules.

The engine is read-only with respect to commercial execution. It does not
contact companies, issue quotations, create purchase orders, release payments
or instruct shipments.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Iterable
from uuid import uuid4

from database.connection import get_connection
from services.ai_assistant_service import build_ai_context


class NodeType(str, Enum):
    BUYER = "Buyer"
    SUPPLIER = "Supplier"
    PARTNER = "Partner"
    PRODUCT = "Product"
    PRODUCT_CATEGORY = "Product Category"
    COUNTRY = "Country"
    CITY = "City"
    PORT = "Port"
    ROUTE = "Route"
    OPPORTUNITY = "Opportunity"
    RFQ = "RFQ"
    QUOTATION = "Quotation"
    LANDED_COST = "Landed Cost"
    SHIPMENT = "Shipment"
    SHIPPING_LINE = "Shipping Line"
    WAREHOUSE = "Warehouse"
    CERTIFICATE = "Certificate"
    DOCUMENT = "Document"
    WORKFLOW = "Workflow"
    RISK = "Risk"
    RECOMMENDATION = "Recommendation"
    PAYMENT = "Payment"
    USER = "User"


class EdgeType(str, Enum):
    INTERESTED_IN = "Interested In"
    SUPPLIES = "Supplies"
    MANUFACTURES = "Manufactures"
    LOCATED_IN = "Located In"
    ORIGINATES_FROM = "Originates From"
    DESTINED_FOR = "Destined For"
    REQUIRES = "Requires"
    HAS_CERTIFICATE = "Has Certificate"
    HAS_QUOTATION = "Has Quotation"
    QUOTES_FOR = "Quotes For"
    MATCHES = "Matches"
    FULFILLS = "Fulfils"
    USES_ROUTE = "Uses Route"
    SHIPPED_BY = "Shipped By"
    STORED_AT = "Stored At"
    LINKED_TO = "Linked To"
    CALCULATED_FOR = "Calculated For"
    HAS_RISK = "Has Risk"
    HAS_RECOMMENDATION = "Has Recommendation"
    PART_OF_WORKFLOW = "Part Of Workflow"
    PAID_BY = "Paid By"
    PAID_TO = "Paid To"
    OPERATES_IN = "Operates In"
    SERVES = "Serves"
    RELATED_TO = "Related To"


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    node_type: NodeType
    external_id: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)
    source_type: str = ""
    source_id: str | None = None
    confidence_score: int = 50
    active: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


@dataclass(frozen=True)
class GraphEdge:
    edge_id: str
    from_node_id: str
    to_node_id: str
    edge_type: EdgeType
    weight: float = 1.0
    confidence_score: int = 50
    properties: dict[str, Any] = field(default_factory=dict)
    evidence_summary: str = ""
    source_type: str = ""
    source_id: str | None = None
    active: bool = True
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


@dataclass(frozen=True)
class GraphPath:
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    total_weight: float
    minimum_confidence: int
    explanation: str


@dataclass(frozen=True)
class GraphMatch:
    buyer: GraphNode
    product: GraphNode
    supplier: GraphNode
    score: int
    local_supply: bool
    evidence: tuple[str, ...]
    gaps: tuple[str, ...]


@dataclass
class KnowledgeGraphBuildReport:
    nodes_created: int
    nodes_updated: int
    edges_created: int
    edges_updated: int
    warnings: list[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


def create_knowledge_graph_tables() -> None:
    """Create graph storage tables and indexes."""

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL UNIQUE,
                node_type TEXT NOT NULL,
                external_id TEXT NOT NULL,
                name TEXT NOT NULL,
                properties_json TEXT NOT NULL DEFAULT '{}',
                source_type TEXT,
                source_id TEXT,
                confidence_score INTEGER NOT NULL DEFAULT 50,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(node_type, external_id)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                edge_id TEXT NOT NULL UNIQUE,
                from_node_id TEXT NOT NULL,
                to_node_id TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                confidence_score INTEGER NOT NULL DEFAULT 50,
                properties_json TEXT NOT NULL DEFAULT '{}',
                evidence_summary TEXT,
                source_type TEXT,
                source_id TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(
                    from_node_id,
                    to_node_id,
                    edge_type,
                    source_type,
                    source_id
                ),
                FOREIGN KEY (from_node_id)
                    REFERENCES knowledge_graph_nodes(node_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (to_node_id)
                    REFERENCES knowledge_graph_nodes(node_id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_graph_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                actor TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_graph_node_type
            ON knowledge_graph_nodes(node_type, active)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_graph_node_name
            ON knowledge_graph_nodes(name)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_graph_edge_from
            ON knowledge_graph_edges(from_node_id, edge_type, active)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_graph_edge_to
            ON knowledge_graph_edges(to_node_id, edge_type, active)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_graph_edge_confidence
            ON knowledge_graph_edges(edge_type, confidence_score DESC)
            """
        )

        connection.commit()


class EnterpriseKnowledgeGraphEngine:
    """Build, persist and query enterprise trade relationships."""

    def __init__(self) -> None:
        create_knowledge_graph_tables()

    def rebuild_from_platform(
        self,
        *,
        actor: str = "Knowledge Graph Engine",
        limit_per_domain: int = 1000,
    ) -> KnowledgeGraphBuildReport:
        """
        Rebuild graph relationships from the current platform context.

        Existing nodes and edges are updated in place rather than duplicated.
        """

        context = build_ai_context(
            limit_per_domain=limit_per_domain
        )

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        warnings: list[str] = []

        product_nodes = self._product_nodes(
            context.get("products", [])
        )
        nodes.extend(product_nodes)

        supplier_nodes, supplier_edges = self._supplier_graph(
            context.get("suppliers", []),
            product_nodes,
        )
        nodes.extend(supplier_nodes)
        edges.extend(supplier_edges)

        buyer_nodes, buyer_edges = self._buyer_graph(
            context.get("customers", []),
            product_nodes,
        )
        nodes.extend(buyer_nodes)
        edges.extend(buyer_edges)

        opportunity_nodes, opportunity_edges = self._opportunity_graph(
            context.get("opportunities", []),
            buyer_nodes,
            product_nodes,
        )
        nodes.extend(opportunity_nodes)
        edges.extend(opportunity_edges)

        quote_nodes, quote_edges = self._quotation_graph(
            context.get("supplier_quotes", []),
            supplier_nodes,
            product_nodes,
        )
        nodes.extend(quote_nodes)
        edges.extend(quote_edges)

        landed_nodes, landed_edges = self._landed_cost_graph(
            context.get("landed_costs", []),
            supplier_nodes,
            product_nodes,
        )
        nodes.extend(landed_nodes)
        edges.extend(landed_edges)

        shipment_nodes, shipment_edges = self._shipment_graph(
            context.get("shipments", []),
            supplier_nodes,
            product_nodes,
        )
        nodes.extend(shipment_nodes)
        edges.extend(shipment_edges)

        inventory_nodes, inventory_edges = self._inventory_graph(
            context.get("inventory", []),
            product_nodes,
        )
        nodes.extend(inventory_nodes)
        edges.extend(inventory_edges)

        nodes = self._deduplicate_nodes(nodes)
        edges = self._deduplicate_edges(edges)

        nodes_created = 0
        nodes_updated = 0
        edges_created = 0
        edges_updated = 0

        for node in nodes:
            created = self.upsert_node(
                node,
                actor=actor,
            )
            if created:
                nodes_created += 1
            else:
                nodes_updated += 1

        for edge in edges:
            if not self.get_node(edge.from_node_id):
                warnings.append(
                    f"Missing edge source node: {edge.from_node_id}"
                )
                continue

            if not self.get_node(edge.to_node_id):
                warnings.append(
                    f"Missing edge destination node: {edge.to_node_id}"
                )
                continue

            created = self.upsert_edge(
                edge,
                actor=actor,
            )
            if created:
                edges_created += 1
            else:
                edges_updated += 1

        self._audit(
            action="Knowledge Graph Rebuilt",
            entity_type="Graph",
            entity_id="enterprise",
            actor=actor,
            details={
                "nodes_created": nodes_created,
                "nodes_updated": nodes_updated,
                "edges_created": edges_created,
                "edges_updated": edges_updated,
                "warnings": warnings,
            },
        )

        return KnowledgeGraphBuildReport(
            nodes_created=nodes_created,
            nodes_updated=nodes_updated,
            edges_created=edges_created,
            edges_updated=edges_updated,
            warnings=warnings,
        )

    def upsert_node(
        self,
        node: GraphNode,
        *,
        actor: str = "System",
    ) -> bool:
        """Create or update a graph node. Returns True when created."""

        existing = self.get_node(node.node_id)
        now = _now()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_graph_nodes (
                    node_id,
                    node_type,
                    external_id,
                    name,
                    properties_json,
                    source_type,
                    source_id,
                    confidence_score,
                    active,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_type, external_id)
                DO UPDATE SET
                    node_id = excluded.node_id,
                    name = excluded.name,
                    properties_json = excluded.properties_json,
                    source_type = excluded.source_type,
                    source_id = excluded.source_id,
                    confidence_score = excluded.confidence_score,
                    active = excluded.active,
                    updated_at = excluded.updated_at
                """,
                (
                    node.node_id,
                    node.node_type.value,
                    node.external_id,
                    node.name,
                    json.dumps(
                        node.properties,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    node.source_type,
                    node.source_id,
                    node.confidence_score,
                    1 if node.active else 0,
                    node.created_at,
                    now,
                ),
            )
            connection.commit()

        self._audit(
            action=(
                "Graph Node Created"
                if existing is None
                else "Graph Node Updated"
            ),
            entity_type="Node",
            entity_id=node.node_id,
            actor=actor,
            details={
                "node_type": node.node_type.value,
                "name": node.name,
                "confidence_score": node.confidence_score,
            },
        )

        return existing is None

    def upsert_edge(
        self,
        edge: GraphEdge,
        *,
        actor: str = "System",
    ) -> bool:
        """Create or update a graph edge. Returns True when created."""

        existing = self.get_edge(edge.edge_id)
        now = _now()

        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_graph_edges (
                    edge_id,
                    from_node_id,
                    to_node_id,
                    edge_type,
                    weight,
                    confidence_score,
                    properties_json,
                    evidence_summary,
                    source_type,
                    source_id,
                    active,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(
                    from_node_id,
                    to_node_id,
                    edge_type,
                    source_type,
                    source_id
                )
                DO UPDATE SET
                    edge_id = excluded.edge_id,
                    weight = excluded.weight,
                    confidence_score = excluded.confidence_score,
                    properties_json = excluded.properties_json,
                    evidence_summary = excluded.evidence_summary,
                    active = excluded.active,
                    updated_at = excluded.updated_at
                """,
                (
                    edge.edge_id,
                    edge.from_node_id,
                    edge.to_node_id,
                    edge.edge_type.value,
                    edge.weight,
                    edge.confidence_score,
                    json.dumps(
                        edge.properties,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    edge.evidence_summary,
                    edge.source_type,
                    edge.source_id,
                    1 if edge.active else 0,
                    edge.created_at,
                    now,
                ),
            )
            connection.commit()

        self._audit(
            action=(
                "Graph Edge Created"
                if existing is None
                else "Graph Edge Updated"
            ),
            entity_type="Edge",
            entity_id=edge.edge_id,
            actor=actor,
            details={
                "edge_type": edge.edge_type.value,
                "from_node_id": edge.from_node_id,
                "to_node_id": edge.to_node_id,
                "confidence_score": edge.confidence_score,
            },
        )

        return existing is None

    def get_node(
        self,
        node_id: str,
    ) -> GraphNode | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM knowledge_graph_nodes
                WHERE node_id = ?
                LIMIT 1
                """,
                (node_id,),
            ).fetchone()

        return _row_to_node(row) if row else None

    def get_edge(
        self,
        edge_id: str,
    ) -> GraphEdge | None:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM knowledge_graph_edges
                WHERE edge_id = ?
                LIMIT 1
                """,
                (edge_id,),
            ).fetchone()

        return _row_to_edge(row) if row else None

    def search_nodes(
        self,
        search_text: str,
        *,
        node_types: Iterable[NodeType] | None = None,
        active_only: bool = True,
        limit: int = 100,
    ) -> list[GraphNode]:
        conditions = ["1 = 1"]
        values: list[Any] = []

        if search_text.strip():
            pattern = f"%{search_text.strip()}%"
            conditions.append(
                """
                (
                    name LIKE ?
                    OR external_id LIKE ?
                    OR properties_json LIKE ?
                )
                """
            )
            values.extend(
                [
                    pattern,
                    pattern,
                    pattern,
                ]
            )

        if node_types:
            types = [
                item.value
                for item in node_types
            ]
            placeholders = ",".join("?" for _ in types)
            conditions.append(
                f"node_type IN ({placeholders})"
            )
            values.extend(types)

        if active_only:
            conditions.append("active = 1")

        values.append(max(1, min(limit, 1000)))

        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM knowledge_graph_nodes
                WHERE {' AND '.join(conditions)}
                ORDER BY confidence_score DESC, name ASC
                LIMIT ?
                """,
                values,
            ).fetchall()

        return [
            _row_to_node(row)
            for row in rows
        ]

    def neighbours(
        self,
        node_id: str,
        *,
        edge_types: Iterable[EdgeType] | None = None,
        direction: str = "both",
        minimum_confidence: int = 0,
        limit: int = 100,
    ) -> list[tuple[GraphEdge, GraphNode]]:
        """Return adjacent edges and nodes."""

        if direction not in {
            "outgoing",
            "incoming",
            "both",
        }:
            raise ValueError(
                "direction must be outgoing, incoming or both."
            )

        clauses = []
        values: list[Any] = []

        if direction in {"outgoing", "both"}:
            clauses.append("e.from_node_id = ?")
            values.append(node_id)

        if direction in {"incoming", "both"}:
            clauses.append("e.to_node_id = ?")
            values.append(node_id)

        conditions = [
            f"({' OR '.join(clauses)})",
            "e.active = 1",
            "n.active = 1",
            "e.confidence_score >= ?",
        ]
        values.append(minimum_confidence)

        if edge_types:
            types = [
                item.value
                for item in edge_types
            ]
            placeholders = ",".join("?" for _ in types)
            conditions.append(
                f"e.edge_type IN ({placeholders})"
            )
            values.extend(types)

        values.append(max(1, min(limit, 1000)))

        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    e.*,
                    n.node_id AS related_node_id,
                    n.node_type AS related_node_type,
                    n.external_id AS related_external_id,
                    n.name AS related_name,
                    n.properties_json AS related_properties_json,
                    n.source_type AS related_source_type,
                    n.source_id AS related_source_id,
                    n.confidence_score AS related_confidence_score,
                    n.active AS related_active,
                    n.created_at AS related_created_at,
                    n.updated_at AS related_updated_at
                FROM knowledge_graph_edges e
                INNER JOIN knowledge_graph_nodes n
                    ON n.node_id = CASE
                        WHEN e.from_node_id = ?
                        THEN e.to_node_id
                        ELSE e.from_node_id
                    END
                WHERE {' AND '.join(conditions)}
                ORDER BY
                    e.confidence_score DESC,
                    e.weight DESC
                LIMIT ?
                """,
                [
                    node_id,
                    *values,
                ],
            ).fetchall()

        results = []

        for row in rows:
            edge = _row_to_edge(row)
            node = GraphNode(
                node_id=row["related_node_id"],
                node_type=NodeType(
                    row["related_node_type"]
                ),
                external_id=row["related_external_id"],
                name=row["related_name"],
                properties=_decode_json(
                    row["related_properties_json"],
                    {},
                ),
                source_type=row["related_source_type"] or "",
                source_id=row["related_source_id"],
                confidence_score=int(
                    row["related_confidence_score"]
                ),
                active=bool(row["related_active"]),
                created_at=row["related_created_at"],
                updated_at=row["related_updated_at"],
            )
            results.append((edge, node))

        return results

    def find_paths(
        self,
        from_node_id: str,
        to_node_id: str,
        *,
        maximum_depth: int = 4,
        minimum_confidence: int = 50,
        maximum_paths: int = 10,
    ) -> list[GraphPath]:
        """
        Find simple relationship paths using bounded breadth-first search.
        """

        if maximum_depth < 1:
            raise ValueError(
                "maximum_depth must be at least 1."
            )

        start = self.get_node(from_node_id)
        target = self.get_node(to_node_id)

        if start is None or target is None:
            return []

        queue: list[
            tuple[
                GraphNode,
                list[GraphNode],
                list[GraphEdge],
            ]
        ] = [
            (
                start,
                [start],
                [],
            )
        ]
        paths: list[GraphPath] = []

        while queue and len(paths) < maximum_paths:
            current, path_nodes, path_edges = queue.pop(0)

            if len(path_edges) >= maximum_depth:
                continue

            for edge, neighbour in self.neighbours(
                current.node_id,
                direction="both",
                minimum_confidence=minimum_confidence,
                limit=500,
            ):
                if any(
                    node.node_id == neighbour.node_id
                    for node in path_nodes
                ):
                    continue

                next_nodes = [
                    *path_nodes,
                    neighbour,
                ]
                next_edges = [
                    *path_edges,
                    edge,
                ]

                if neighbour.node_id == to_node_id:
                    paths.append(
                        GraphPath(
                            nodes=tuple(next_nodes),
                            edges=tuple(next_edges),
                            total_weight=round(
                                sum(
                                    item.weight
                                    for item in next_edges
                                ),
                                2,
                            ),
                            minimum_confidence=min(
                                item.confidence_score
                                for item in next_edges
                            ),
                            explanation=self._path_explanation(
                                next_nodes,
                                next_edges,
                            ),
                        )
                    )
                    continue

                queue.append(
                    (
                        neighbour,
                        next_nodes,
                        next_edges,
                    )
                )

        paths.sort(
            key=lambda item: (
                -item.minimum_confidence,
                -item.total_weight,
                len(item.edges),
            )
        )

        return paths

    def match_buyers_to_suppliers(
        self,
        *,
        product_name: str,
        destination_country: str = "Australia",
        minimum_confidence: int = 50,
        limit: int = 20,
    ) -> list[GraphMatch]:
        """
        Match buyer demand to local and international suppliers.
        """

        products = [
            item
            for item in self.search_nodes(
                product_name,
                node_types=[NodeType.PRODUCT],
                active_only=True,
                limit=20,
            )
            if item.confidence_score >= minimum_confidence
        ]

        if not products:
            return []

        product_ids = {
            item.node_id
            for item in products
        }

        buyers = self.search_nodes(
            "",
            node_types=[NodeType.BUYER],
            active_only=True,
            limit=500,
        )
        suppliers = self.search_nodes(
            "",
            node_types=[NodeType.SUPPLIER],
            active_only=True,
            limit=500,
        )

        buyer_product_edges = self._edges_for_nodes(
            buyers,
            EdgeType.INTERESTED_IN,
            product_ids,
            minimum_confidence,
        )
        supplier_product_edges = self._edges_for_nodes(
            suppliers,
            EdgeType.SUPPLIES,
            product_ids,
            minimum_confidence,
        )

        results: list[GraphMatch] = []

        for buyer, buyer_edge, product in buyer_product_edges:
            for supplier, supplier_edge, supplied_product in supplier_product_edges:
                if product.node_id != supplied_product.node_id:
                    continue

                supplier_country = str(
                    supplier.properties.get("country")
                    or ""
                )
                local = (
                    supplier_country.strip().lower()
                    == destination_country.strip().lower()
                )

                score = round(
                    buyer_edge.confidence_score * 0.30
                    + supplier_edge.confidence_score * 0.35
                    + buyer.confidence_score * 0.15
                    + supplier.confidence_score * 0.20
                    + (5 if local else 0)
                )
                score = max(0, min(100, score))

                gaps = []

                if supplier.properties.get(
                    "verification_status"
                ) != "Verified":
                    gaps.append(
                        "Supplier verification is incomplete."
                    )

                if not supplier.properties.get(
                    "certificates"
                ):
                    gaps.append(
                        "Required certificates are not recorded."
                    )

                if not buyer.properties.get(
                    "credit_status"
                ):
                    gaps.append(
                        "Buyer credit status is not recorded."
                    )

                results.append(
                    GraphMatch(
                        buyer=buyer,
                        product=product,
                        supplier=supplier,
                        score=score,
                        local_supply=local,
                        evidence=(
                            buyer_edge.evidence_summary,
                            supplier_edge.evidence_summary,
                        ),
                        gaps=tuple(gaps),
                    )
                )

        results.sort(
            key=lambda item: (
                -item.score,
                not item.local_supply,
                item.supplier.name.lower(),
            )
        )

        return results[:limit]

    def identify_supply_demand_gaps(
        self,
        *,
        destination_country: str = "Australia",
        minimum_confidence: int = 50,
    ) -> list[dict[str, Any]]:
        """Identify products with recorded demand but inadequate supply."""

        products = self.search_nodes(
            "",
            node_types=[NodeType.PRODUCT],
            active_only=True,
            limit=1000,
        )

        results = []

        for product in products:
            demand_edges = self._incoming_edges(
                product.node_id,
                EdgeType.INTERESTED_IN,
                minimum_confidence,
            )
            supply_edges = self._incoming_edges(
                product.node_id,
                EdgeType.SUPPLIES,
                minimum_confidence,
            )

            verified_supply = []

            for edge in supply_edges:
                supplier = self.get_node(
                    edge.from_node_id
                )
                if (
                    supplier
                    and supplier.properties.get(
                        "verification_status"
                    ) == "Verified"
                ):
                    verified_supply.append(
                        supplier
                    )

            local_verified = [
                supplier
                for supplier in verified_supply
                if str(
                    supplier.properties.get("country")
                    or ""
                ).strip().lower()
                == destination_country.strip().lower()
            ]

            if demand_edges and not verified_supply:
                gap_level = "Critical"
            elif len(demand_edges) > len(verified_supply) * 3:
                gap_level = "High"
            elif demand_edges and not local_verified:
                gap_level = "Medium"
            else:
                continue

            results.append(
                {
                    "product_node_id": product.node_id,
                    "product": product.name,
                    "demand_relationships": len(demand_edges),
                    "verified_supply_relationships": len(
                        verified_supply
                    ),
                    "local_verified_suppliers": len(
                        local_verified
                    ),
                    "gap_level": gap_level,
                    "recommended_action": (
                        "Run local and international supplier discovery, "
                        "then verify capacity, certificates, quotations and "
                        "landed cost."
                    ),
                }
            )

        severity_rank = {
            "Critical": 3,
            "High": 2,
            "Medium": 1,
        }

        results.sort(
            key=lambda item: (
                -severity_rank[item["gap_level"]],
                -item["demand_relationships"],
                item["product"].lower(),
            )
        )

        return results

    @staticmethod
    def _product_nodes(
        products: list[dict[str, Any]],
    ) -> list[GraphNode]:
        nodes = []

        for item in products:
            name = str(
                item.get("name")
                or item.get("product_name")
                or ""
            ).strip()

            if not name:
                continue

            external_id = str(
                item.get("id")
                or item.get("sku")
                or name.lower()
            )

            nodes.append(
                _node(
                    NodeType.PRODUCT,
                    external_id,
                    name,
                    properties={
                        "sku": item.get("sku"),
                        "category": item.get("category"),
                        "unit": item.get("unit"),
                        "brand": item.get("brand"),
                        "origin_country": item.get(
                            "origin_country"
                        ),
                        "status": item.get("status"),
                    },
                    source_type="Product",
                    source_id=_optional_string(
                        item.get("id")
                    ),
                    confidence_score=85,
                )
            )

        return nodes

    @staticmethod
    def _supplier_graph(
        suppliers: list[dict[str, Any]],
        product_nodes: list[GraphNode],
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        for item in suppliers:
            name = str(
                item.get("company_name") or ""
            ).strip()

            if not name:
                continue

            external_id = str(
                item.get("id")
                or name.lower()
            )
            verification = str(
                item.get("verification_status")
                or "Unverified"
            )

            supplier_node = _node(
                NodeType.SUPPLIER,
                external_id,
                name,
                properties={
                    "country": item.get("country"),
                    "city": item.get("city"),
                    "category": item.get("category"),
                    "verification_status": verification,
                    "rating": item.get("rating"),
                    "email": item.get("email"),
                    "website": item.get("website"),
                    "certificates": item.get(
                        "certificates"
                    ),
                },
                source_type="Supplier",
                source_id=_optional_string(
                    item.get("id")
                ),
                confidence_score=(
                    90 if verification == "Verified" else 55
                ),
            )
            nodes.append(supplier_node)

            country = str(
                item.get("country") or ""
            ).strip()

            if country:
                country_node = _node(
                    NodeType.COUNTRY,
                    country.lower(),
                    country,
                    source_type="Supplier",
                    source_id=_optional_string(
                        item.get("id")
                    ),
                    confidence_score=80,
                )
                nodes.append(country_node)
                edges.append(
                    _edge(
                        supplier_node,
                        country_node,
                        EdgeType.LOCATED_IN,
                        confidence_score=80,
                        evidence_summary=(
                            f"Supplier country recorded as {country}."
                        ),
                        source_type="Supplier",
                        source_id=_optional_string(
                            item.get("id")
                        ),
                    )
                )

            text = " ".join(
                str(item.get(key) or "")
                for key in (
                    "category",
                    "products",
                    "products_services",
                    "notes",
                )
            ).lower()

            for product_node in product_nodes:
                if _matches_name(
                    product_node.name,
                    text,
                ):
                    edges.append(
                        _edge(
                            supplier_node,
                            product_node,
                            EdgeType.SUPPLIES,
                            weight=1.0,
                            confidence_score=(
                                85
                                if verification == "Verified"
                                else 60
                            ),
                            evidence_summary=(
                                f"Supplier record indicates capability for "
                                f"{product_node.name}."
                            ),
                            source_type="Supplier",
                            source_id=_optional_string(
                                item.get("id")
                            ),
                        )
                    )

        return nodes, edges

    @staticmethod
    def _buyer_graph(
        customers: list[dict[str, Any]],
        product_nodes: list[GraphNode],
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        for item in customers:
            name = str(
                item.get("company_name") or ""
            ).strip()

            if not name:
                continue

            external_id = str(
                item.get("id")
                or name.lower()
            )

            lead_status = str(
                item.get("lead_status") or ""
            )

            buyer_node = _node(
                NodeType.BUYER,
                external_id,
                name,
                properties={
                    "country": item.get("country"),
                    "city": item.get("city"),
                    "lead_status": lead_status,
                    "credit_status": item.get(
                        "credit_status"
                    ),
                    "estimated_demand": item.get(
                        "estimated_demand"
                    ),
                    "products_of_interest": item.get(
                        "products_of_interest"
                    ),
                },
                source_type="Customer",
                source_id=_optional_string(
                    item.get("id")
                ),
                confidence_score={
                    "Prospect": 45,
                    "Contacted": 55,
                    "Qualified": 70,
                    "Quotation Sent": 75,
                    "Accepted": 85,
                    "Customer": 90,
                }.get(lead_status, 50),
            )
            nodes.append(buyer_node)

            country = str(
                item.get("country") or ""
            ).strip()

            if country:
                country_node = _node(
                    NodeType.COUNTRY,
                    country.lower(),
                    country,
                    source_type="Customer",
                    source_id=_optional_string(
                        item.get("id")
                    ),
                    confidence_score=80,
                )
                nodes.append(country_node)
                edges.append(
                    _edge(
                        buyer_node,
                        country_node,
                        EdgeType.LOCATED_IN,
                        confidence_score=80,
                        evidence_summary=(
                            f"Buyer country recorded as {country}."
                        ),
                        source_type="Customer",
                        source_id=_optional_string(
                            item.get("id")
                        ),
                    )
                )

            interests = str(
                item.get("products_of_interest")
                or ""
            ).lower()

            for product_node in product_nodes:
                if _matches_name(
                    product_node.name,
                    interests,
                ):
                    edges.append(
                        _edge(
                            buyer_node,
                            product_node,
                            EdgeType.INTERESTED_IN,
                            weight=1.0,
                            confidence_score=buyer_node.confidence_score,
                            evidence_summary=(
                                f"Buyer record lists interest in "
                                f"{product_node.name}."
                            ),
                            source_type="Customer",
                            source_id=_optional_string(
                                item.get("id")
                            ),
                        )
                    )

        return nodes, edges

    @staticmethod
    def _opportunity_graph(
        opportunities: list[dict[str, Any]],
        buyer_nodes: list[GraphNode],
        product_nodes: list[GraphNode],
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        buyers_by_name = {
            item.name.strip().lower(): item
            for item in buyer_nodes
        }

        for item in opportunities:
            title = str(
                item.get("title") or ""
            ).strip()

            if not title:
                continue

            external_id = str(
                item.get("id")
                or title.lower()
            )
            confidence = int(
                _number(
                    item.get("confidence_score")
                )
            )
            opportunity_node = _node(
                NodeType.OPPORTUNITY,
                external_id,
                title,
                properties={
                    "product": item.get("product"),
                    "buyer_company": item.get(
                        "buyer_company"
                    ),
                    "country": item.get("country"),
                    "urgency": item.get("urgency"),
                    "demand_score": item.get(
                        "demand_score"
                    ),
                    "competition_score": item.get(
                        "competition_score"
                    ),
                    "expected_margin": item.get(
                        "expected_margin"
                    ),
                    "status": item.get("status"),
                },
                source_type="Market Opportunity",
                source_id=_optional_string(
                    item.get("id")
                ),
                confidence_score=max(
                    30,
                    min(100, confidence or 50),
                ),
            )
            nodes.append(opportunity_node)

            product_name = str(
                item.get("product") or ""
            )
            for product_node in product_nodes:
                if _matches_name(
                    product_node.name,
                    product_name,
                ):
                    edges.append(
                        _edge(
                            opportunity_node,
                            product_node,
                            EdgeType.REQUIRES,
                            confidence_score=(
                                opportunity_node.confidence_score
                            ),
                            evidence_summary=(
                                f"Opportunity requires "
                                f"{product_node.name}."
                            ),
                            source_type="Market Opportunity",
                            source_id=_optional_string(
                                item.get("id")
                            ),
                        )
                    )

            buyer_name = str(
                item.get("buyer_company") or ""
            ).strip().lower()

            if buyer_name in buyers_by_name:
                edges.append(
                    _edge(
                        buyers_by_name[buyer_name],
                        opportunity_node,
                        EdgeType.LINKED_TO,
                        confidence_score=(
                            opportunity_node.confidence_score
                        ),
                        evidence_summary=(
                            "Opportunity is linked to the recorded buyer."
                        ),
                        source_type="Market Opportunity",
                        source_id=_optional_string(
                            item.get("id")
                        ),
                    )
                )

        return nodes, edges

    @staticmethod
    def _quotation_graph(
        quotes: list[dict[str, Any]],
        supplier_nodes: list[GraphNode],
        product_nodes: list[GraphNode],
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        suppliers_by_name = {
            item.name.strip().lower(): item
            for item in supplier_nodes
        }

        for item in quotes:
            quote_id = str(
                item.get("id")
                or uuid4().hex
            )
            supplier_name = str(
                item.get("supplier_name") or ""
            ).strip()
            title = (
                f"Quotation {quote_id}"
                + (
                    f" — {supplier_name}"
                    if supplier_name
                    else ""
                )
            )

            quote_node = _node(
                NodeType.QUOTATION,
                quote_id,
                title,
                properties={
                    "unit_price": item.get("unit_price"),
                    "currency": item.get("currency"),
                    "incoterm": item.get("incoterm"),
                    "lead_time_days": item.get(
                        "lead_time_days"
                    ),
                    "valid_until": item.get(
                        "quotation_valid_until"
                    ),
                    "risk_score": item.get(
                        "risk_score"
                    ),
                    "certificates": item.get(
                        "certificates"
                    ),
                },
                source_type="Supplier Quotation",
                source_id=_optional_string(
                    item.get("id")
                ),
                confidence_score=70,
            )
            nodes.append(quote_node)

            supplier = suppliers_by_name.get(
                supplier_name.lower()
            )

            if supplier:
                edges.append(
                    _edge(
                        supplier,
                        quote_node,
                        EdgeType.HAS_QUOTATION,
                        confidence_score=75,
                        evidence_summary=(
                            f"Quotation is recorded for "
                            f"{supplier.name}."
                        ),
                        source_type="Supplier Quotation",
                        source_id=_optional_string(
                            item.get("id")
                        ),
                    )
                )

            product_text = " ".join(
                str(item.get(key) or "")
                for key in (
                    "product_name",
                    "packaging",
                    "notes",
                )
            )

            for product_node in product_nodes:
                if _matches_name(
                    product_node.name,
                    product_text,
                ):
                    edges.append(
                        _edge(
                            quote_node,
                            product_node,
                            EdgeType.QUOTES_FOR,
                            confidence_score=65,
                            evidence_summary=(
                                f"Quotation appears related to "
                                f"{product_node.name}."
                            ),
                            source_type="Supplier Quotation",
                            source_id=_optional_string(
                                item.get("id")
                            ),
                        )
                    )

        return nodes, edges

    @staticmethod
    def _landed_cost_graph(
        landed_costs: list[dict[str, Any]],
        supplier_nodes: list[GraphNode],
        product_nodes: list[GraphNode],
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        suppliers_by_name = {
            item.name.strip().lower(): item
            for item in supplier_nodes
        }

        for item in landed_costs:
            record_id = str(
                item.get("id")
                or uuid4().hex
            )
            name = str(
                item.get("name")
                or f"Landed Cost {record_id}"
            )

            landed_node = _node(
                NodeType.LANDED_COST,
                record_id,
                name,
                properties={
                    "product_name": item.get(
                        "product_name"
                    ),
                    "supplier_name": item.get(
                        "supplier_name"
                    ),
                    "landed_cost_per_unit": item.get(
                        "landed_cost_per_unit"
                    ),
                    "gross_margin_percent": item.get(
                        "gross_margin_percent"
                    ),
                    "gross_profit": item.get(
                        "gross_profit"
                    ),
                    "reporting_currency": item.get(
                        "reporting_currency"
                    ),
                    "destination": item.get(
                        "destination"
                    ),
                },
                source_type="Landed Cost",
                source_id=_optional_string(
                    item.get("id")
                ),
                confidence_score=80,
            )
            nodes.append(landed_node)

            supplier_name = str(
                item.get("supplier_name") or ""
            ).strip().lower()
            supplier = suppliers_by_name.get(
                supplier_name
            )

            if supplier:
                edges.append(
                    _edge(
                        landed_node,
                        supplier,
                        EdgeType.CALCULATED_FOR,
                        confidence_score=80,
                        evidence_summary=(
                            "Landed-cost record is linked to supplier."
                        ),
                        source_type="Landed Cost",
                        source_id=_optional_string(
                            item.get("id")
                        ),
                    )
                )

            product_name = str(
                item.get("product_name") or ""
            )

            for product_node in product_nodes:
                if _matches_name(
                    product_node.name,
                    product_name,
                ):
                    edges.append(
                        _edge(
                            landed_node,
                            product_node,
                            EdgeType.CALCULATED_FOR,
                            confidence_score=85,
                            evidence_summary=(
                                f"Landed-cost record calculated for "
                                f"{product_node.name}."
                            ),
                            source_type="Landed Cost",
                            source_id=_optional_string(
                                item.get("id")
                            ),
                        )
                    )

        return nodes, edges

    @staticmethod
    def _shipment_graph(
        shipments: list[dict[str, Any]],
        supplier_nodes: list[GraphNode],
        product_nodes: list[GraphNode],
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        suppliers_by_name = {
            item.name.strip().lower(): item
            for item in supplier_nodes
        }

        for item in shipments:
            record_id = str(
                item.get("id")
                or item.get("shipment_number")
                or uuid4().hex
            )
            name = str(
                item.get("shipment_number")
                or item.get("shipment_reference")
                or f"Shipment {record_id}"
            )

            shipment_node = _node(
                NodeType.SHIPMENT,
                record_id,
                name,
                properties={
                    "status": (
                        item.get("shipment_status")
                        or item.get("status")
                    ),
                    "origin_port": item.get(
                        "origin_port"
                    ),
                    "destination_port": item.get(
                        "destination_port"
                    ),
                    "shipping_line": item.get(
                        "shipping_line"
                    ),
                    "eta": item.get("eta"),
                    "delay_days": item.get(
                        "delay_days"
                    ),
                    "delay_reason": item.get(
                        "delay_reason"
                    ),
                },
                source_type="Shipment",
                source_id=_optional_string(
                    item.get("id")
                ),
                confidence_score=85,
            )
            nodes.append(shipment_node)

            supplier_name = str(
                item.get("supplier_name") or ""
            ).strip().lower()
            supplier = suppliers_by_name.get(
                supplier_name
            )

            if supplier:
                edges.append(
                    _edge(
                        shipment_node,
                        supplier,
                        EdgeType.FULFILLS,
                        confidence_score=80,
                        evidence_summary=(
                            "Shipment is linked to supplier."
                        ),
                        source_type="Shipment",
                        source_id=_optional_string(
                            item.get("id")
                        ),
                    )
                )

            product_name = str(
                item.get("product_name") or ""
            )

            for product_node in product_nodes:
                if _matches_name(
                    product_node.name,
                    product_name,
                ):
                    edges.append(
                        _edge(
                            shipment_node,
                            product_node,
                            EdgeType.RELATED_TO,
                            confidence_score=80,
                            evidence_summary=(
                                f"Shipment contains "
                                f"{product_node.name}."
                            ),
                            source_type="Shipment",
                            source_id=_optional_string(
                                item.get("id")
                            ),
                        )
                    )

            origin = str(
                item.get("origin_port")
                or item.get("origin_country")
                or ""
            ).strip()
            destination = str(
                item.get("destination_port")
                or item.get("destination_country")
                or ""
            ).strip()

            if origin and destination:
                route_name = f"{origin} → {destination}"
                route_node = _node(
                    NodeType.ROUTE,
                    route_name.lower(),
                    route_name,
                    properties={
                        "origin": origin,
                        "destination": destination,
                    },
                    source_type="Shipment",
                    source_id=_optional_string(
                        item.get("id")
                    ),
                    confidence_score=80,
                )
                nodes.append(route_node)
                edges.append(
                    _edge(
                        shipment_node,
                        route_node,
                        EdgeType.USES_ROUTE,
                        confidence_score=80,
                        evidence_summary=(
                            f"Shipment uses route {route_name}."
                        ),
                        source_type="Shipment",
                        source_id=_optional_string(
                            item.get("id")
                        ),
                    )
                )

            shipping_line = str(
                item.get("shipping_line") or ""
            ).strip()

            if shipping_line:
                shipping_node = _node(
                    NodeType.SHIPPING_LINE,
                    shipping_line.lower(),
                    shipping_line,
                    source_type="Shipment",
                    source_id=_optional_string(
                        item.get("id")
                    ),
                    confidence_score=75,
                )
                nodes.append(shipping_node)
                edges.append(
                    _edge(
                        shipment_node,
                        shipping_node,
                        EdgeType.SHIPPED_BY,
                        confidence_score=75,
                        evidence_summary=(
                            f"Shipment is handled by {shipping_line}."
                        ),
                        source_type="Shipment",
                        source_id=_optional_string(
                            item.get("id")
                        ),
                    )
                )

        return nodes, edges

    @staticmethod
    def _inventory_graph(
        inventory: list[dict[str, Any]],
        product_nodes: list[GraphNode],
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        for item in inventory:
            warehouse_name = str(
                item.get("warehouse_name")
                or item.get("warehouse")
                or ""
            ).strip()

            if not warehouse_name:
                continue

            warehouse_node = _node(
                NodeType.WAREHOUSE,
                warehouse_name.lower(),
                warehouse_name,
                properties={
                    "location": item.get("location"),
                    "quantity_on_hand": item.get(
                        "quantity_on_hand"
                    ),
                    "quantity_reserved": item.get(
                        "quantity_reserved"
                    ),
                    "reorder_level": item.get(
                        "reorder_level"
                    ),
                },
                source_type="Inventory",
                source_id=_optional_string(
                    item.get("id")
                ),
                confidence_score=75,
            )
            nodes.append(warehouse_node)

            product_name = str(
                item.get("product_name")
                or item.get("sku")
                or ""
            )

            for product_node in product_nodes:
                if _matches_name(
                    product_node.name,
                    product_name,
                ):
                    edges.append(
                        _edge(
                            product_node,
                            warehouse_node,
                            EdgeType.STORED_AT,
                            confidence_score=75,
                            evidence_summary=(
                                f"{product_node.name} inventory is "
                                f"recorded at {warehouse_name}."
                            ),
                            source_type="Inventory",
                            source_id=_optional_string(
                                item.get("id")
                            ),
                        )
                    )

        return nodes, edges

    def _edges_for_nodes(
        self,
        nodes: list[GraphNode],
        edge_type: EdgeType,
        product_ids: set[str],
        minimum_confidence: int,
    ) -> list[
        tuple[GraphNode, GraphEdge, GraphNode]
    ]:
        results = []

        for node in nodes:
            for edge, neighbour in self.neighbours(
                node.node_id,
                edge_types=[edge_type],
                direction="outgoing",
                minimum_confidence=minimum_confidence,
                limit=500,
            ):
                if neighbour.node_id in product_ids:
                    results.append(
                        (
                            node,
                            edge,
                            neighbour,
                        )
                    )

        return results

    def _incoming_edges(
        self,
        node_id: str,
        edge_type: EdgeType,
        minimum_confidence: int,
    ) -> list[GraphEdge]:
        return [
            edge
            for edge, _ in self.neighbours(
                node_id,
                edge_types=[edge_type],
                direction="incoming",
                minimum_confidence=minimum_confidence,
                limit=1000,
            )
        ]

    @staticmethod
    def _path_explanation(
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> str:
        parts = [nodes[0].name]

        for edge, node in zip(
            edges,
            nodes[1:],
        ):
            parts.append(
                f"--{edge.edge_type.value}--> {node.name}"
            )

        return " ".join(parts)

    @staticmethod
    def _deduplicate_nodes(
        nodes: list[GraphNode],
    ) -> list[GraphNode]:
        unique: dict[
            tuple[str, str],
            GraphNode,
        ] = {}

        for item in nodes:
            key = (
                item.node_type.value,
                item.external_id,
            )
            current = unique.get(key)

            if (
                current is None
                or item.confidence_score
                > current.confidence_score
            ):
                unique[key] = item

        return list(unique.values())

    @staticmethod
    def _deduplicate_edges(
        edges: list[GraphEdge],
    ) -> list[GraphEdge]:
        unique: dict[
            tuple[str, str, str, str, str | None],
            GraphEdge,
        ] = {}

        for item in edges:
            key = (
                item.from_node_id,
                item.to_node_id,
                item.edge_type.value,
                item.source_type,
                item.source_id,
            )
            current = unique.get(key)

            if (
                current is None
                or item.confidence_score
                > current.confidence_score
            ):
                unique[key] = item

        return list(unique.values())

    def _audit(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: str,
        actor: str,
        details: dict[str, Any],
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_graph_audit (
                    action,
                    entity_type,
                    entity_id,
                    details_json,
                    actor,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    action,
                    entity_type,
                    entity_id,
                    json.dumps(
                        details,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    actor,
                    _now(),
                ),
            )
            connection.commit()


def _node(
    node_type: NodeType,
    external_id: str,
    name: str,
    *,
    properties: dict[str, Any] | None = None,
    source_type: str = "",
    source_id: str | None = None,
    confidence_score: int = 50,
) -> GraphNode:
    return GraphNode(
        node_id=_node_id(
            node_type,
            external_id,
        ),
        node_type=node_type,
        external_id=external_id,
        name=name,
        properties=properties or {},
        source_type=source_type,
        source_id=source_id,
        confidence_score=max(
            0,
            min(100, confidence_score),
        ),
    )


def _edge(
    from_node: GraphNode,
    to_node: GraphNode,
    edge_type: EdgeType,
    *,
    weight: float = 1.0,
    confidence_score: int = 50,
    properties: dict[str, Any] | None = None,
    evidence_summary: str = "",
    source_type: str = "",
    source_id: str | None = None,
) -> GraphEdge:
    return GraphEdge(
        edge_id=_edge_id(
            from_node.node_id,
            to_node.node_id,
            edge_type,
            source_type,
            source_id,
        ),
        from_node_id=from_node.node_id,
        to_node_id=to_node.node_id,
        edge_type=edge_type,
        weight=max(0.0, weight),
        confidence_score=max(
            0,
            min(100, confidence_score),
        ),
        properties=properties or {},
        evidence_summary=evidence_summary,
        source_type=source_type,
        source_id=source_id,
    )


def _node_id(
    node_type: NodeType,
    external_id: str,
) -> str:
    raw = (
        f"{node_type.value}|"
        f"{external_id.strip().lower()}"
    )
    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:16].upper()
    return f"NOD-{digest}"


def _edge_id(
    from_node_id: str,
    to_node_id: str,
    edge_type: EdgeType,
    source_type: str,
    source_id: str | None,
) -> str:
    raw = (
        f"{from_node_id}|{to_node_id}|"
        f"{edge_type.value}|{source_type}|"
        f"{source_id or ''}"
    )
    digest = hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:16].upper()
    return f"EDG-{digest}"


def _row_to_node(
    row: Any,
) -> GraphNode:
    return GraphNode(
        node_id=row["node_id"],
        node_type=NodeType(row["node_type"]),
        external_id=row["external_id"],
        name=row["name"],
        properties=_decode_json(
            row["properties_json"],
            {},
        ),
        source_type=row["source_type"] or "",
        source_id=row["source_id"],
        confidence_score=int(
            row["confidence_score"]
        ),
        active=bool(row["active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_edge(
    row: Any,
) -> GraphEdge:
    return GraphEdge(
        edge_id=row["edge_id"],
        from_node_id=row["from_node_id"],
        to_node_id=row["to_node_id"],
        edge_type=EdgeType(row["edge_type"]),
        weight=float(row["weight"]),
        confidence_score=int(
            row["confidence_score"]
        ),
        properties=_decode_json(
            row["properties_json"],
            {},
        ),
        evidence_summary=row["evidence_summary"] or "",
        source_type=row["source_type"] or "",
        source_id=row["source_id"],
        active=bool(row["active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _matches_name(
    name: str,
    text: str,
) -> bool:
    normalized_name = " ".join(
        name.lower()
        .replace("-", " ")
        .replace(",", " ")
        .split()
    )
    normalized_text = " ".join(
        text.lower()
        .replace("-", " ")
        .replace(",", " ")
        .split()
    )

    if not normalized_name or not normalized_text:
        return False

    if normalized_name in normalized_text:
        return True

    tokens = [
        token
        for token in normalized_name.split()
        if len(token) >= 3
    ]

    return bool(
        tokens
        and all(
            token in normalized_text
            for token in tokens
        )
    )


def _decode_json(
    value: str | None,
    default: Any,
) -> Any:
    if not value:
        return default

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _number(
    value: Any,
) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _optional_string(
    value: Any,
) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _now() -> str:
    return datetime.now().isoformat(
        timespec="seconds"
    )


_knowledge_graph_engine = EnterpriseKnowledgeGraphEngine()


def get_knowledge_graph_engine() -> EnterpriseKnowledgeGraphEngine:
    """Return the knowledge graph singleton."""

    return _knowledge_graph_engine


def rebuild_enterprise_knowledge_graph(
    *,
    actor: str = "Knowledge Graph Engine",
    limit_per_domain: int = 1000,
) -> KnowledgeGraphBuildReport:
    """Rebuild the graph from current platform records."""

    return _knowledge_graph_engine.rebuild_from_platform(
        actor=actor,
        limit_per_domain=limit_per_domain,
    )


def match_trade_network(
    *,
    product_name: str,
    destination_country: str = "Australia",
    minimum_confidence: int = 50,
    limit: int = 20,
) -> list[GraphMatch]:
    """Match recorded buyers to local and international suppliers."""

    return _knowledge_graph_engine.match_buyers_to_suppliers(
        product_name=product_name,
        destination_country=destination_country,
        minimum_confidence=minimum_confidence,
        limit=limit,
    )


def identify_trade_gaps(
    *,
    destination_country: str = "Australia",
    minimum_confidence: int = 50,
) -> list[dict[str, Any]]:
    """Identify demand with inadequate verified supply."""

    return _knowledge_graph_engine.identify_supply_demand_gaps(
        destination_country=destination_country,
        minimum_confidence=minimum_confidence,
    )