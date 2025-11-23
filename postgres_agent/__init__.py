"""
PostgreSQL Multi-Agent Analyzer (PMA-Agent)

A comprehensive multi-agent system for PostgreSQL database auditing,
security analysis, performance optimization, and schema normalization.
"""

__version__ = "1.0.0"
__author__ = "PMA-Agent Team"

from .engine import PGClient, QueryRunner, MetricsCollector
from .manager import AgentManager, SharedMemory, TaskRouter

__all__ = [
    'PGClient',
    'QueryRunner',
    'MetricsCollector',
    'AgentManager',
    'SharedMemory',
    'TaskRouter',
]
