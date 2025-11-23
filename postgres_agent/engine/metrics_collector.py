"""
Metrics Collector for comprehensive PostgreSQL catalog extraction.
"""

import logging
from typing import Any, Dict, List, Optional
from .pg_client import PGClient
from .query_runner import QueryRunner

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collect comprehensive database metrics and metadata."""

    def __init__(self, client: PGClient):
        self.client = client
        self.runner = QueryRunner(client)

    async def collect_full_catalog(self, schemas: List[str] = None) -> Dict[str, Any]:
        """Collect complete database catalog information."""
        if schemas is None:
            schemas = ['public']

        catalog = {
            'database_info': await self.get_database_info(),
            'schemas': {},
            'roles': await self.get_roles(),
            'extensions': await self.get_extensions(),
            'tablespaces': await self.get_tablespaces(),
            'settings': await self.get_relevant_settings(),
        }

        for schema in schemas:
            catalog['schemas'][schema] = await self.collect_schema_catalog(schema)

        return catalog

    async def get_database_info(self) -> Dict[str, Any]:
        """Get general database information."""
        query = """
        SELECT
            current_database() as database_name,
            current_user as current_user,
            pg_catalog.pg_database_size(current_database()) as size_bytes,
            pg_catalog.pg_size_pretty(pg_catalog.pg_database_size(current_database())) as size_pretty,
            (SELECT count(*) FROM pg_catalog.pg_stat_activity WHERE datname = current_database()) as active_connections,
            version() as pg_version,
            pg_postmaster_start_time() as server_start_time,
            (SELECT setting FROM pg_settings WHERE name = 'server_encoding') as encoding,
            (SELECT setting FROM pg_settings WHERE name = 'lc_collate') as collation
        """
        results = await self.runner.execute_safe(query, description="Get database info")
        return results[0] if results else {}

    async def collect_schema_catalog(self, schema: str) -> Dict[str, Any]:
        """Collect complete catalog for a schema."""
        return {
            'tables': await self.get_tables_detailed(schema),
            'views': await self.runner.get_views(schema),
            'materialized_views': await self.runner.get_materialized_views(schema),
            'functions': await self.runner.get_functions(schema),
            'triggers': await self.runner.get_triggers(schema),
            'sequences': await self.runner.get_sequences(schema),
            'constraints': await self.runner.get_constraints(schema),
            'indexes': await self.runner.get_indexes(schema),
            'types': await self.get_custom_types(schema),
            'domains': await self.get_domains(schema),
        }

    async def get_tables_detailed(self, schema: str) -> List[Dict[str, Any]]:
        """Get detailed table information including columns."""
        tables = await self.runner.get_all_tables(schema)

        for table in tables:
            table_name = table['table_name']
            table['columns'] = await self.runner.get_table_columns(table_name, schema)
            table['stats'] = await self.runner.get_table_stats(table_name, schema)
            table['primary_key'] = await self.get_primary_key(table_name, schema)
            table['foreign_keys'] = await self.get_foreign_keys(table_name, schema)
            table['row_count'] = await self.get_row_count(table_name, schema)

        return tables

    async def get_primary_key(self, table_name: str, schema: str = 'public') -> List[str]:
        """Get primary key columns for a table."""
        query = """
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        JOIN pg_class c ON c.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE i.indisprimary
        AND n.nspname = $1
        AND c.relname = $2
        ORDER BY array_position(i.indkey, a.attnum)
        """
        results = await self.runner.execute_safe(query, (schema, table_name), f"Get PK for {table_name}")
        return [r['attname'] for r in results]

    async def get_foreign_keys(self, table_name: str, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get foreign key relationships for a table."""
        query = """
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_schema AS foreign_schema,
            ccu.table_name AS foreign_table,
            ccu.column_name AS foreign_column,
            rc.update_rule,
            rc.delete_rule
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
        JOIN information_schema.referential_constraints rc
            ON tc.constraint_name = rc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = $1
        AND tc.table_name = $2
        """
        return await self.runner.execute_safe(query, (schema, table_name), f"Get FKs for {table_name}")

    async def get_row_count(self, table_name: str, schema: str = 'public') -> int:
        """Get estimated row count for a table (fast)."""
        query = """
        SELECT reltuples::bigint as estimate
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = $1 AND c.relname = $2
        """
        results = await self.runner.execute_safe(query, (schema, table_name), f"Get row count for {table_name}")
        return results[0]['estimate'] if results else 0

    async def get_roles(self) -> List[Dict[str, Any]]:
        """Get all database roles and their attributes."""
        query = """
        SELECT
            r.rolname,
            r.rolsuper,
            r.rolinherit,
            r.rolcreaterole,
            r.rolcreatedb,
            r.rolcanlogin,
            r.rolreplication,
            r.rolconnlimit,
            r.rolvaliduntil,
            r.rolbypassrls,
            ARRAY(
                SELECT b.rolname
                FROM pg_catalog.pg_auth_members m
                JOIN pg_catalog.pg_roles b ON m.roleid = b.oid
                WHERE m.member = r.oid
            ) as member_of
        FROM pg_catalog.pg_roles r
        WHERE r.rolname !~ '^pg_'
        ORDER BY r.rolname
        """
        return await self.runner.execute_safe(query, description="Get all roles")

    async def get_extensions(self) -> List[Dict[str, Any]]:
        """Get installed extensions."""
        query = """
        SELECT
            extname,
            extversion,
            extrelocatable,
            extnamespace::regnamespace::text as schema
        FROM pg_extension
        ORDER BY extname
        """
        return await self.runner.execute_safe(query, description="Get extensions")

    async def get_tablespaces(self) -> List[Dict[str, Any]]:
        """Get tablespace information."""
        query = """
        SELECT
            spcname as name,
            pg_catalog.pg_get_userbyid(spcowner) as owner,
            pg_catalog.pg_tablespace_location(oid) as location,
            pg_tablespace_size(spcname) as size_bytes
        FROM pg_tablespace
        ORDER BY spcname
        """
        return await self.runner.execute_safe(query, description="Get tablespaces")

    async def get_relevant_settings(self) -> List[Dict[str, Any]]:
        """Get security and performance relevant settings."""
        query = """
        SELECT name, setting, unit, category, short_desc
        FROM pg_settings
        WHERE category IN (
            'Autovacuum',
            'Client Connection Defaults / Statement Behavior',
            'Connections and Authentication / Authentication',
            'Connections and Authentication / SSL',
            'Lock Management',
            'Query Tuning / Planner Cost Constants',
            'Query Tuning / Planner Method Configuration',
            'Reporting and Logging / What to Log',
            'Resource Usage / Memory',
            'Write-Ahead Log / Settings'
        )
        ORDER BY category, name
        """
        return await self.runner.execute_safe(query, description="Get relevant settings")

    async def get_custom_types(self, schema: str) -> List[Dict[str, Any]]:
        """Get custom types in a schema."""
        query = """
        SELECT
            t.typname as type_name,
            t.typtype as type_type,
            pg_catalog.format_type(t.typbasetype, t.typtypmod) as base_type,
            pg_catalog.obj_description(t.oid, 'pg_type') as description
        FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = $1
        AND t.typtype IN ('c', 'd', 'e', 'r')
        AND NOT EXISTS (
            SELECT 1 FROM pg_class WHERE reltype = t.oid
        )
        ORDER BY t.typname
        """
        return await self.runner.execute_safe(query, (schema,), f"Get custom types in {schema}")

    async def get_domains(self, schema: str) -> List[Dict[str, Any]]:
        """Get domains in a schema."""
        query = """
        SELECT
            domain_name,
            data_type,
            character_maximum_length,
            domain_default,
            is_nullable
        FROM information_schema.domains
        WHERE domain_schema = $1
        ORDER BY domain_name
        """
        return await self.runner.execute_safe(query, (schema,), f"Get domains in {schema}")

    async def get_table_permissions(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get table-level permissions."""
        query = """
        SELECT
            grantee,
            table_schema,
            table_name,
            privilege_type,
            is_grantable
        FROM information_schema.table_privileges
        WHERE table_schema = $1
        ORDER BY table_name, grantee, privilege_type
        """
        return await self.runner.execute_safe(query, (schema,), "Get table permissions")

    async def get_column_permissions(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get column-level permissions."""
        query = """
        SELECT
            grantee,
            table_schema,
            table_name,
            column_name,
            privilege_type,
            is_grantable
        FROM information_schema.column_privileges
        WHERE table_schema = $1
        ORDER BY table_name, column_name, grantee
        """
        return await self.runner.execute_safe(query, (schema,), "Get column permissions")

    async def get_table_bloat(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """Estimate table bloat."""
        query = """
        SELECT
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) as total_size,
            n_dead_tup,
            n_live_tup,
            CASE
                WHEN n_live_tup > 0
                THEN round(100.0 * n_dead_tup / (n_live_tup + n_dead_tup), 2)
                ELSE 0
            END as dead_tuple_percent,
            last_autovacuum
        FROM pg_stat_user_tables
        WHERE schemaname = $1
        AND n_dead_tup > 0
        ORDER BY n_dead_tup DESC
        """
        return await self.runner.execute_safe(query, (schema,), "Get table bloat estimates")

    async def get_index_usage(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get index usage statistics."""
        query = """
        SELECT
            schemaname,
            relname as table_name,
            indexrelname as index_name,
            idx_scan,
            idx_tup_read,
            idx_tup_fetch,
            pg_size_pretty(pg_relation_size(indexrelid)) as index_size
        FROM pg_stat_user_indexes
        WHERE schemaname = $1
        ORDER BY idx_scan
        """
        return await self.runner.execute_safe(query, (schema,), "Get index usage")

    async def get_sequential_scans(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get tables with high sequential scans."""
        query = """
        SELECT
            schemaname,
            relname as table_name,
            seq_scan,
            seq_tup_read,
            idx_scan,
            CASE
                WHEN (seq_scan + idx_scan) > 0
                THEN round(100.0 * seq_scan / (seq_scan + idx_scan), 2)
                ELSE 0
            END as seq_scan_percent,
            n_live_tup as row_count
        FROM pg_stat_user_tables
        WHERE schemaname = $1
        AND seq_scan > 0
        ORDER BY seq_scan DESC
        """
        return await self.runner.execute_safe(query, (schema,), "Get sequential scans")

    async def get_long_running_queries(self) -> List[Dict[str, Any]]:
        """Get currently running queries."""
        query = """
        SELECT
            pid,
            usename,
            application_name,
            client_addr,
            state,
            query_start,
            now() - query_start as duration,
            query
        FROM pg_stat_activity
        WHERE state != 'idle'
        AND query NOT LIKE '%pg_stat_activity%'
        ORDER BY query_start
        """
        return await self.runner.execute_safe(query, description="Get running queries")

    async def get_lock_info(self) -> List[Dict[str, Any]]:
        """Get current lock information."""
        query = """
        SELECT
            l.locktype,
            l.relation::regclass as relation,
            l.mode,
            l.granted,
            l.pid,
            a.usename,
            a.query
        FROM pg_locks l
        JOIN pg_stat_activity a ON l.pid = a.pid
        WHERE l.relation IS NOT NULL
        ORDER BY l.relation
        """
        return await self.runner.execute_safe(query, description="Get lock info")

    async def get_cache_hit_ratio(self) -> Dict[str, Any]:
        """Get buffer cache hit ratio."""
        query = """
        SELECT
            sum(heap_blks_read) as heap_read,
            sum(heap_blks_hit) as heap_hit,
            CASE
                WHEN sum(heap_blks_hit) + sum(heap_blks_read) > 0
                THEN round(100.0 * sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)), 2)
                ELSE 100
            END as cache_hit_ratio
        FROM pg_statio_user_tables
        """
        results = await self.runner.execute_safe(query, description="Get cache hit ratio")
        return results[0] if results else {}

    async def get_replication_status(self) -> List[Dict[str, Any]]:
        """Get replication status if applicable."""
        query = """
        SELECT
            client_addr,
            state,
            sent_lsn,
            write_lsn,
            flush_lsn,
            replay_lsn,
            sync_state
        FROM pg_stat_replication
        """
        return await self.runner.execute_safe(query, description="Get replication status")
