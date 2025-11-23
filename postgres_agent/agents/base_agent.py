"""
Base Agent class for all specialized agents.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging

from ..engine import PGClient, QueryRunner
from ..manager.memory import SharedMemory, FindingSeverity

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all analysis agents.
    """

    def __init__(self, client: PGClient):
        self.client = client
        self.runner = QueryRunner(client)
        self.name = self.__class__.__name__

    @abstractmethod
    async def analyze(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Perform analysis. Must be implemented by each agent.

        Args:
            catalog: Full database catalog
            schemas: List of schemas to analyze
            memory: Shared memory for storing findings
            options: Optional configuration

        Returns:
            Analysis results dictionary
        """
        pass

    async def add_finding(
        self,
        memory: SharedMemory,
        category: str,
        title: str,
        description: str,
        severity: FindingSeverity,
        affected_objects: List[str] = None,
        remediation: str = "",
        metadata: Dict[str, Any] = None
    ) -> None:
        """Helper method to add findings."""
        await memory.add_finding(
            agent=self.name,
            category=category,
            title=title,
            description=description,
            severity=severity,
            affected_objects=affected_objects,
            remediation=remediation,
            metadata=metadata
        )

    async def add_recommendation(
        self,
        memory: SharedMemory,
        category: str,
        title: str,
        description: str,
        priority: int,
        effort: str = "medium",
        impact: str = "medium",
        implementation: str = ""
    ) -> None:
        """Helper method to add recommendations."""
        await memory.add_recommendation(
            agent=self.name,
            category=category,
            title=title,
            description=description,
            priority=priority,
            effort=effort,
            impact=impact,
            implementation=implementation
        )

    def get_tables_from_catalog(self, catalog: Dict[str, Any], schema: str) -> List[Dict]:
        """Extract tables from catalog for a schema."""
        return catalog.get('schemas', {}).get(schema, {}).get('tables', [])

    def get_constraints_from_catalog(self, catalog: Dict[str, Any], schema: str) -> List[Dict]:
        """Extract constraints from catalog."""
        return catalog.get('schemas', {}).get(schema, {}).get('constraints', [])

    def get_indexes_from_catalog(self, catalog: Dict[str, Any], schema: str) -> List[Dict]:
        """Extract indexes from catalog."""
        return catalog.get('schemas', {}).get(schema, {}).get('indexes', [])

    def get_functions_from_catalog(self, catalog: Dict[str, Any], schema: str) -> List[Dict]:
        """Extract functions from catalog."""
        return catalog.get('schemas', {}).get(schema, {}).get('functions', [])

    def log_info(self, message: str) -> None:
        """Log info message with agent name."""
        logger.info(f"[{self.name}] {message}")

    def log_warning(self, message: str) -> None:
        """Log warning with agent name."""
        logger.warning(f"[{self.name}] {message}")

    def log_error(self, message: str) -> None:
        """Log error with agent name."""
        logger.error(f"[{self.name}] {message}")
