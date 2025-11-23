"""
Performance Agent - Analyzes database performance issues.
"""

from typing import Any, Dict, List
from .base_agent import BaseAgent
from ..manager.memory import SharedMemory, FindingSeverity


class PerformanceAgent(BaseAgent):
    """
    Analyzes performance including:
    - Sequential scans
    - Expensive joins
    - Slow functions
    - Table bloat
    - Cache efficiency
    """

    async def analyze(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Perform performance analysis."""
        self.log_info("Starting performance analysis")

        results = {
            'tables_analyzed': 0,
            'seq_scan_issues': [],
            'bloat_issues': [],
            'cache_stats': {},
            'slow_queries': [],
        }

        for schema in schemas:
            await self._analyze_sequential_scans(schema, memory, results)
            await self._analyze_table_bloat(schema, memory, results)
            await self._analyze_index_usage(schema, memory, results)

        await self._analyze_cache_performance(memory, results)
        await self._analyze_vacuum_status(memory, results)
        await self._analyze_connection_stats(memory, results)

        self.log_info(f"Performance analysis complete. Found {len(results['seq_scan_issues'])} issues")
        return results

    async def _analyze_sequential_scans(
        self,
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Identify tables with excessive sequential scans."""
        query = """
        SELECT
            schemaname,
            relname,
            seq_scan,
            seq_tup_read,
            idx_scan,
            n_live_tup,
            CASE
                WHEN (seq_scan + idx_scan) > 0
                THEN round(100.0 * seq_scan / (seq_scan + idx_scan), 2)
                ELSE 0
            END as seq_scan_pct
        FROM pg_stat_user_tables
        WHERE schemaname = $1
        AND seq_scan > 100
        AND n_live_tup > 10000
        ORDER BY seq_scan_pct DESC, seq_scan DESC
        LIMIT 20
        """
        tables = await self.runner.execute_safe(query, (schema,), "Get sequential scans")

        for table in tables:
            results['tables_analyzed'] += 1
            seq_pct = table.get('seq_scan_pct', 0)

            if seq_pct > 50 and table.get('n_live_tup', 0) > 10000:
                await self.add_finding(
                    memory,
                    category="Performance",
                    title=f"High sequential scans: {table['relname']}",
                    description=f"{seq_pct}% of scans are sequential ({table['seq_scan']} scans, {table['n_live_tup']} rows)",
                    severity=FindingSeverity.HIGH if seq_pct > 80 else FindingSeverity.MEDIUM,
                    affected_objects=[f"{schema}.{table['relname']}"],
                    remediation="Add appropriate indexes based on query patterns",
                    metadata={'seq_scan_pct': seq_pct, 'row_count': table['n_live_tup']}
                )
                results['seq_scan_issues'].append(table['relname'])

    async def _analyze_table_bloat(
        self,
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze table bloat."""
        query = """
        SELECT
            schemaname,
            relname,
            n_live_tup,
            n_dead_tup,
            CASE
                WHEN n_live_tup > 0
                THEN round(100.0 * n_dead_tup / (n_live_tup + n_dead_tup), 2)
                ELSE 0
            END as dead_pct,
            last_autovacuum,
            last_vacuum,
            pg_size_pretty(pg_total_relation_size(relid)) as total_size
        FROM pg_stat_user_tables
        WHERE schemaname = $1
        AND n_dead_tup > 1000
        ORDER BY n_dead_tup DESC
        LIMIT 20
        """
        tables = await self.runner.execute_safe(query, (schema,), "Get table bloat")

        for table in tables:
            dead_pct = table.get('dead_pct', 0)

            if dead_pct > 10:
                severity = FindingSeverity.HIGH if dead_pct > 30 else FindingSeverity.MEDIUM
                await self.add_finding(
                    memory,
                    category="Performance",
                    title=f"Table bloat: {table['relname']}",
                    description=f"{dead_pct}% dead tuples ({table['n_dead_tup']} dead of {table['n_live_tup']} live)",
                    severity=severity,
                    affected_objects=[f"{schema}.{table['relname']}"],
                    remediation="Run VACUUM ANALYZE or consider VACUUM FULL for severe bloat",
                    metadata={'dead_tuples': table['n_dead_tup']}
                )
                results['bloat_issues'].append(table['relname'])

    async def _analyze_index_usage(
        self,
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze index usage patterns."""
        query = """
        SELECT
            schemaname,
            relname,
            indexrelname,
            idx_scan,
            idx_tup_read,
            idx_tup_fetch,
            pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
            pg_relation_size(indexrelid) as size_bytes
        FROM pg_stat_user_indexes
        WHERE schemaname = $1
        ORDER BY idx_scan ASC
        LIMIT 30
        """
        indexes = await self.runner.execute_safe(query, (schema,), "Get index usage")

        for idx in indexes:
            # Unused indexes (large but never scanned)
            if idx.get('idx_scan', 0) == 0 and idx.get('size_bytes', 0) > 1024 * 1024:
                await self.add_finding(
                    memory,
                    category="Performance",
                    title=f"Unused index: {idx['indexrelname']}",
                    description=f"Index on {idx['relname']} has never been used ({idx['index_size']})",
                    severity=FindingSeverity.MEDIUM,
                    affected_objects=[f"{schema}.{idx['relname']}.{idx['indexrelname']}"],
                    remediation="Consider dropping unused index to save space and improve write performance"
                )

    async def _analyze_cache_performance(
        self,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze buffer cache hit ratio."""
        query = """
        SELECT
            sum(heap_blks_read) as heap_read,
            sum(heap_blks_hit) as heap_hit,
            sum(idx_blks_read) as idx_read,
            sum(idx_blks_hit) as idx_hit
        FROM pg_statio_user_tables
        """
        stats = await self.runner.execute_safe(query, description="Get cache stats")

        if stats:
            s = stats[0]
            heap_total = (s.get('heap_read', 0) or 0) + (s.get('heap_hit', 0) or 0)
            idx_total = (s.get('idx_read', 0) or 0) + (s.get('idx_hit', 0) or 0)

            heap_hit_ratio = 0
            idx_hit_ratio = 0

            if heap_total > 0:
                heap_hit_ratio = round(100.0 * (s.get('heap_hit', 0) or 0) / heap_total, 2)
            if idx_total > 0:
                idx_hit_ratio = round(100.0 * (s.get('idx_hit', 0) or 0) / idx_total, 2)

            results['cache_stats'] = {
                'heap_hit_ratio': heap_hit_ratio,
                'index_hit_ratio': idx_hit_ratio
            }

            if heap_hit_ratio < 90:
                await self.add_finding(
                    memory,
                    category="Performance",
                    title="Low buffer cache hit ratio",
                    description=f"Heap cache hit ratio is {heap_hit_ratio}% (target: >90%)",
                    severity=FindingSeverity.HIGH if heap_hit_ratio < 80 else FindingSeverity.MEDIUM,
                    remediation="Consider increasing shared_buffers or optimizing queries"
                )

    async def _analyze_vacuum_status(
        self,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check vacuum status across tables."""
        query = """
        SELECT
            schemaname,
            relname,
            last_vacuum,
            last_autovacuum,
            last_analyze,
            last_autoanalyze,
            n_mod_since_analyze
        FROM pg_stat_user_tables
        WHERE last_analyze IS NULL
        OR last_analyze < NOW() - INTERVAL '7 days'
        ORDER BY n_mod_since_analyze DESC NULLS FIRST
        LIMIT 20
        """
        tables = await self.runner.execute_safe(query, description="Get vacuum status")

        for table in tables:
            if not table.get('last_analyze'):
                await self.add_finding(
                    memory,
                    category="Performance",
                    title=f"Never analyzed: {table['relname']}",
                    description="Table has never been analyzed - statistics are missing",
                    severity=FindingSeverity.HIGH,
                    affected_objects=[f"{table['schemaname']}.{table['relname']}"],
                    remediation=f"Run ANALYZE {table['schemaname']}.{table['relname']}"
                )

    async def _analyze_connection_stats(
        self,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze connection usage."""
        query = """
        SELECT
            (SELECT count(*) FROM pg_stat_activity) as current_connections,
            (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_connections
        """
        stats = await self.runner.execute_safe(query, description="Get connection stats")

        if stats:
            current = stats[0].get('current_connections', 0)
            max_conn = stats[0].get('max_connections', 100)
            usage_pct = round(100.0 * current / max_conn, 2)

            if usage_pct > 80:
                await self.add_finding(
                    memory,
                    category="Performance",
                    title="High connection usage",
                    description=f"Using {current}/{max_conn} connections ({usage_pct}%)",
                    severity=FindingSeverity.HIGH if usage_pct > 90 else FindingSeverity.MEDIUM,
                    remediation="Consider implementing connection pooling (PgBouncer)"
                )

        # Add recommendations
        await self.add_recommendation(
            memory,
            category="Performance",
            title="Implement regular maintenance",
            description="Schedule regular VACUUM and ANALYZE operations",
            priority=8,
            effort="low",
            impact="high",
            implementation="Configure autovacuum settings or create maintenance jobs"
        )
