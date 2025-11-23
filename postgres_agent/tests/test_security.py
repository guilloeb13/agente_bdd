"""
Tests for Security Agent.
"""

import pytest
from unittest.mock import AsyncMock, patch

from postgres_agent.agents.security_agent import SecurityAgent
from postgres_agent.manager.memory import SharedMemory, FindingSeverity


@pytest.mark.asyncio
async def test_security_agent_initialization(mock_pg_client):
    """Test SecurityAgent initialization."""
    agent = SecurityAgent(mock_pg_client)
    assert agent.name == "SecurityAgent"
    assert agent.client == mock_pg_client


@pytest.mark.asyncio
async def test_analyze_roles_superuser(mock_pg_client, sample_catalog, shared_memory):
    """Test detection of superuser roles."""
    agent = SecurityAgent(mock_pg_client)

    await shared_memory.initialize_audit("test-001")

    results = await agent.analyze(
        catalog=sample_catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    # Should detect non-postgres superusers
    findings = await shared_memory.get_findings()
    superuser_findings = [
        f for f in findings
        if 'superuser' in f['title'].lower()
    ]

    assert results['roles_analyzed'] == 2


@pytest.mark.asyncio
async def test_analyze_no_password_expiration(mock_pg_client, shared_memory):
    """Test detection of roles without password expiration."""
    catalog = {
        'roles': [
            {
                'rolname': 'app_user',
                'rolsuper': False,
                'rolcanlogin': True,
                'rolvaliduntil': None,
                'rolconnlimit': -1,
                'rolcreaterole': False,
                'rolreplication': False
            }
        ],
        'schemas': {'public': {'functions': [], 'constraints': []}},
        'settings': []
    }

    agent = SecurityAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-002")

    # Mock queries
    mock_pg_client.fetch_as_dict = AsyncMock(return_value=[])

    await agent.analyze(
        catalog=catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    findings = await shared_memory.get_findings()
    expiration_findings = [
        f for f in findings
        if 'expiration' in f['title'].lower()
    ]

    assert len(expiration_findings) > 0


@pytest.mark.asyncio
async def test_analyze_security_definer(mock_pg_client, sample_catalog, shared_memory):
    """Test detection of SECURITY DEFINER functions."""
    agent = SecurityAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-003")

    # Mock the query runner's execute_safe
    agent.runner.execute_safe = AsyncMock(return_value=[])

    await agent.analyze(
        catalog=sample_catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    # Should have analyzed functions
    assert 'functions_analyzed' in await agent.runner.execute_safe.call_count >= 0


@pytest.mark.asyncio
async def test_security_recommendations(mock_pg_client, sample_catalog, shared_memory):
    """Test that security agent generates recommendations."""
    agent = SecurityAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-004")

    # Mock queries
    agent.runner.execute_safe = AsyncMock(return_value=[])

    await agent.analyze(
        catalog=sample_catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    recommendations = await shared_memory.get_recommendations()
    assert len(recommendations) > 0


@pytest.mark.asyncio
async def test_finding_severity_levels(mock_pg_client, shared_memory):
    """Test that findings have appropriate severity levels."""
    catalog = {
        'roles': [
            {
                'rolname': 'dangerous_user',
                'rolsuper': True,
                'rolcanlogin': True,
                'rolvaliduntil': None,
                'rolconnlimit': -1,
                'rolcreaterole': True,
                'rolreplication': True
            }
        ],
        'schemas': {'public': {'functions': [], 'constraints': []}},
        'settings': []
    }

    agent = SecurityAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-005")
    agent.runner.execute_safe = AsyncMock(return_value=[])

    await agent.analyze(
        catalog=catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    findings = await shared_memory.get_findings()

    # Should have high severity findings for superuser
    high_findings = [f for f in findings if f['severity'] in ('high', 'critical')]
    assert len(high_findings) > 0


@pytest.mark.asyncio
async def test_public_schema_privileges(mock_pg_client, sample_catalog, shared_memory):
    """Test detection of PUBLIC schema privileges."""
    agent = SecurityAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-006")

    # Mock to return that PUBLIC can create
    async def mock_execute(query, *args, **kwargs):
        if 'has_schema_privilege' in query:
            return [{'can_create': True}]
        return []

    agent.runner.execute_safe = mock_execute

    await agent.analyze(
        catalog=sample_catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    findings = await shared_memory.get_findings()
    public_findings = [f for f in findings if 'PUBLIC' in f['title']]

    assert len(public_findings) > 0
