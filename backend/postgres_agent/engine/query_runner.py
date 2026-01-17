"""
Query Runner with sanitization and safe execution patterns.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from .pg_client import PGClient

logger = logging.getLogger(__name__)


class QueryRunner:
    """Safe query execution with sanitization and auditing."""

    # Forbidden patterns for read-only auditing
    FORBIDDEN_PATTERNS = [
        r'\bINSERT\b',
        r'\bUPDATE\b',
        r'\bDELETE\b',
        r'\bDROP\b',
        r'\bTRUNCATE\b',
        r'\bALTER\b',
        r'\bCREATE\b',
        r'\bGRANT\b',
        r'\bREVOKE\b',
        r'\bVACUUM\b',
        r'\bREINDEX\b',
        r'\bCLUSTER\b',
        r'\bCOPY\b',
        r'\bEXECUTE\b',
        r'\bCALL\b',
    ]

    def __init__(self, client: PGClient):
        self.client = client
        self._query_log: List[Dict[str, Any]] = []

    def _is_safe_query(self, query: str) -> Tuple[bool, str]:
        """Check if query is safe for read-only auditing."""
        query_upper = query.upper().strip()

        # Remove comments
        query_clean = re.sub(r'--.*$', '', query_upper, flags=re.MULTILINE)
        query_clean = re.sub(r'/\*.*?\*/', '', query_clean, flags=re.DOTALL)

        for pattern in self.FORBIDDEN_PATTERNS:
            if re.search(pattern, query_clean, re.IGNORECASE):
                return False, f"Forbidden pattern detected: {pattern}"

        # Must start with SELECT, WITH, EXPLAIN, or SHOW
        allowed_starts = ['SELECT', 'WITH', 'EXPLAIN', 'SHOW', 'TABLE']
        if not any(query_clean.strip().startswith(start) for start in allowed_starts):
            return False, f"Query must start with: {', '.join(allowed_starts)}"

        return True, "Query is safe"

    async def execute_safe(
        self,
        query: str,
        params: Optional[Tuple] = None,
        description: str = ""
    ) -> List[Dict[str, Any]]:
        """Execute a safe read-only query."""
        is_safe, message = self._is_safe_query(query)

        if not is_safe:
            logger.warning(f"Blocked unsafe query: {message}")
            raise ValueError(f"Query blocked: {message}")

        try:
            if params:
                results = await self.client.fetch_as_dict(query, *params)
            else:
                results = await self.client.fetch_as_dict(query)

            self._log_query(query, description, len(results), None)
            return results

        except Exception as e:
            self._log_query(query, description, 0, str(e))
            logger.error(f"Query execution failed: {e}")
            raise

    def _log_query(
        self,
        query: str,
        description: str,
        row_count: int,
        error: Optional[str]
    ) -> None:
        """Log query execution for auditing."""
        self._query_log.append({
            'query': query[:500],  # Truncate long queries
            'description': description,
            'row_count': row_count,
            'error': error,
        })

    def get_query_log(self) -> List[Dict[str, Any]]:
        """Get query execution log."""
        return self._query_log.copy()

    def clear_log(self) -> None:
        """Clear query execution log."""
        self._query_log = []

    # Common catalog queries
    async def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Get all schemas in the database."""
        query = """
        SELECT
            schema_name,
            schema_owner,
            default_character_set_catalog,
            default_character_set_schema,
            default_character_set_name
        FROM information_schema.schemata
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
        ORDER BY schema_name
        """
        return await self.execute_safe(query, description="Get all schemas")

    async def get_all_tables(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get all tables in a schema."""
        query = """
        SELECT
            t.table_schema,
            t.table_name,
            t.table_type,
            pg_catalog.obj_description(c.oid) as table_comment,
            pg_total_relation_size(c.oid) as total_size,
            pg_table_size(c.oid) as table_size,
            pg_indexes_size(c.oid) as indexes_size,
            (SELECT count(*) FROM pg_catalog.pg_indexes WHERE tablename = t.table_name) as index_count
        FROM information_schema.tables t
        JOIN pg_catalog.pg_class c ON c.relname = t.table_name
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace AND n.nspname = t.table_schema
        WHERE t.table_schema = $1
        AND t.table_type IN ('BASE TABLE', 'VIEW')
        ORDER BY t.table_name
        """
        return await self.execute_safe(query, (schema,), "Get all tables")

    async def get_table_columns(self, table_name: str, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get all columns for a table."""
        query = """
        SELECT
            c.column_name,
            c.data_type,
            c.udt_name,
            c.character_maximum_length,
            c.numeric_precision,
            c.numeric_scale,
            c.is_nullable,
            c.column_default,
            c.ordinal_position,
            pg_catalog.col_description(t.oid, c.ordinal_position) as column_comment
        FROM information_schema.columns c
        JOIN pg_catalog.pg_class t ON t.relname = c.table_name
        JOIN pg_catalog.pg_namespace n ON n.oid = t.relnamespace AND n.nspname = c.table_schema
        WHERE c.table_schema = $1 AND c.table_name = $2
        ORDER BY c.ordinal_position
        """
        return await self.execute_safe(query, (schema, table_name), f"Get columns for {table_name}")

    async def get_constraints(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get all constraints in a schema."""
        query = """
        SELECT
            tc.constraint_name,
            tc.table_schema,
            tc.table_name,
            tc.constraint_type,
            kcu.column_name,
            ccu.table_schema AS foreign_table_schema,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.update_rule,
            rc.delete_rule
        FROM information_schema.table_constraints tc
        LEFT JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        LEFT JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        LEFT JOIN information_schema.referential_constraints rc
            ON tc.constraint_name = rc.constraint_name
            AND tc.table_schema = rc.constraint_schema
        WHERE tc.table_schema = $1
        ORDER BY tc.table_name, tc.constraint_type
        """
        return await self.execute_safe(query, (schema,), "Get all constraints")

    async def get_indexes(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get all indexes in a schema."""
        query = """
        SELECT
            schemaname,
            tablename,
            indexname,
            indexdef,
            pg_relation_size(indexrelid) as index_size,
            idx_scan,
            idx_tup_read,
            idx_tup_fetch
        FROM pg_catalog.pg_indexes
        JOIN pg_catalog.pg_stat_user_indexes USING (schemaname, indexrelname)
        WHERE schemaname = $1
        ORDER BY tablename, indexname
        """
        return await self.execute_safe(query, (schema,), "Get all indexes")

    async def get_functions(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get all functions in a schema."""
        query = """
        SELECT
            p.proname as function_name,
            pg_catalog.pg_get_function_arguments(p.oid) as arguments,
            pg_catalog.pg_get_function_result(p.oid) as return_type,
            p.prosrc as source_code,
            p.prosecdef as security_definer,
            p.provolatile as volatility,
            l.lanname as language,
            pg_catalog.obj_description(p.oid) as comment
        FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        JOIN pg_catalog.pg_language l ON l.oid = p.prolang
        WHERE n.nspname = $1
        AND p.prokind = 'f'
        ORDER BY p.proname
        """
        return await self.execute_safe(query, (schema,), "Get all functions")

    async def get_triggers(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get all triggers in a schema."""
        query = """
        SELECT
            t.trigger_name,
            t.event_manipulation,
            t.event_object_schema,
            t.event_object_table,
            t.action_timing,
            t.action_statement,
            t.action_orientation
        FROM information_schema.triggers t
        WHERE t.trigger_schema = $1
        ORDER BY t.event_object_table, t.trigger_name
        """
        return await self.execute_safe(query, (schema,), "Get all triggers")

    async def get_views(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get all views in a schema."""
        query = """
        SELECT
            v.table_name as view_name,
            v.view_definition,
            v.check_option,
            v.is_updatable,
            v.is_insertable_into
        FROM information_schema.views v
        WHERE v.table_schema = $1
        ORDER BY v.table_name
        """
        return await self.execute_safe(query, (schema,), "Get all views")

    async def get_materialized_views(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get all materialized views in a schema."""
        query = """
        SELECT
            schemaname,
            matviewname,
            matviewowner,
            tablespace,
            hasindexes,
            ispopulated,
            definition
        FROM pg_catalog.pg_matviews
        WHERE schemaname = $1
        ORDER BY matviewname
        """
        return await self.execute_safe(query, (schema,), "Get all materialized views")

    async def get_sequences(self, schema: str = 'public') -> List[Dict[str, Any]]:
        """Get all sequences in a schema."""
        query = """
        SELECT
            sequence_schema,
            sequence_name,
            data_type,
            start_value,
            minimum_value,
            maximum_value,
            increment,
            cycle_option
        FROM information_schema.sequences
        WHERE sequence_schema = $1
        ORDER BY sequence_name
        """
        return await self.execute_safe(query, (schema,), "Get all sequences")

    async def explain_query(self, query: str, analyze: bool = False) -> List[Dict[str, Any]]:
        """Get execution plan for a query."""
        explain_prefix = "EXPLAIN (FORMAT JSON, VERBOSE, COSTS"
        if analyze:
            explain_prefix += ", ANALYZE, BUFFERS"
        explain_prefix += ")"

        explain_query = f"{explain_prefix} {query}"
        return await self.execute_safe(explain_query, description="Explain query")

    async def get_table_stats(self, table_name: str, schema: str = 'public') -> Dict[str, Any]:
        """Get statistics for a table."""
        query = """
        SELECT
            relname as table_name,
            n_live_tup as live_rows,
            n_dead_tup as dead_rows,
            n_mod_since_analyze as mods_since_analyze,
            last_vacuum,
            last_autovacuum,
            last_analyze,
            last_autoanalyze,
            vacuum_count,
            autovacuum_count,
            analyze_count,
            autoanalyze_count
        FROM pg_stat_user_tables
        WHERE schemaname = $1 AND relname = $2
        """
        results = await self.execute_safe(query, (schema, table_name), f"Get stats for {table_name}")
        return results[0] if results else {}
