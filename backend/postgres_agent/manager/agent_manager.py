"""
Agent Manager - Central orchestrator for multi-agent coordination.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Type
import logging

from .memory import SharedMemory, TaskStatus
from .task_router import TaskRouter, TaskType, AgentCapability
from ..engine import PGClient, MetricsCollector

logger = logging.getLogger(__name__)


class AgentManager:
    """
    Central manager that coordinates all agents for database auditing.
    """

    def __init__(self, pg_client: PGClient):
        self.pg_client = pg_client
        self.metrics_collector = MetricsCollector(pg_client)
        self.memory = SharedMemory()
        self.router = TaskRouter()
        self._agents: Dict[AgentCapability, Any] = {}
        self._is_running = False
        self._current_audit_id: Optional[str] = None

    def register_agent(self, capability: AgentCapability, agent_instance: Any) -> None:
        """Register an agent instance."""
        self._agents[capability] = agent_instance
        self.router.register_agent(capability, type(agent_instance))
        logger.info(f"Registered agent: {capability.value}")

    async def run_full_audit(
        self,
        schemas: List[str] = None,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a complete database audit using all agents.
        """
        if self._is_running:
            raise RuntimeError("An audit is already in progress")

        self._is_running = True
        audit_id = str(uuid.uuid4())[:8]
        self._current_audit_id = audit_id

        try:
            # Initialize audit session
            await self.memory.initialize_audit(audit_id)
            logger.info(f"Starting full audit: {audit_id}")

            # Collect initial catalog
            schemas = schemas or ['public']
            options = options or {}

            logger.info(f"Collecting catalog for schemas: {schemas}")
            catalog = await self.metrics_collector.collect_full_catalog(schemas)
            await self.memory.cache_catalog('full_catalog', catalog)

            # Execute audit
            await self._execute_task(TaskType.FULL_AUDIT, schemas, options)

            # Get final results
            results = await self.memory.get_all_results()
            logger.info(f"Audit {audit_id} completed successfully")

            return results

        except Exception as e:
            logger.error(f"Audit {audit_id} failed: {e}")
            raise
        finally:
            self._is_running = False
            self._current_audit_id = None

    async def run_specific_audit(
        self,
        task_type: TaskType,
        schemas: List[str] = None,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Execute a specific type of audit.
        """
        if self._is_running:
            raise RuntimeError("An audit is already in progress")

        self._is_running = True
        audit_id = str(uuid.uuid4())[:8]
        self._current_audit_id = audit_id

        try:
            await self.memory.initialize_audit(audit_id)
            logger.info(f"Starting {task_type.value} audit: {audit_id}")

            schemas = schemas or ['public']
            options = options or {}

            # Collect catalog
            catalog = await self.metrics_collector.collect_full_catalog(schemas)
            await self.memory.cache_catalog('full_catalog', catalog)

            # Execute specific task
            await self._execute_task(task_type, schemas, options)

            results = await self.memory.get_all_results()
            logger.info(f"Audit {audit_id} completed")

            return results

        except Exception as e:
            logger.error(f"Audit {audit_id} failed: {e}")
            raise
        finally:
            self._is_running = False
            self._current_audit_id = None

    async def _execute_task(
        self,
        task_type: TaskType,
        schemas: List[str],
        options: Dict[str, Any]
    ) -> None:
        """
        Execute a task by running agents according to execution plan.
        """
        # Validate all required agents are available
        if not self.router.validate_task(task_type):
            missing = self._get_missing_agents(task_type)
            raise RuntimeError(f"Missing agents for task: {missing}")

        # Get execution plan
        plan = self.router.get_execution_plan(task_type)
        logger.info(f"Execution plan has {len(plan)} parallel groups")

        # Execute groups in order
        for group_idx, group in enumerate(plan):
            logger.info(f"Executing group {group_idx + 1}/{len(plan)}: {[c.value for c in group]}")

            # Run agents in this group concurrently
            tasks = []
            for capability in group:
                agent = self._agents.get(capability)
                if agent:
                    task = self._run_agent(capability, agent, schemas, options)
                    tasks.append(task)

            # Wait for all agents in group to complete
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Check for exceptions
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Agent failed: {result}")

    async def _run_agent(
        self,
        capability: AgentCapability,
        agent: Any,
        schemas: List[str],
        options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run a single agent and store its results.
        """
        agent_name = capability.value
        task_id = f"{self._current_audit_id}_{agent_name}"

        try:
            await self.memory.set_task_status(task_id, TaskStatus.RUNNING)
            logger.info(f"Running agent: {agent_name}")

            # Get cached catalog
            catalog = await self.memory.get_cached_catalog('full_catalog')

            # Run agent analysis
            start_time = datetime.utcnow()
            result = await agent.analyze(
                catalog=catalog,
                schemas=schemas,
                memory=self.memory,
                options=options
            )
            duration = (datetime.utcnow() - start_time).total_seconds()

            # Store results
            result['duration_seconds'] = duration
            await self.memory.store_agent_result(agent_name, result)
            await self.memory.set_task_status(task_id, TaskStatus.COMPLETED)

            logger.info(f"Agent {agent_name} completed in {duration:.2f}s")
            return result

        except Exception as e:
            await self.memory.set_task_status(task_id, TaskStatus.FAILED)
            logger.error(f"Agent {agent_name} failed: {e}")
            raise

    def _get_missing_agents(self, task_type: TaskType) -> List[str]:
        """Get list of missing agents for a task."""
        required = self.router.get_agents_for_task(task_type)
        missing = []
        for cap in required:
            if cap not in self._agents:
                missing.append(cap.value)
        return missing

    async def get_status(self) -> Dict[str, Any]:
        """Get current audit status."""
        if not self._is_running:
            return {
                'status': 'idle',
                'audit_id': None
            }

        summary = await self.memory.get_summary()
        return {
            'status': 'running',
            'audit_id': self._current_audit_id,
            **summary
        }

    async def get_summary(self) -> Dict[str, Any]:
        """Get audit summary."""
        return await self.memory.get_summary()

    async def get_findings(self, **filters) -> List[Dict[str, Any]]:
        """Get findings with optional filters."""
        return await self.memory.get_findings(**filters)

    async def get_recommendations(self, min_priority: int = 0) -> List[Dict[str, Any]]:
        """Get recommendations."""
        return await self.memory.get_recommendations(min_priority)

    async def export_results(self) -> str:
        """Export results as JSON."""
        return await self.memory.export_json()

    @property
    def is_running(self) -> bool:
        """Check if an audit is currently running."""
        return self._is_running

    @property
    def registered_agents(self) -> List[str]:
        """Get list of registered agent names."""
        return [cap.value for cap in self._agents.keys()]


async def create_manager(
    host: str = "localhost",
    port: int = 5432,
    database: str = "postgres",
    user: str = "postgres",
    password: str = ""
) -> AgentManager:
    """
    Factory function to create a fully configured AgentManager.
    """
    # Create client
    client = PGClient(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password
    )
    await client.connect()

    # Create manager
    manager = AgentManager(client)

    # Import and register all agents
    from ..agents import (
        SecurityAgent,
        SchemaAgent,
        FKIntegrityAgent,
        OrphanCheckerAgent,
        NormalizationAgent,
        PerformanceAgent,
        IndexingAgent,
        DataQualityAgent,
        AnomalyAgent,
        DDLReconstructionAgent,
        RecommendationAgent,
    )

    # Register agents
    manager.register_agent(AgentCapability.SECURITY, SecurityAgent(client))
    manager.register_agent(AgentCapability.SCHEMA, SchemaAgent(client))
    manager.register_agent(AgentCapability.INTEGRITY, FKIntegrityAgent(client))
    manager.register_agent(AgentCapability.ORPHANS, OrphanCheckerAgent(client))
    manager.register_agent(AgentCapability.NORMALIZATION, NormalizationAgent(client))
    manager.register_agent(AgentCapability.PERFORMANCE, PerformanceAgent(client))
    manager.register_agent(AgentCapability.INDEXING, IndexingAgent(client))
    manager.register_agent(AgentCapability.DATA_QUALITY, DataQualityAgent(client))
    manager.register_agent(AgentCapability.ANOMALY, AnomalyAgent(client))
    manager.register_agent(AgentCapability.DDL, DDLReconstructionAgent(client))
    manager.register_agent(AgentCapability.RECOMMENDATIONS, RecommendationAgent(client))

    return manager
