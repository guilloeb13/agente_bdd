"""
Tests for Agent Manager.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from postgres_agent.manager.agent_manager import AgentManager
from postgres_agent.manager.task_router import TaskType, AgentCapability
from postgres_agent.manager.memory import SharedMemory, TaskStatus


@pytest.mark.asyncio
async def test_agent_manager_initialization(mock_pg_client):
    """Test AgentManager initialization."""
    manager = AgentManager(mock_pg_client)

    assert manager.pg_client == mock_pg_client
    assert manager._is_running is False
    assert len(manager._agents) == 0


@pytest.mark.asyncio
async def test_register_agent(mock_pg_client):
    """Test agent registration."""
    manager = AgentManager(mock_pg_client)

    # Create mock agent
    mock_agent = MagicMock()

    manager.register_agent(AgentCapability.SECURITY, mock_agent)

    assert AgentCapability.SECURITY in manager._agents
    assert 'security' in manager.registered_agents


@pytest.mark.asyncio
async def test_get_status_idle(mock_pg_client):
    """Test status when no audit is running."""
    manager = AgentManager(mock_pg_client)

    status = await manager.get_status()

    assert status['status'] == 'idle'
    assert status['audit_id'] is None


@pytest.mark.asyncio
async def test_shared_memory_operations(shared_memory):
    """Test SharedMemory operations."""
    from postgres_agent.manager.memory import FindingSeverity

    await shared_memory.initialize_audit("test-001")

    # Add finding
    await shared_memory.add_finding(
        agent="TestAgent",
        category="Test",
        title="Test Finding",
        description="Test description",
        severity=FindingSeverity.HIGH,
        affected_objects=["test.table"]
    )

    # Get findings
    findings = await shared_memory.get_findings()
    assert len(findings) == 1
    assert findings[0]['title'] == "Test Finding"
    assert findings[0]['severity'] == 'high'


@pytest.mark.asyncio
async def test_shared_memory_recommendations(shared_memory):
    """Test recommendation storage."""
    await shared_memory.initialize_audit("test-002")

    await shared_memory.add_recommendation(
        agent="TestAgent",
        category="Performance",
        title="Add Index",
        description="Add index for better performance",
        priority=8,
        effort="low",
        impact="high",
        implementation="CREATE INDEX..."
    )

    recommendations = await shared_memory.get_recommendations()
    assert len(recommendations) == 1
    assert recommendations[0]['priority'] == 8


@pytest.mark.asyncio
async def test_shared_memory_summary(shared_memory):
    """Test summary generation."""
    from postgres_agent.manager.memory import FindingSeverity

    await shared_memory.initialize_audit("test-003")

    # Add various findings
    await shared_memory.add_finding(
        agent="SecurityAgent",
        category="Security",
        title="Critical Issue",
        description="Test",
        severity=FindingSeverity.CRITICAL
    )

    await shared_memory.add_finding(
        agent="PerformanceAgent",
        category="Performance",
        title="High Issue",
        description="Test",
        severity=FindingSeverity.HIGH
    )

    summary = await shared_memory.get_summary()

    assert summary['total_findings'] == 2
    assert summary['severity_distribution']['critical'] == 1
    assert summary['severity_distribution']['high'] == 1


@pytest.mark.asyncio
async def test_task_router_execution_plan():
    """Test task router execution planning."""
    from postgres_agent.manager.task_router import TaskRouter

    router = TaskRouter()

    plan = router.get_execution_plan(TaskType.FULL_AUDIT)

    # Should have multiple groups
    assert len(plan) > 0

    # First group should be schema (foundation)
    assert AgentCapability.SCHEMA in plan[0]


@pytest.mark.asyncio
async def test_task_router_agent_registration():
    """Test agent registration in router."""
    from postgres_agent.manager.task_router import TaskRouter

    router = TaskRouter()

    # Register mock agent
    mock_class = MagicMock

    router.register_agent(AgentCapability.SECURITY, mock_class)

    assert router.get_agent_class(AgentCapability.SECURITY) == mock_class


@pytest.mark.asyncio
async def test_task_validation():
    """Test task validation."""
    from postgres_agent.manager.task_router import TaskRouter

    router = TaskRouter()

    # Without registered agents, validation should fail
    is_valid = router.validate_task(TaskType.SECURITY_AUDIT)
    assert is_valid is False

    # Register required agent
    router.register_agent(AgentCapability.SECURITY, MagicMock)

    is_valid = router.validate_task(TaskType.SECURITY_AUDIT)
    assert is_valid is True


@pytest.mark.asyncio
async def test_memory_export_json(shared_memory):
    """Test JSON export."""
    from postgres_agent.manager.memory import FindingSeverity

    await shared_memory.initialize_audit("test-004")

    await shared_memory.add_finding(
        agent="TestAgent",
        category="Test",
        title="Test",
        description="Test",
        severity=FindingSeverity.INFO
    )

    json_export = await shared_memory.export_json()

    import json
    data = json.loads(json_export)

    assert data['audit_id'] == "test-004"
    assert len(data['findings']) == 1


@pytest.mark.asyncio
async def test_memory_clear(shared_memory):
    """Test memory clearing."""
    from postgres_agent.manager.memory import FindingSeverity

    await shared_memory.initialize_audit("test-005")

    await shared_memory.add_finding(
        agent="TestAgent",
        category="Test",
        title="Test",
        description="Test",
        severity=FindingSeverity.LOW
    )

    await shared_memory.clear()

    findings = await shared_memory.get_findings()
    assert len(findings) == 0


@pytest.mark.asyncio
async def test_task_status_tracking(shared_memory):
    """Test task status tracking."""
    await shared_memory.initialize_audit("test-006")

    await shared_memory.set_task_status("task-1", TaskStatus.RUNNING)

    status = await shared_memory.get_task_status("task-1")
    assert status == TaskStatus.RUNNING

    await shared_memory.set_task_status("task-1", TaskStatus.COMPLETED)

    status = await shared_memory.get_task_status("task-1")
    assert status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_agent_result_storage(shared_memory):
    """Test storing agent results."""
    await shared_memory.initialize_audit("test-007")

    result = {
        'tables_analyzed': 10,
        'issues_found': 5
    }

    await shared_memory.store_agent_result("security", result)

    stored = await shared_memory.get_agent_result("security")

    assert stored is not None
    assert stored['result']['tables_analyzed'] == 10


@pytest.mark.asyncio
async def test_catalog_caching(shared_memory):
    """Test catalog data caching."""
    await shared_memory.initialize_audit("test-008")

    catalog_data = {'tables': ['users', 'orders']}

    await shared_memory.cache_catalog('full_catalog', catalog_data)

    cached = await shared_memory.get_cached_catalog('full_catalog')

    assert cached == catalog_data
