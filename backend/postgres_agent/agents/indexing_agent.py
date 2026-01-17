"""
Indexing Agent - Analyzes and recommends indexes.
"""

from typing import Any, Dict, List
from .base_agent import BaseAgent
from ..manager.memory import SharedMemory, FindingSeverity


class IndexingAgent(BaseAgent):
    """
    Analyzes indexes including:
    - Missing indexes
    - Redundant indexes
    - Index type recommendations
    - Partial/covering index opportunities
    """

    async def analyze(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Perform indexing analysis."""
        self.log_info("Starting indexing analysis")

        results = {
            'indexes_analyzed': 0,
            'redundant_indexes': [],
            'missing_indexes': [],
            'recommendations': [],
        }

        for schema in schemas:
            await self._analyze_existing_indexes(catalog, schema, memory, results)
            await self._find_redundant_indexes(schema, memory, results)
            await self._recommend_missing_indexes(catalog, schema, memory, results)
            await self._recommend_specialized_indexes(catalog, schema, memory, results)

        self.log_info(f"Indexing analysis complete. Found {len(results['recommendations'])} recommendations")
        return results

    async def _analyze_existing_indexes(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze existing index definitions."""
        indexes = self.get_indexes_from_catalog(catalog, schema)
        results['indexes_analyzed'] = len(indexes)

        for idx in indexes:
            idx_name = idx.get('indexname', '')
            idx_scan = idx.get('idx_scan', 0)
            idx_size = idx.get('index_size', 0)

            # Check for unused large indexes
            if idx_scan == 0 and idx_size > 10 * 1024 * 1024:  # 10MB
                await self.add_finding(
                    memory,
                    category="Indexes",
                    title=f"Large unused index: {idx_name}",
                    description=f"Index is {idx_size // (1024*1024)}MB but has 0 scans",
                    severity=FindingSeverity.MEDIUM,
                    affected_objects=[f"{schema}.{idx['tablename']}.{idx_name}"],
                    remediation=f"DROP INDEX IF EXISTS {schema}.{idx_name}"
                )

            # Check for inefficient index scans (low fetch ratio)
            if idx_scan > 100 and idx.get('idx_tup_read', 0) > 0:
                fetch_ratio = idx.get('idx_tup_fetch', 0) / idx.get('idx_tup_read', 1)
                if fetch_ratio < 0.1:
                    await self.add_finding(
                        memory,
                        category="Indexes",
                        title=f"Low fetch ratio: {idx_name}",
                        description=f"Only {fetch_ratio*100:.1f}% of index reads result in fetches",
                        severity=FindingSeverity.INFO,
                        affected_objects=[f"{schema}.{idx_name}"],
                        remediation="Review index selectivity and query patterns"
                    )

    async def _find_redundant_indexes(
        self,
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Find redundant/duplicate indexes."""
        query = """
        WITH index_cols AS (
            SELECT
                i.indexrelid,
                i.indrelid,
                c.relname as tablename,
                ic.relname as indexname,
                array_agg(a.attname ORDER BY array_position(i.indkey, a.attnum)) as columns,
                pg_get_indexdef(i.indexrelid) as indexdef
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indrelid
            JOIN pg_class ic ON ic.oid = i.indexrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE n.nspname = $1
            GROUP BY i.indexrelid, i.indrelid, c.relname, ic.relname
        )
        SELECT
            a.tablename,
            a.indexname as redundant_index,
            b.indexname as covering_index,
            a.columns as redundant_cols,
            b.columns as covering_cols
        FROM index_cols a
        JOIN index_cols b ON a.indrelid = b.indrelid
            AND a.indexrelid != b.indexrelid
            AND a.columns <@ b.columns
            AND array_length(a.columns, 1) < array_length(b.columns, 1)
        """
        redundant = await self.runner.execute_safe(query, (schema,), "Find redundant indexes")

        for idx in redundant:
            results['redundant_indexes'].append(idx['redundant_index'])
            await self.add_finding(
                memory,
                category="Indexes",
                title=f"Redundant index: {idx['redundant_index']}",
                description=f"Covered by {idx['covering_index']} ({idx['redundant_cols']} is prefix of {idx['covering_cols']})",
                severity=FindingSeverity.MEDIUM,
                affected_objects=[f"{schema}.{idx['tablename']}.{idx['redundant_index']}"],
                remediation=f"DROP INDEX IF EXISTS {schema}.{idx['redundant_index']}"
            )

    async def _recommend_missing_indexes(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Recommend indexes for FK columns without indexes."""
        query = """
        SELECT
            tc.table_name,
            kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = $1
        AND NOT EXISTS (
            SELECT 1
            FROM pg_index i
            JOIN pg_class c ON c.oid = i.indrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = i.indrelid
                AND a.attnum = i.indkey[0]
            WHERE n.nspname = tc.table_schema
            AND c.relname = tc.table_name
            AND a.attname = kcu.column_name
        )
        """
        missing = await self.runner.execute_safe(query, (schema,), "Find missing FK indexes")

        for col in missing:
            results['missing_indexes'].append(f"{col['table_name']}.{col['column_name']}")
            await self.add_recommendation(
                memory,
                category="Indexes",
                title=f"Add index on FK: {col['table_name']}.{col['column_name']}",
                description="Foreign key column lacks an index, slowing joins and deletes",
                priority=8,
                effort="low",
                impact="high",
                implementation=f"CREATE INDEX idx_{col['table_name']}_{col['column_name']} ON {schema}.{col['table_name']}({col['column_name']})"
            )

    async def _recommend_specialized_indexes(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Recommend specialized index types."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])

            for col in columns:
                col_name = col.get('column_name', '')
                udt_name = col.get('udt_name', '')

                # Recommend GIN for JSONB
                if udt_name == 'jsonb':
                    results['recommendations'].append(f"GIN:{table_name}.{col_name}")
                    await self.add_recommendation(
                        memory,
                        category="Indexes",
                        title=f"GIN index for JSONB: {table_name}.{col_name}",
                        description="JSONB column can benefit from GIN index for containment queries",
                        priority=6,
                        effort="low",
                        impact="medium",
                        implementation=f"CREATE INDEX idx_{table_name}_{col_name}_gin ON {schema}.{table_name} USING GIN ({col_name})"
                    )

                # Recommend GiST for geometric/range types
                if udt_name in ('point', 'box', 'polygon', 'circle', 'tsrange', 'tstzrange', 'int4range'):
                    results['recommendations'].append(f"GiST:{table_name}.{col_name}")
                    await self.add_recommendation(
                        memory,
                        category="Indexes",
                        title=f"GiST index: {table_name}.{col_name}",
                        description=f"{udt_name} type benefits from GiST index",
                        priority=5,
                        effort="low",
                        impact="medium",
                        implementation=f"CREATE INDEX idx_{table_name}_{col_name}_gist ON {schema}.{table_name} USING GiST ({col_name})"
                    )

                # Recommend text search indexes
                if udt_name in ('text', 'varchar') and col_name in ('name', 'title', 'description', 'content'):
                    results['recommendations'].append(f"TRGM:{table_name}.{col_name}")
                    await self.add_recommendation(
                        memory,
                        category="Indexes",
                        title=f"Trigram index: {table_name}.{col_name}",
                        description="Text column can use trigram index for LIKE searches",
                        priority=4,
                        effort="low",
                        impact="medium",
                        implementation=f"CREATE INDEX idx_{table_name}_{col_name}_trgm ON {schema}.{table_name} USING GIN ({col_name} gin_trgm_ops)"
                    )
