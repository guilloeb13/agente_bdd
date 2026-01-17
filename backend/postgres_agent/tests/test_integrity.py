"""
Tests for FK Integrity Agent.
"""

import pytest
from unittest.mock import AsyncMock

from postgres_agent.agents.fk_integrity_agent import FKIntegrityAgent
from postgres_agent.manager.memory import SharedMemory


@pytest.mark.asyncio
async def test_integrity_agent_initialization(mock_pg_client):
    """Test FKIntegrityAgent initialization."""
    agent = FKIntegrityAgent(mock_pg_client)
    assert agent.name == "FKIntegrityAgent"


@pytest.mark.asyncio
async def test_analyze_foreign_keys(mock_pg_client, sample_catalog, shared_memory):
    """Test FK analysis."""
    agent = FKIntegrityAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-001")

    # Mock query responses
    agent.runner.execute_safe = AsyncMock(return_value=[])

    results = await agent.analyze(
        catalog=sample_catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    assert 'fks_analyzed' in results
    assert 'relationship_graph' in results


@pytest.mark.asyncio
async def test_detect_missing_fk(mock_pg_client, shared_memory):
    """Test detection of missing FK constraints."""
    catalog = {
        'schemas': {
            'public': {
                'tables': [
                    {
                        'table_name': 'users',
                        'table_type': 'BASE TABLE',
                        'columns': [
                            {'column_name': 'id', 'data_type': 'integer', 'udt_name': 'int4'}
                        ],
                        'primary_key': ['id'],
                        'foreign_keys': []
                    },
                    {
                        'table_name': 'orders',
                        'table_type': 'BASE TABLE',
                        'columns': [
                            {'column_name': 'id', 'data_type': 'integer', 'udt_name': 'int4'},
                            {'column_name': 'user_id', 'data_type': 'integer', 'udt_name': 'int4'}  # Should have FK
                        ],
                        'primary_key': ['id'],
                        'foreign_keys': []  # Missing FK!
                    }
                ],
                'constraints': []  # No FK constraints defined
            }
        }
    }

    agent = FKIntegrityAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-002")
    agent.runner.execute_safe = AsyncMock(return_value=[])

    await agent.analyze(
        catalog=catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    findings = await shared_memory.get_findings()
    missing_fk = [f for f in findings if 'Missing FK' in f['title']]

    assert len(missing_fk) > 0


@pytest.mark.asyncio
async def test_detect_cascade_delete(mock_pg_client, shared_memory):
    """Test detection of CASCADE DELETE rules."""
    catalog = {
        'schemas': {
            'public': {
                'tables': [],
                'constraints': [
                    {
                        'constraint_name': 'orders_user_fk',
                        'table_name': 'orders',
                        'constraint_type': 'FOREIGN KEY',
                        'column_name': 'user_id',
                        'foreign_table_name': 'users',
                        'foreign_column_name': 'id',
                        'delete_rule': 'CASCADE',
                        'update_rule': 'NO ACTION'
                    }
                ]
            }
        }
    }

    agent = FKIntegrityAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-003")
    agent.runner.execute_safe = AsyncMock(return_value=[])

    await agent.analyze(
        catalog=catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    findings = await shared_memory.get_findings()
    cascade_findings = [f for f in findings if 'CASCADE' in f['title']]

    assert len(cascade_findings) > 0


@pytest.mark.asyncio
async def test_relationship_graph_building(mock_pg_client, shared_memory):
    """Test that relationship graph is built correctly."""
    catalog = {
        'schemas': {
            'public': {
                'tables': [],
                'constraints': [
                    {
                        'constraint_name': 'orders_user_fk',
                        'table_name': 'orders',
                        'constraint_type': 'FOREIGN KEY',
                        'column_name': 'user_id',
                        'foreign_table_name': 'users',
                        'foreign_column_name': 'id',
                        'delete_rule': 'NO ACTION',
                        'update_rule': 'NO ACTION'
                    },
                    {
                        'constraint_name': 'items_order_fk',
                        'table_name': 'order_items',
                        'constraint_type': 'FOREIGN KEY',
                        'column_name': 'order_id',
                        'foreign_table_name': 'orders',
                        'foreign_column_name': 'id',
                        'delete_rule': 'CASCADE',
                        'update_rule': 'NO ACTION'
                    }
                ]
            }
        }
    }

    agent = FKIntegrityAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-004")
    agent.runner.execute_safe = AsyncMock(return_value=[])

    results = await agent.analyze(
        catalog=catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    graph = results['relationship_graph']

    assert 'orders' in graph
    assert 'users' in graph['orders']['references']
    assert 'orders' in graph['users']['referenced_by']


@pytest.mark.asyncio
async def test_integrity_recommendations(mock_pg_client, sample_catalog, shared_memory):
    """Test that integrity agent generates recommendations."""
    agent = FKIntegrityAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-005")
    agent.runner.execute_safe = AsyncMock(return_value=[])

    await agent.analyze(
        catalog=sample_catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    recommendations = await shared_memory.get_recommendations()
    integrity_recs = [r for r in recommendations if r['category'] == 'Integrity']

    assert len(integrity_recs) > 0
