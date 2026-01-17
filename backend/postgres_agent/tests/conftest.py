"""
Pytest fixtures and configuration for PMA-Agent tests.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Any, Dict, List

from postgres_agent.engine import PGClient
from postgres_agent.manager.memory import SharedMemory


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_pg_client():
    """Create a mock PostgreSQL client."""
    client = AsyncMock(spec=PGClient)
    client.fetch = AsyncMock(return_value=[])
    client.fetchrow = AsyncMock(return_value=None)
    client.fetchval = AsyncMock(return_value=None)
    client.fetch_as_dict = AsyncMock(return_value=[])
    client.test_connection = AsyncMock(return_value=True)
    return client


@pytest.fixture
def shared_memory():
    """Create shared memory instance for tests."""
    return SharedMemory()


@pytest.fixture
def sample_catalog():
    """Create sample catalog data for testing."""
    return {
        'database_info': {
            'database_name': 'testdb',
            'size_bytes': 1000000,
            'pg_version': 'PostgreSQL 15.0'
        },
        'schemas': {
            'public': {
                'tables': [
                    {
                        'table_name': 'users',
                        'table_type': 'BASE TABLE',
                        'total_size': 100000,
                        'row_count': 1000,
                        'columns': [
                            {
                                'column_name': 'id',
                                'data_type': 'integer',
                                'udt_name': 'int4',
                                'is_nullable': 'NO',
                                'column_default': "nextval('users_id_seq')"
                            },
                            {
                                'column_name': 'email',
                                'data_type': 'character varying',
                                'udt_name': 'varchar',
                                'is_nullable': 'NO',
                                'character_maximum_length': 255
                            },
                            {
                                'column_name': 'created_at',
                                'data_type': 'timestamp without time zone',
                                'udt_name': 'timestamp',
                                'is_nullable': 'YES'
                            }
                        ],
                        'primary_key': ['id'],
                        'foreign_keys': [],
                        'stats': {'n_live_tup': 1000, 'n_dead_tup': 10}
                    },
                    {
                        'table_name': 'orders',
                        'table_type': 'BASE TABLE',
                        'total_size': 50000,
                        'row_count': 500,
                        'columns': [
                            {
                                'column_name': 'id',
                                'data_type': 'integer',
                                'udt_name': 'int4',
                                'is_nullable': 'NO'
                            },
                            {
                                'column_name': 'user_id',
                                'data_type': 'integer',
                                'udt_name': 'int4',
                                'is_nullable': 'NO'
                            },
                            {
                                'column_name': 'status',
                                'data_type': 'character varying',
                                'udt_name': 'varchar',
                                'is_nullable': 'YES'
                            }
                        ],
                        'primary_key': ['id'],
                        'foreign_keys': [
                            {
                                'column_name': 'user_id',
                                'foreign_table': 'users',
                                'foreign_column': 'id'
                            }
                        ],
                        'stats': {'n_live_tup': 500, 'n_dead_tup': 5}
                    }
                ],
                'views': [],
                'materialized_views': [],
                'functions': [
                    {
                        'function_name': 'get_user',
                        'arguments': 'user_id integer',
                        'return_type': 'users',
                        'security_definer': True,
                        'source_code': 'SELECT * FROM users WHERE id = user_id',
                        'language': 'sql'
                    }
                ],
                'triggers': [],
                'sequences': [],
                'constraints': [
                    {
                        'constraint_name': 'users_pkey',
                        'table_name': 'users',
                        'constraint_type': 'PRIMARY KEY',
                        'column_name': 'id'
                    },
                    {
                        'constraint_name': 'orders_user_id_fkey',
                        'table_name': 'orders',
                        'constraint_type': 'FOREIGN KEY',
                        'column_name': 'user_id',
                        'foreign_table_name': 'users',
                        'foreign_column_name': 'id',
                        'delete_rule': 'NO ACTION',
                        'update_rule': 'NO ACTION'
                    }
                ],
                'indexes': [
                    {
                        'tablename': 'users',
                        'indexname': 'users_pkey',
                        'indexdef': 'CREATE UNIQUE INDEX users_pkey ON users USING btree (id)',
                        'idx_scan': 1000,
                        'idx_tup_read': 1000,
                        'idx_tup_fetch': 950,
                        'index_size': 8192
                    }
                ],
                'types': [],
                'domains': []
            }
        },
        'roles': [
            {
                'rolname': 'postgres',
                'rolsuper': True,
                'rolinherit': True,
                'rolcreaterole': True,
                'rolcreatedb': True,
                'rolcanlogin': True,
                'rolreplication': True,
                'rolconnlimit': -1,
                'rolvaliduntil': None,
                'rolbypassrls': True,
                'member_of': []
            },
            {
                'rolname': 'app_user',
                'rolsuper': False,
                'rolinherit': True,
                'rolcreaterole': False,
                'rolcreatedb': False,
                'rolcanlogin': True,
                'rolreplication': False,
                'rolconnlimit': 10,
                'rolvaliduntil': None,
                'rolbypassrls': False,
                'member_of': []
            }
        ],
        'extensions': [],
        'tablespaces': [],
        'settings': []
    }


@pytest.fixture
def sample_findings():
    """Sample findings for testing."""
    return [
        {
            'id': 1,
            'agent': 'SecurityAgent',
            'category': 'Roles',
            'title': 'Test finding',
            'description': 'Test description',
            'severity': 'high',
            'affected_objects': ['public.users'],
            'remediation': 'Fix it',
            'metadata': {},
            'timestamp': '2024-01-01T00:00:00'
        }
    ]
