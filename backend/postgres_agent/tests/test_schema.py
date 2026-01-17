"""
Tests for Schema Agent.
"""

import pytest
from unittest.mock import AsyncMock

from postgres_agent.agents.schema_agent import SchemaAgent
from postgres_agent.manager.memory import SharedMemory


@pytest.mark.asyncio
async def test_schema_agent_initialization(mock_pg_client):
    """Test SchemaAgent initialization."""
    agent = SchemaAgent(mock_pg_client)
    assert agent.name == "SchemaAgent"


@pytest.mark.asyncio
async def test_analyze_tables(mock_pg_client, sample_catalog, shared_memory):
    """Test basic table analysis."""
    agent = SchemaAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-001")

    results = await agent.analyze(
        catalog=sample_catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    assert results['tables_analyzed'] == 2
    assert results['columns_analyzed'] > 0
    assert 'public' in results['schema_summary']


@pytest.mark.asyncio
async def test_detect_missing_primary_key(mock_pg_client, shared_memory):
    """Test detection of tables without primary keys."""
    catalog = {
        'schemas': {
            'public': {
                'tables': [
                    {
                        'table_name': 'no_pk_table',
                        'table_type': 'BASE TABLE',
                        'total_size': 1000,
                        'row_count': 100,
                        'columns': [
                            {
                                'column_name': 'data',
                                'data_type': 'text',
                                'udt_name': 'text',
                                'is_nullable': 'YES'
                            }
                        ],
                        'primary_key': [],  # No primary key
                        'foreign_keys': [],
                        'stats': {}
                    }
                ]
            }
        }
    }

    agent = SchemaAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-002")

    await agent.analyze(
        catalog=catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    findings = await shared_memory.get_findings()
    pk_findings = [f for f in findings if 'primary key' in f['title'].lower()]

    assert len(pk_findings) > 0
    assert pk_findings[0]['severity'] == 'high'


@pytest.mark.asyncio
async def test_detect_timestamp_without_timezone(mock_pg_client, shared_memory):
    """Test detection of timestamp without timezone."""
    catalog = {
        'schemas': {
            'public': {
                'tables': [
                    {
                        'table_name': 'events',
                        'table_type': 'BASE TABLE',
                        'total_size': 1000,
                        'row_count': 100,
                        'columns': [
                            {
                                'column_name': 'id',
                                'data_type': 'integer',
                                'udt_name': 'int4',
                                'is_nullable': 'NO'
                            },
                            {
                                'column_name': 'event_time',
                                'data_type': 'timestamp without time zone',
                                'udt_name': 'timestamp',
                                'is_nullable': 'YES'
                            }
                        ],
                        'primary_key': ['id'],
                        'foreign_keys': [],
                        'stats': {}
                    }
                ]
            }
        }
    }

    agent = SchemaAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-003")

    await agent.analyze(
        catalog=catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    findings = await shared_memory.get_findings()
    tz_findings = [f for f in findings if 'timezone' in f['title'].lower()]

    assert len(tz_findings) > 0


@pytest.mark.asyncio
async def test_detect_wide_table(mock_pg_client, shared_memory):
    """Test detection of wide tables."""
    # Create table with 35 columns
    columns = []
    for i in range(35):
        columns.append({
            'column_name': f'col_{i}',
            'data_type': 'text',
            'udt_name': 'text',
            'is_nullable': 'YES'
        })

    catalog = {
        'schemas': {
            'public': {
                'tables': [
                    {
                        'table_name': 'wide_table',
                        'table_type': 'BASE TABLE',
                        'total_size': 100000,
                        'row_count': 1000,
                        'columns': columns,
                        'primary_key': ['col_0'],
                        'foreign_keys': [],
                        'stats': {}
                    }
                ]
            }
        }
    }

    agent = SchemaAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-004")

    await agent.analyze(
        catalog=catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    findings = await shared_memory.get_findings()
    wide_findings = [f for f in findings if 'wide' in f['title'].lower()]

    assert len(wide_findings) > 0


@pytest.mark.asyncio
async def test_detect_mixed_case_names(mock_pg_client, shared_memory):
    """Test detection of mixed case naming."""
    catalog = {
        'schemas': {
            'public': {
                'tables': [
                    {
                        'table_name': 'UserAccounts',  # Mixed case
                        'table_type': 'BASE TABLE',
                        'total_size': 1000,
                        'row_count': 100,
                        'columns': [
                            {
                                'column_name': 'userId',  # Mixed case
                                'data_type': 'integer',
                                'udt_name': 'int4',
                                'is_nullable': 'NO'
                            }
                        ],
                        'primary_key': ['userId'],
                        'foreign_keys': [],
                        'stats': {}
                    }
                ]
            }
        }
    }

    agent = SchemaAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-005")

    await agent.analyze(
        catalog=catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    findings = await shared_memory.get_findings()
    naming_findings = [f for f in findings if 'case' in f['title'].lower()]

    assert len(naming_findings) >= 2  # Table and column


@pytest.mark.asyncio
async def test_json_column_detection(mock_pg_client, shared_memory):
    """Test detection of JSON columns."""
    catalog = {
        'schemas': {
            'public': {
                'tables': [
                    {
                        'table_name': 'documents',
                        'table_type': 'BASE TABLE',
                        'total_size': 1000,
                        'row_count': 100,
                        'columns': [
                            {
                                'column_name': 'id',
                                'data_type': 'integer',
                                'udt_name': 'int4',
                                'is_nullable': 'NO'
                            },
                            {
                                'column_name': 'data',
                                'data_type': 'jsonb',
                                'udt_name': 'jsonb',
                                'is_nullable': 'YES'
                            }
                        ],
                        'primary_key': ['id'],
                        'foreign_keys': [],
                        'stats': {}
                    }
                ]
            }
        }
    }

    agent = SchemaAgent(mock_pg_client)
    await shared_memory.initialize_audit("test-006")

    await agent.analyze(
        catalog=catalog,
        schemas=['public'],
        memory=shared_memory,
        options={}
    )

    findings = await shared_memory.get_findings()
    json_findings = [f for f in findings if 'json' in f['title'].lower()]

    assert len(json_findings) > 0
