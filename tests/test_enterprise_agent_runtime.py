"""Tests for Phase 21 Package R enterprise AI agent runtime."""

from __future__ import annotations

import pytest

from app.orchestration import (
    EnterpriseAgentCapability,
    EnterpriseAgentDefinition,
    EnterpriseAgentHealth,
    EnterpriseAgentMemory,
    EnterpriseAgentPolicy,
    EnterpriseAgentRegistry,
    EnterpriseAgentRuntime,
    EnterpriseAgentStatus,
    EnterpriseAgentTask,
    EnterpriseAgentTaskStatus,
    WorkflowIntegrityError,
)


def agent(
    agent_id: str = "agent-1",
    *,
    status: EnterpriseAgentStatus = EnterpriseAgentStatus.IDLE,
    capability: EnterpriseAgentCapability = (
        EnterpriseAgentCapability.PROCUREMENT
    ),
) -> EnterpriseAgentDefinition:
    return EnterpriseAgentDefinition(
        agent_id=agent_id,
        name=agent_id,
        capabilities=(capability,),
        maximum_concurrency=1,
        status=status,
    )


def task(
    entity_id: str = "PROC-1",
    *,
    capability: EnterpriseAgentCapability = (
        EnterpriseAgentCapability.PROCUREMENT
    ),
    priority: int = 50,
) -> EnterpriseAgentTask:
    return EnterpriseAgentTask(
        capability=capability,
        entity_id=entity_id,
        payload={"entity_id": entity_id},
        priority=priority,
    )


def runtime_with_agent(handler) -> EnterpriseAgentRuntime:
    registry = EnterpriseAgentRegistry()
    registry.register(agent(), handler)

    return EnterpriseAgentRuntime(
        registry=registry,
        policy=EnterpriseAgentPolicy(
            policy_id="runtime",
            name="Runtime",
        ),
    )


def test_policy_validates_limits() -> None:
    with pytest.raises(ValueError):
        EnterpriseAgentPolicy(
            policy_id="invalid",
            name="Invalid",
            maximum_runtime_agents=0,
        )


def test_agent_requires_capability() -> None:
    with pytest.raises(ValueError):
        EnterpriseAgentDefinition(
            agent_id="agent",
            name="Agent",
            capabilities=(),
        )


def test_task_validates_priority() -> None:
    with pytest.raises(ValueError):
        task(priority=101)


def test_registry_rejects_duplicate_agent() -> None:
    registry = EnterpriseAgentRegistry()
    registry.register(agent(), lambda payload: {})

    with pytest.raises(WorkflowIntegrityError):
        registry.register(agent(), lambda payload: {})


def test_successful_task_completes() -> None:
    runtime = runtime_with_agent(
        lambda payload: {"approved": True}
    )

    result = runtime.run((task(),))

    assert len(result.completed) == 1
    assert result.completed[0].successful is True
    assert (
        result.completed[0].task.status
        is EnterpriseAgentTaskStatus.COMPLETED
    )


def test_missing_capable_agent_blocks_task() -> None:
    runtime = runtime_with_agent(
        lambda payload: {"ok": True}
    )

    result = runtime.run(
        (
            task(
                capability=(
                    EnterpriseAgentCapability.RISK_ANALYSIS
                )
            ),
        )
    )

    assert len(result.blocked_tasks) == 1
    assert (
        result.blocked_tasks[0].status
        is EnterpriseAgentTaskStatus.BLOCKED
    )


def test_failed_handler_returns_failure() -> None:
    def failing_handler(payload):
        raise RuntimeError("agent failure")

    runtime = runtime_with_agent(failing_handler)
    result = runtime.run((task(),))

    assert len(result.failed) == 1
    assert result.failed[0].successful is False
    assert "agent failure" in result.failed[0].error


def test_handler_must_return_dictionary() -> None:
    runtime = runtime_with_agent(
        lambda payload: "invalid"
    )

    result = runtime.run((task(),))

    assert len(result.failed) == 1


def test_memory_records_successful_output() -> None:
    runtime = runtime_with_agent(
        lambda payload: {"score": 95}
    )
    item = task()

    result = runtime.run((item,))
    assigned_agent_id = (
        result.completed[0].task.assigned_agent_id
    )

    assert runtime.memory.read(
        assigned_agent_id,
        item.task_id,
    ) == {"score": 95}


def test_memory_redacts_sensitive_mapping() -> None:
    memory = EnterpriseAgentMemory()
    memory.write(
        "agent-1",
        "secret",
        {"password": "private"},
    )

    stored = memory.read("agent-1", "secret")

    assert stored["password"] != "private"


def test_unhealthy_agent_does_not_receive_work() -> None:
    registry = EnterpriseAgentRegistry()
    registry.register(
        agent(
            status=EnterpriseAgentStatus.DISABLED,
        ),
        lambda payload: {"ok": True},
    )
    runtime = EnterpriseAgentRuntime(registry=registry)

    result = runtime.run((task(),))

    assert len(result.blocked_tasks) == 1


def test_health_detects_capacity_exhaustion() -> None:
    health = EnterpriseAgentHealth().evaluate(
        agent(),
        active_tasks=1,
    )

    assert health.healthy is False
    assert health.status is EnterpriseAgentStatus.DEGRADED


def test_higher_priority_task_runs_first() -> None:
    order = []
    runtime = runtime_with_agent(
        lambda payload: order.append(
            payload["entity_id"]
        ) or {"ok": True}
    )

    runtime.run(
        (
            task("LOW", priority=10),
            task("HIGH", priority=100),
        )
    )

    assert order == ["HIGH", "LOW"]


def test_terminal_tasks_are_skipped() -> None:
    runtime = runtime_with_agent(
        lambda payload: {"ok": True}
    )
    completed_task = EnterpriseAgentTask(
        capability=EnterpriseAgentCapability.PROCUREMENT,
        entity_id="PROC-1",
        payload={},
        status=EnterpriseAgentTaskStatus.COMPLETED,
    )

    result = runtime.run((completed_task,))

    assert result.completed == ()
    assert result.failed == ()


def test_result_serialises() -> None:
    result = runtime_with_agent(
        lambda payload: {"ok": True}
    ).run((task(),))

    payload = result.as_dict()

    assert payload["completed_count"] == 1
    assert payload["completed"]


def test_disabled_policy_rejects_run() -> None:
    runtime = EnterpriseAgentRuntime(
        policy=EnterpriseAgentPolicy(
            policy_id="disabled",
            name="Disabled",
            enabled=False,
        )
    )

    with pytest.raises(ValueError):
        runtime.run((task(),))