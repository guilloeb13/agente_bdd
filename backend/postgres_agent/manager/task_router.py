"""
Task Router for directing work to appropriate agents.
"""

from enum import Enum
from typing import Any, Dict, List, Type, Optional
import logging

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    FULL_AUDIT = "full_audit"
    SECURITY_AUDIT = "security_audit"
    SCHEMA_ANALYSIS = "schema_analysis"
    FK_INTEGRITY = "fk_integrity"
    ORPHAN_CHECK = "orphan_check"
    NORMALIZATION = "normalization"
    PERFORMANCE = "performance"
    INDEXING = "indexing"
    DATA_QUALITY = "data_quality"
    ANOMALY_DETECTION = "anomaly_detection"
    DDL_RECONSTRUCTION = "ddl_reconstruction"
    RECOMMENDATIONS = "recommendations"


class AgentCapability(str, Enum):
    SECURITY = "security"
    SCHEMA = "schema"
    INTEGRITY = "integrity"
    ORPHANS = "orphans"
    NORMALIZATION = "normalization"
    PERFORMANCE = "performance"
    INDEXING = "indexing"
    DATA_QUALITY = "data_quality"
    ANOMALY = "anomaly"
    DDL = "ddl"
    RECOMMENDATIONS = "recommendations"


class TaskRouter:
    """
    Routes tasks to appropriate agents based on task type and agent capabilities.
    """

    # Mapping of task types to required agent capabilities
    TASK_AGENT_MAP: Dict[TaskType, List[AgentCapability]] = {
        TaskType.FULL_AUDIT: [
            AgentCapability.SECURITY,
            AgentCapability.SCHEMA,
            AgentCapability.INTEGRITY,
            AgentCapability.ORPHANS,
            AgentCapability.NORMALIZATION,
            AgentCapability.PERFORMANCE,
            AgentCapability.INDEXING,
            AgentCapability.DATA_QUALITY,
            AgentCapability.ANOMALY,
            AgentCapability.DDL,
            AgentCapability.RECOMMENDATIONS,
        ],
        TaskType.SECURITY_AUDIT: [AgentCapability.SECURITY],
        TaskType.SCHEMA_ANALYSIS: [AgentCapability.SCHEMA],
        TaskType.FK_INTEGRITY: [AgentCapability.INTEGRITY],
        TaskType.ORPHAN_CHECK: [AgentCapability.ORPHANS],
        TaskType.NORMALIZATION: [AgentCapability.NORMALIZATION],
        TaskType.PERFORMANCE: [AgentCapability.PERFORMANCE],
        TaskType.INDEXING: [AgentCapability.INDEXING],
        TaskType.DATA_QUALITY: [AgentCapability.DATA_QUALITY],
        TaskType.ANOMALY_DETECTION: [AgentCapability.ANOMALY],
        TaskType.DDL_RECONSTRUCTION: [AgentCapability.DDL],
        TaskType.RECOMMENDATIONS: [AgentCapability.RECOMMENDATIONS],
    }

    # Agent execution order (dependencies)
    EXECUTION_ORDER: List[AgentCapability] = [
        AgentCapability.SCHEMA,       # First - provides base catalog
        AgentCapability.SECURITY,     # Can run parallel with integrity
        AgentCapability.INTEGRITY,    # FK analysis
        AgentCapability.ORPHANS,      # Depends on integrity
        AgentCapability.NORMALIZATION,# Depends on schema
        AgentCapability.PERFORMANCE,  # Independent
        AgentCapability.INDEXING,     # Depends on performance
        AgentCapability.DATA_QUALITY, # Independent
        AgentCapability.ANOMALY,      # Depends on data quality
        AgentCapability.DDL,          # Independent
        AgentCapability.RECOMMENDATIONS,  # Last - consolidates all
    ]

    # Agents that can run in parallel (no dependencies on each other)
    PARALLEL_GROUPS: List[List[AgentCapability]] = [
        [AgentCapability.SCHEMA],
        [AgentCapability.SECURITY, AgentCapability.INTEGRITY],
        [AgentCapability.ORPHANS, AgentCapability.NORMALIZATION, AgentCapability.PERFORMANCE, AgentCapability.DATA_QUALITY, AgentCapability.DDL],
        [AgentCapability.INDEXING, AgentCapability.ANOMALY],
        [AgentCapability.RECOMMENDATIONS],
    ]

    def __init__(self):
        self._registered_agents: Dict[AgentCapability, Any] = {}

    def register_agent(self, capability: AgentCapability, agent_class: Type) -> None:
        """Register an agent class for a capability."""
        self._registered_agents[capability] = agent_class
        logger.debug(f"Registered agent for {capability.value}")

    def get_agents_for_task(self, task_type: TaskType) -> List[AgentCapability]:
        """Get list of agent capabilities needed for a task."""
        return self.TASK_AGENT_MAP.get(task_type, [])

    def get_execution_plan(self, task_type: TaskType) -> List[List[AgentCapability]]:
        """
        Get execution plan as groups of agents that can run in parallel.
        Returns list of groups, where agents in each group can run concurrently.
        """
        required_capabilities = set(self.get_agents_for_task(task_type))

        plan = []
        for group in self.PARALLEL_GROUPS:
            agents_in_group = [cap for cap in group if cap in required_capabilities]
            if agents_in_group:
                plan.append(agents_in_group)

        return plan

    def get_agent_class(self, capability: AgentCapability) -> Optional[Type]:
        """Get registered agent class for a capability."""
        return self._registered_agents.get(capability)

    def validate_task(self, task_type: TaskType) -> bool:
        """Validate that all required agents are registered for a task."""
        required = self.get_agents_for_task(task_type)
        for cap in required:
            if cap not in self._registered_agents:
                logger.error(f"Missing agent for capability: {cap.value}")
                return False
        return True

    def get_dependencies(self, capability: AgentCapability) -> List[AgentCapability]:
        """Get agent capabilities that must run before this one."""
        dependencies = []

        for group in self.PARALLEL_GROUPS:
            if capability in group:
                break
            dependencies.extend(group)

        return dependencies

    def get_task_info(self, task_type: TaskType) -> Dict[str, Any]:
        """Get information about a task type."""
        agents = self.get_agents_for_task(task_type)
        plan = self.get_execution_plan(task_type)

        return {
            'task_type': task_type.value,
            'required_agents': [a.value for a in agents],
            'execution_plan': [[a.value for a in group] for group in plan],
            'total_agents': len(agents),
            'parallel_groups': len(plan),
        }

    @staticmethod
    def list_task_types() -> List[str]:
        """List all available task types."""
        return [t.value for t in TaskType]

    @staticmethod
    def list_capabilities() -> List[str]:
        """List all agent capabilities."""
        return [c.value for c in AgentCapability]


class SubTask:
    """Represents a subtask for an agent."""

    def __init__(
        self,
        task_id: str,
        capability: AgentCapability,
        params: Dict[str, Any] = None,
        priority: int = 1
    ):
        self.task_id = task_id
        self.capability = capability
        self.params = params or {}
        self.priority = priority

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'capability': self.capability.value,
            'params': self.params,
            'priority': self.priority
        }
