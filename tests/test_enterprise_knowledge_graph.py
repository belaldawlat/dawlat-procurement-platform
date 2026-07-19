"""Tests for Phase 21 Package P enterprise knowledge graph."""

from __future__ import annotations

import pytest

from app.orchestration import (
    EnterpriseGraphStore,
    EnterpriseKnowledgeGraph,
    EnterpriseKnowledgePolicy,
    EnterpriseKnowledgeRegistry,
    KnowledgeEntity,
    KnowledgeEntityType,
    KnowledgeRelationship,
    KnowledgeRelationshipType,
    WorkflowIntegrityError,
)


def entity(
    external_id: str,
    entity_type: KnowledgeEntityType,
) -> KnowledgeEntity:
    return KnowledgeEntity(
        external_id=external_id,
        entity_type=entity_type,
        name=external_id,
    )


def test_policy_validates_depth() -> None:
    with pytest.raises(ValueError):
        EnterpriseKnowledgePolicy(
            policy_id="invalid",
            name="Invalid",
            maximum_traversal_depth=0,
        )


def test_entity_requires_name() -> None:
    with pytest.raises(ValueError):
        KnowledgeEntity(
            external_id="SUP-1",
            entity_type=KnowledgeEntityType.SUPPLIER,
            name="",
        )


def test_relationship_rejects_self_reference() -> None:
    with pytest.raises(ValueError):
        KnowledgeRelationship(
            source_entity_id="A",
            target_entity_id="A",
            relationship_type=(
                KnowledgeRelationshipType.ASSOCIATED_WITH
            ),
        )


def test_store_rejects_duplicate_external_id() -> None:
    store = EnterpriseGraphStore()
    store.add_entity(
        entity(
            "SUP-1",
            KnowledgeEntityType.SUPPLIER,
        )
    )

    with pytest.raises(WorkflowIntegrityError):
        store.add_entity(
            entity(
                "SUP-1",
                KnowledgeEntityType.SUPPLIER,
            )
        )


def test_graph_adds_entities_and_relationships() -> None:
    graph = EnterpriseKnowledgeGraph()
    supplier = graph.add_entity(
        entity(
            "SUP-1",
            KnowledgeEntityType.SUPPLIER,
        )
    )
    product = graph.add_entity(
        entity(
            "PROD-1",
            KnowledgeEntityType.PRODUCT,
        )
    )

    relationship = graph.add_relationship(
        KnowledgeRelationship(
            source_entity_id=supplier.entity_id,
            target_entity_id=product.entity_id,
            relationship_type=(
                KnowledgeRelationshipType.SUPPLIES
            ),
        )
    )

    assert relationship.source_entity_id == supplier.entity_id


def test_relationship_requires_existing_entities() -> None:
    graph = EnterpriseKnowledgeGraph()

    with pytest.raises(WorkflowIntegrityError):
        graph.add_relationship(
            KnowledgeRelationship(
                source_entity_id="missing-a",
                target_entity_id="missing-b",
                relationship_type=(
                    KnowledgeRelationshipType.DEPENDS_ON
                ),
            )
        )


def test_query_entity_returns_neighbours() -> None:
    graph = EnterpriseKnowledgeGraph()
    supplier = graph.add_entity(
        entity(
            "SUP-1",
            KnowledgeEntityType.SUPPLIER,
        )
    )
    product = graph.add_entity(
        entity(
            "PROD-1",
            KnowledgeEntityType.PRODUCT,
        )
    )
    graph.add_relationship(
        KnowledgeRelationship(
            source_entity_id=supplier.entity_id,
            target_entity_id=product.entity_id,
            relationship_type=(
                KnowledgeRelationshipType.SUPPLIES
            ),
        )
    )

    result = graph.query_entity(supplier.entity_id)

    assert len(result.entities) == 2
    assert len(result.relationships) == 1


def test_find_paths_returns_direct_path() -> None:
    graph = EnterpriseKnowledgeGraph()
    supplier = graph.add_entity(
        entity(
            "SUP-1",
            KnowledgeEntityType.SUPPLIER,
        )
    )
    product = graph.add_entity(
        entity(
            "PROD-1",
            KnowledgeEntityType.PRODUCT,
        )
    )
    graph.add_relationship(
        KnowledgeRelationship(
            source_entity_id=supplier.entity_id,
            target_entity_id=product.entity_id,
            relationship_type=(
                KnowledgeRelationshipType.SUPPLIES
            ),
            weight=0.9,
        )
    )

    result = graph.find_paths(
        supplier.entity_id,
        product.entity_id,
    )

    assert len(result.paths) == 1
    assert result.paths[0].total_weight == 0.9


def test_find_paths_returns_multi_hop_path() -> None:
    graph = EnterpriseKnowledgeGraph()
    supplier = graph.add_entity(
        entity(
            "SUP-1",
            KnowledgeEntityType.SUPPLIER,
        )
    )
    product = graph.add_entity(
        entity(
            "PROD-1",
            KnowledgeEntityType.PRODUCT,
        )
    )
    shipment = graph.add_entity(
        entity(
            "SHIP-1",
            KnowledgeEntityType.SHIPMENT,
        )
    )

    graph.add_relationship(
        KnowledgeRelationship(
            source_entity_id=supplier.entity_id,
            target_entity_id=product.entity_id,
            relationship_type=(
                KnowledgeRelationshipType.SUPPLIES
            ),
        )
    )
    graph.add_relationship(
        KnowledgeRelationship(
            source_entity_id=product.entity_id,
            target_entity_id=shipment.entity_id,
            relationship_type=(
                KnowledgeRelationshipType.CONTAINS
            ),
        )
    )

    result = graph.find_paths(
        supplier.entity_id,
        shipment.entity_id,
    )

    assert len(result.paths) == 1
    assert len(result.paths[0].relationship_ids) == 2


def test_minimum_weight_filters_paths() -> None:
    graph = EnterpriseKnowledgeGraph(
        policy=EnterpriseKnowledgePolicy(
            policy_id="weighted",
            name="Weighted",
            minimum_relationship_weight=0.8,
        )
    )
    supplier = graph.add_entity(
        entity(
            "SUP-1",
            KnowledgeEntityType.SUPPLIER,
        )
    )
    product = graph.add_entity(
        entity(
            "PROD-1",
            KnowledgeEntityType.PRODUCT,
        )
    )
    graph.add_relationship(
        KnowledgeRelationship(
            source_entity_id=supplier.entity_id,
            target_entity_id=product.entity_id,
            relationship_type=(
                KnowledgeRelationshipType.SUPPLIES
            ),
            weight=0.5,
        )
    )

    result = graph.find_paths(
        supplier.entity_id,
        product.entity_id,
    )

    assert result.paths == ()


def test_cycle_creation_can_be_blocked() -> None:
    graph = EnterpriseKnowledgeGraph(
        policy=EnterpriseKnowledgePolicy(
            policy_id="acyclic",
            name="Acyclic",
            allow_cycle_creation=False,
        )
    )
    first = graph.add_entity(
        entity(
            "A",
            KnowledgeEntityType.PRODUCT,
        )
    )
    second = graph.add_entity(
        entity(
            "B",
            KnowledgeEntityType.PRODUCT,
        )
    )
    graph.add_relationship(
        KnowledgeRelationship(
            source_entity_id=first.entity_id,
            target_entity_id=second.entity_id,
            relationship_type=(
                KnowledgeRelationshipType.DEPENDS_ON
            ),
        )
    )

    with pytest.raises(WorkflowIntegrityError):
        graph.add_relationship(
            KnowledgeRelationship(
                source_entity_id=second.entity_id,
                target_entity_id=first.entity_id,
                relationship_type=(
                    KnowledgeRelationshipType.DEPENDS_ON
                ),
            )
        )


def test_impact_analysis_returns_downstream_entities() -> None:
    graph = EnterpriseKnowledgeGraph()
    first = graph.add_entity(
        entity(
            "A",
            KnowledgeEntityType.SUPPLIER,
        )
    )
    second = graph.add_entity(
        entity(
            "B",
            KnowledgeEntityType.PRODUCT,
        )
    )
    third = graph.add_entity(
        entity(
            "C",
            KnowledgeEntityType.SHIPMENT,
        )
    )

    graph.add_relationship(
        KnowledgeRelationship(
            source_entity_id=first.entity_id,
            target_entity_id=second.entity_id,
            relationship_type=(
                KnowledgeRelationshipType.SUPPLIES
            ),
        )
    )
    graph.add_relationship(
        KnowledgeRelationship(
            source_entity_id=second.entity_id,
            target_entity_id=third.entity_id,
            relationship_type=(
                KnowledgeRelationshipType.CONTAINS
            ),
        )
    )

    result = graph.impact_analysis(first.entity_id)

    assert len(result.entities) == 3


def test_registry_rejects_duplicate_resolver() -> None:
    registry = EnterpriseKnowledgeRegistry()
    registry.register(
        KnowledgeEntityType.SUPPLIER,
        lambda external_id: {"id": external_id},
    )

    with pytest.raises(WorkflowIntegrityError):
        registry.register(
            KnowledgeEntityType.SUPPLIER,
            lambda external_id: {"id": external_id},
        )


def test_result_serialises() -> None:
    graph = EnterpriseKnowledgeGraph()
    supplier = graph.add_entity(
        entity(
            "SUP-1",
            KnowledgeEntityType.SUPPLIER,
        )
    )

    payload = graph.query_entity(
        supplier.entity_id
    ).as_dict()

    assert payload["entity_count"] == 1
    assert payload["entities"][0]["external_id"] == "SUP-1"


def test_disabled_policy_rejects_mutation() -> None:
    graph = EnterpriseKnowledgeGraph(
        policy=EnterpriseKnowledgePolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        graph.add_entity(
            entity(
                "SUP-1",
                KnowledgeEntityType.SUPPLIER,
            )
        )