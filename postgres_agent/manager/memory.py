"""
Shared Memory for multi-agent coordination and decision tracking.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SharedMemory:
    """
    Centralized memory store for multi-agent coordination.
    Thread-safe storage for findings, decisions, and agent results.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._findings: List[Dict[str, Any]] = []
        self._recommendations: List[Dict[str, Any]] = []
        self._agent_results: Dict[str, Dict[str, Any]] = {}
        self._task_states: Dict[str, TaskStatus] = {}
        self._catalog_cache: Dict[str, Any] = {}
        self._decisions: List[Dict[str, Any]] = []
        self._metrics: Dict[str, Any] = {}
        self._audit_id: Optional[str] = None
        self._start_time: Optional[datetime] = None

    async def initialize_audit(self, audit_id: str) -> None:
        """Initialize a new audit session."""
        async with self._lock:
            self._audit_id = audit_id
            self._start_time = datetime.utcnow()
            self._findings = []
            self._recommendations = []
            self._agent_results = {}
            self._task_states = {}
            self._decisions = []
            self._metrics = {
                'audit_id': audit_id,
                'start_time': self._start_time.isoformat(),
                'agents_completed': 0,
                'total_findings': 0,
                'critical_findings': 0,
            }
            logger.info(f"Initialized audit session: {audit_id}")

    async def add_finding(
        self,
        agent: str,
        category: str,
        title: str,
        description: str,
        severity: FindingSeverity,
        affected_objects: List[str] = None,
        remediation: str = "",
        metadata: Dict[str, Any] = None
    ) -> None:
        """Add a finding from an agent."""
        async with self._lock:
            finding = {
                'id': len(self._findings) + 1,
                'agent': agent,
                'category': category,
                'title': title,
                'description': description,
                'severity': severity.value,
                'affected_objects': affected_objects or [],
                'remediation': remediation,
                'metadata': metadata or {},
                'timestamp': datetime.utcnow().isoformat()
            }
            self._findings.append(finding)
            self._metrics['total_findings'] = len(self._findings)

            if severity == FindingSeverity.CRITICAL:
                self._metrics['critical_findings'] += 1

            logger.debug(f"Added finding: {title} ({severity.value})")

    async def add_recommendation(
        self,
        agent: str,
        category: str,
        title: str,
        description: str,
        priority: int,
        effort: str = "medium",
        impact: str = "medium",
        implementation: str = ""
    ) -> None:
        """Add a recommendation."""
        async with self._lock:
            recommendation = {
                'id': len(self._recommendations) + 1,
                'agent': agent,
                'category': category,
                'title': title,
                'description': description,
                'priority': priority,
                'effort': effort,
                'impact': impact,
                'implementation': implementation,
                'timestamp': datetime.utcnow().isoformat()
            }
            self._recommendations.append(recommendation)
            logger.debug(f"Added recommendation: {title}")

    async def store_agent_result(self, agent_name: str, result: Dict[str, Any]) -> None:
        """Store the complete result from an agent."""
        async with self._lock:
            self._agent_results[agent_name] = {
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            }
            self._metrics['agents_completed'] += 1
            logger.info(f"Stored results from agent: {agent_name}")

    async def set_task_status(self, task_id: str, status: TaskStatus) -> None:
        """Update task status."""
        async with self._lock:
            self._task_states[task_id] = status
            logger.debug(f"Task {task_id} status: {status.value}")

    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get task status."""
        async with self._lock:
            return self._task_states.get(task_id)

    async def cache_catalog(self, key: str, data: Any) -> None:
        """Cache catalog data for reuse by agents."""
        async with self._lock:
            self._catalog_cache[key] = data

    async def get_cached_catalog(self, key: str) -> Optional[Any]:
        """Get cached catalog data."""
        async with self._lock:
            return self._catalog_cache.get(key)

    async def add_decision(self, agent: str, decision: str, rationale: str) -> None:
        """Record a decision made by an agent."""
        async with self._lock:
            self._decisions.append({
                'agent': agent,
                'decision': decision,
                'rationale': rationale,
                'timestamp': datetime.utcnow().isoformat()
            })

    async def get_findings(
        self,
        severity: Optional[FindingSeverity] = None,
        agent: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get findings with optional filters."""
        async with self._lock:
            results = self._findings.copy()

            if severity:
                results = [f for f in results if f['severity'] == severity.value]
            if agent:
                results = [f for f in results if f['agent'] == agent]
            if category:
                results = [f for f in results if f['category'] == category]

            return results

    async def get_recommendations(self, min_priority: int = 0) -> List[Dict[str, Any]]:
        """Get recommendations sorted by priority."""
        async with self._lock:
            results = [r for r in self._recommendations if r['priority'] >= min_priority]
            return sorted(results, key=lambda x: x['priority'], reverse=True)

    async def get_agent_result(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get results from a specific agent."""
        async with self._lock:
            return self._agent_results.get(agent_name)

    async def get_all_results(self) -> Dict[str, Any]:
        """Get consolidated results from all agents."""
        async with self._lock:
            end_time = datetime.utcnow()
            duration = (end_time - self._start_time).total_seconds() if self._start_time else 0

            return {
                'audit_id': self._audit_id,
                'start_time': self._start_time.isoformat() if self._start_time else None,
                'end_time': end_time.isoformat(),
                'duration_seconds': duration,
                'metrics': self._metrics.copy(),
                'findings': self._findings.copy(),
                'recommendations': sorted(
                    self._recommendations.copy(),
                    key=lambda x: x['priority'],
                    reverse=True
                ),
                'agent_results': {k: v['result'] for k, v in self._agent_results.items()},
                'decisions': self._decisions.copy(),
            }

    async def get_summary(self) -> Dict[str, Any]:
        """Get audit summary statistics."""
        async with self._lock:
            severity_counts = {}
            for finding in self._findings:
                sev = finding['severity']
                severity_counts[sev] = severity_counts.get(sev, 0) + 1

            category_counts = {}
            for finding in self._findings:
                cat = finding['category']
                category_counts[cat] = category_counts.get(cat, 0) + 1

            agent_finding_counts = {}
            for finding in self._findings:
                agent = finding['agent']
                agent_finding_counts[agent] = agent_finding_counts.get(agent, 0) + 1

            return {
                'audit_id': self._audit_id,
                'total_findings': len(self._findings),
                'total_recommendations': len(self._recommendations),
                'agents_completed': len(self._agent_results),
                'severity_distribution': severity_counts,
                'category_distribution': category_counts,
                'findings_by_agent': agent_finding_counts,
                'decisions_made': len(self._decisions),
            }

    async def export_json(self) -> str:
        """Export all results as JSON."""
        results = await self.get_all_results()
        return json.dumps(results, indent=2, default=str)

    async def clear(self) -> None:
        """Clear all stored data."""
        async with self._lock:
            self._findings = []
            self._recommendations = []
            self._agent_results = {}
            self._task_states = {}
            self._catalog_cache = {}
            self._decisions = []
            self._metrics = {}
            self._audit_id = None
            self._start_time = None
            logger.info("Memory cleared")
