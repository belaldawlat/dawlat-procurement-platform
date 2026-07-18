"""
Platform Bootstrap.

Provides one safe startup entry point for the Dawlat AI Procurement & Global
Trade Intelligence Platform.

Responsibilities:
- initialize enterprise persistence tables;
- register workflow-manager subscribers once;
- register notification-service subscribers once;
- initialize event, monitoring, learning and knowledge-graph services;
- avoid duplicate initialization during Streamlit reruns;
- expose startup health and diagnostics;
- keep app/main.py free from infrastructure details.

The bootstrap does not run recurring monitoring or learning cycles by itself.
Schedulers or approved user actions should invoke those operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from typing import Any

from repositories.procurement_workflow_repository import (
    ProcurementWorkflowRepository,
    create_workflow_tables,
)
from services.event_bus import (
    EnterpriseEventBus,
    create_event_bus_tables,
    get_event_bus,
)
from services.intelligence.knowledge_graph_engine import (
    EnterpriseKnowledgeGraphEngine,
    create_knowledge_graph_tables,
    get_knowledge_graph_engine,
)
from services.intelligence.learning_intelligence_engine import (
    LearningIntelligenceEngine,
    create_learning_tables,
    get_learning_intelligence_engine,
)
from services.monitoring_service import (
    EnterpriseMonitoringService,
    get_monitoring_service,
)
from services.notification_service import (
    EnterpriseNotificationService,
    create_notification_tables,
    get_notification_service,
    register_notification_subscribers,
)
from services.workflow_manager import (
    EnterpriseWorkflowManager,
    get_workflow_manager,
    register_workflow_subscribers,
)


@dataclass(frozen=True)
class BootstrapComponentStatus:
    component: str
    initialized: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformBootstrapResult:
    success: bool
    already_initialized: bool
    components: list[BootstrapComponentStatus] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    initialized_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )

    @property
    def healthy_components(self) -> int:
        return sum(
            1
            for item in self.components
            if item.initialized
        )

    @property
    def failed_components(self) -> int:
        return sum(
            1
            for item in self.components
            if not item.initialized
        )


class PlatformBootstrap:
    """Thread-safe, idempotent enterprise-platform startup coordinator."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._initialized = False
        self._last_result: PlatformBootstrapResult | None = None

        self.event_bus: EnterpriseEventBus | None = None
        self.workflow_repository: ProcurementWorkflowRepository | None = None
        self.workflow_manager: EnterpriseWorkflowManager | None = None
        self.monitoring_service: EnterpriseMonitoringService | None = None
        self.notification_service: EnterpriseNotificationService | None = None
        self.learning_engine: LearningIntelligenceEngine | None = None
        self.knowledge_graph_engine: EnterpriseKnowledgeGraphEngine | None = None

    def initialize(
        self,
        *,
        force: bool = False,
        fail_fast: bool = False,
    ) -> PlatformBootstrapResult:
        """
        Initialize platform infrastructure.

        Safe to call on every Streamlit rerun. Unless force=True, completed
        initialization is reused and subscriber registration is not duplicated.
        """

        with self._lock:
            if self._initialized and not force:
                previous = self._last_result

                if previous is None:
                    return PlatformBootstrapResult(
                        success=True,
                        already_initialized=True,
                    )

                return PlatformBootstrapResult(
                    success=previous.success,
                    already_initialized=True,
                    components=list(previous.components),
                    errors=list(previous.errors),
                    initialized_at=previous.initialized_at,
                )

            components: list[BootstrapComponentStatus] = []
            errors: list[str] = []

            self._run_component(
                name="Workflow Persistence",
                action=create_workflow_tables,
                components=components,
                errors=errors,
                fail_fast=fail_fast,
            )
            self._run_component(
                name="Enterprise Event Bus",
                action=create_event_bus_tables,
                components=components,
                errors=errors,
                fail_fast=fail_fast,
            )
            self._run_component(
                name="Notification Persistence",
                action=create_notification_tables,
                components=components,
                errors=errors,
                fail_fast=fail_fast,
            )
            self._run_component(
                name="Learning Persistence",
                action=create_learning_tables,
                components=components,
                errors=errors,
                fail_fast=fail_fast,
            )
            self._run_component(
                name="Knowledge Graph Persistence",
                action=create_knowledge_graph_tables,
                components=components,
                errors=errors,
                fail_fast=fail_fast,
            )

            self._initialize_services(
                components=components,
                errors=errors,
                fail_fast=fail_fast,
            )

            self._register_subscribers(
                components=components,
                errors=errors,
                fail_fast=fail_fast,
            )

            success = not errors

            result = PlatformBootstrapResult(
                success=success,
                already_initialized=False,
                components=components,
                errors=errors,
            )

            self._initialized = success
            self._last_result = result

            return result

    def health_check(self) -> dict[str, Any]:
        """Return current bootstrap and service availability."""

        result = self._last_result

        return {
            "initialized": self._initialized,
            "success": bool(
                result and result.success
            ),
            "initialized_at": (
                result.initialized_at
                if result
                else None
            ),
            "healthy_components": (
                result.healthy_components
                if result
                else 0
            ),
            "failed_components": (
                result.failed_components
                if result
                else 0
            ),
            "errors": (
                list(result.errors)
                if result
                else []
            ),
            "services": {
                "event_bus": self.event_bus is not None,
                "workflow_repository": (
                    self.workflow_repository is not None
                ),
                "workflow_manager": (
                    self.workflow_manager is not None
                ),
                "monitoring_service": (
                    self.monitoring_service is not None
                ),
                "notification_service": (
                    self.notification_service is not None
                ),
                "learning_engine": (
                    self.learning_engine is not None
                ),
                "knowledge_graph_engine": (
                    self.knowledge_graph_engine is not None
                ),
            },
        }

    def reset_for_testing(self) -> None:
        """
        Reset only in-memory bootstrap state.

        This does not drop database tables or delete persisted records.
        """

        with self._lock:
            self._initialized = False
            self._last_result = None

    def _initialize_services(
        self,
        *,
        components: list[BootstrapComponentStatus],
        errors: list[str],
        fail_fast: bool,
    ) -> None:
        service_initializers = [
            (
                "Event Bus Service",
                self._set_event_bus,
            ),
            (
                "Workflow Repository Service",
                self._set_workflow_repository,
            ),
            (
                "Workflow Manager Service",
                self._set_workflow_manager,
            ),
            (
                "Monitoring Service",
                self._set_monitoring_service,
            ),
            (
                "Notification Service",
                self._set_notification_service,
            ),
            (
                "Learning Intelligence Service",
                self._set_learning_engine,
            ),
            (
                "Knowledge Graph Service",
                self._set_knowledge_graph_engine,
            ),
        ]

        for name, action in service_initializers:
            self._run_component(
                name=name,
                action=action,
                components=components,
                errors=errors,
                fail_fast=fail_fast,
            )

    def _register_subscribers(
        self,
        *,
        components: list[BootstrapComponentStatus],
        errors: list[str],
        fail_fast: bool,
    ) -> None:
        def register_workflow() -> dict[str, Any]:
            subscriber_ids = register_workflow_subscribers()
            return {
                "subscriber_count": len(subscriber_ids),
                "subscriber_ids": subscriber_ids,
            }

        def register_notifications() -> dict[str, Any]:
            subscriber_ids = register_notification_subscribers()
            return {
                "subscriber_count": len(subscriber_ids),
                "subscriber_ids": subscriber_ids,
            }

        self._run_component(
            name="Workflow Event Subscribers",
            action=register_workflow,
            components=components,
            errors=errors,
            fail_fast=fail_fast,
        )
        self._run_component(
            name="Notification Event Subscribers",
            action=register_notifications,
            components=components,
            errors=errors,
            fail_fast=fail_fast,
        )

    def _set_event_bus(self) -> dict[str, Any]:
        self.event_bus = get_event_bus()
        return {
            "service": type(self.event_bus).__name__,
        }

    def _set_workflow_repository(self) -> dict[str, Any]:
        self.workflow_repository = ProcurementWorkflowRepository()
        return {
            "service": type(
                self.workflow_repository
            ).__name__,
        }

    def _set_workflow_manager(self) -> dict[str, Any]:
        self.workflow_manager = get_workflow_manager()
        return {
            "service": type(
                self.workflow_manager
            ).__name__,
        }

    def _set_monitoring_service(self) -> dict[str, Any]:
        self.monitoring_service = get_monitoring_service()
        return {
            "service": type(
                self.monitoring_service
            ).__name__,
        }

    def _set_notification_service(self) -> dict[str, Any]:
        self.notification_service = get_notification_service()
        return {
            "service": type(
                self.notification_service
            ).__name__,
        }

    def _set_learning_engine(self) -> dict[str, Any]:
        self.learning_engine = get_learning_intelligence_engine()
        return {
            "service": type(
                self.learning_engine
            ).__name__,
        }

    def _set_knowledge_graph_engine(self) -> dict[str, Any]:
        self.knowledge_graph_engine = get_knowledge_graph_engine()
        return {
            "service": type(
                self.knowledge_graph_engine
            ).__name__,
        }

    @staticmethod
    def _run_component(
        *,
        name: str,
        action: Any,
        components: list[BootstrapComponentStatus],
        errors: list[str],
        fail_fast: bool,
    ) -> None:
        try:
            result = action()
            details = (
                result
                if isinstance(result, dict)
                else {}
            )

            components.append(
                BootstrapComponentStatus(
                    component=name,
                    initialized=True,
                    message="Initialized successfully.",
                    details=details,
                )
            )

        except Exception as error:
            message = f"{name}: {error}"
            errors.append(message)
            components.append(
                BootstrapComponentStatus(
                    component=name,
                    initialized=False,
                    message=str(error),
                )
            )

            if fail_fast:
                raise RuntimeError(message) from error


_bootstrap = PlatformBootstrap()


def get_platform_bootstrap() -> PlatformBootstrap:
    """Return the platform bootstrap singleton."""

    return _bootstrap


def initialize_platform(
    *,
    force: bool = False,
    fail_fast: bool = False,
) -> PlatformBootstrapResult:
    """
    Initialize all enterprise platform services.

    Recommended usage in app/main.py:

        from services.platform_bootstrap import initialize_platform

        bootstrap = initialize_platform()
        if not bootstrap.success:
            st.error("Platform initialization failed.")
            st.stop()
    """

    return _bootstrap.initialize(
        force=force,
        fail_fast=fail_fast,
    )


def get_platform_health() -> dict[str, Any]:
    """Return bootstrap and enterprise service health."""

    return _bootstrap.health_check()