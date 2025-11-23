"""
Orphan Checker Agent - Detects orphaned data in the database.
"""

from typing import Any, Dict, List
from .base_agent import BaseAgent
from ..manager.memory import SharedMemory, FindingSeverity


class OrphanCheckerAgent(BaseAgent):
    """
    Detects orphaned data including:
    - Records without parent references
    - Cascade deletion candidates
    - Hierarchical inconsistencies
    """

    async def analyze(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Perform orphan data analysis."""
        self.log_info("Starting orphan data analysis")

        results = {
            'orphans_found': 0,
            'tables_checked': 0,
            'orphan_details': [],
        }

        for schema in schemas:
            await self._check_orphaned_records(catalog, schema, memory, results)
            await self._check_self_references(catalog, schema, memory, results)
            await self._check_soft_delete_orphans(catalog, schema, memory, results)

        self.log_info(f"Orphan analysis complete. Found {results['orphans_found']} orphan groups")
        return results

    async def _check_orphaned_records(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check for orphaned records based on FK relationships."""
        # Get all FKs
        query = """
        SELECT
            tc.table_name as child_table,
            kcu.column_name as child_column,
            ccu.table_name AS parent_table,
            ccu.column_name AS parent_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = $1
        """
        fks = await self.runner.execute_safe(query, (schema,), "Get FKs for orphan check")

        for fk in fks:
            results['tables_checked'] += 1

            # Check for orphaned records (records in child without matching parent)
            orphan_query = f"""
            SELECT COUNT(*) as orphan_count
            FROM {schema}.{fk['child_table']} c
            LEFT JOIN {schema}.{fk['parent_table']} p
                ON c.{fk['child_column']} = p.{fk['parent_column']}
            WHERE c.{fk['child_column']} IS NOT NULL
            AND p.{fk['parent_column']} IS NULL
            """

            try:
                result = await self.runner.execute_safe(orphan_query, description="Check orphans")
                orphan_count = result[0].get('orphan_count', 0) if result else 0

                if orphan_count > 0:
                    results['orphans_found'] += 1
                    results['orphan_details'].append({
                        'child_table': fk['child_table'],
                        'parent_table': fk['parent_table'],
                        'count': orphan_count
                    })

                    await self.add_finding(
                        memory,
                        category="Orphans",
                        title=f"Orphaned records: {fk['child_table']}",
                        description=f"{orphan_count} records reference non-existent {fk['parent_table']} records",
                        severity=FindingSeverity.HIGH,
                        affected_objects=[f"{schema}.{fk['child_table']}"],
                        remediation=f"DELETE FROM {fk['child_table']} WHERE {fk['child_column']} NOT IN (SELECT {fk['parent_column']} FROM {fk['parent_table']})",
                        metadata={'orphan_count': orphan_count}
                    )
            except Exception as e:
                self.log_warning(f"Could not check orphans for {fk['child_table']}: {e}")

    async def _check_self_references(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check self-referencing tables for orphaned hierarchy."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])

            # Look for parent_id or similar self-reference patterns
            parent_cols = [c for c in columns if c.get('column_name', '').endswith('parent_id')]

            for col in parent_cols:
                col_name = col.get('column_name', '')

                # Check for broken hierarchy
                query = f"""
                WITH RECURSIVE hierarchy AS (
                    SELECT id, {col_name}, 0 as depth
                    FROM {schema}.{table_name}
                    WHERE {col_name} IS NULL
                    UNION ALL
                    SELECT t.id, t.{col_name}, h.depth + 1
                    FROM {schema}.{table_name} t
                    JOIN hierarchy h ON t.{col_name} = h.id
                    WHERE h.depth < 100
                )
                SELECT COUNT(*) as orphan_count
                FROM {schema}.{table_name}
                WHERE id NOT IN (SELECT id FROM hierarchy)
                AND {col_name} IS NOT NULL
                """

                try:
                    result = await self.runner.execute_safe(query, description="Check hierarchy orphans")
                    orphan_count = result[0].get('orphan_count', 0) if result else 0

                    if orphan_count > 0:
                        await self.add_finding(
                            memory,
                            category="Orphans",
                            title=f"Broken hierarchy in {table_name}",
                            description=f"{orphan_count} records have broken parent chain",
                            severity=FindingSeverity.HIGH,
                            affected_objects=[f"{schema}.{table_name}"],
                            remediation="Review and fix parent references or remove orphaned records"
                        )
                except Exception:
                    pass  # Table may not have id column

    async def _check_soft_delete_orphans(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check for orphans created by soft deletes."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])

            # Look for soft delete columns
            delete_cols = [c for c in columns if c.get('column_name', '') in (
                'deleted_at', 'is_deleted', 'deleted', 'archived_at'
            )]

            if delete_cols:
                await self.add_finding(
                    memory,
                    category="Orphans",
                    title=f"Soft delete table: {table_name}",
                    description="Table uses soft deletes which can create orphan-like scenarios",
                    severity=FindingSeverity.INFO,
                    affected_objects=[f"{schema}.{table_name}"],
                    remediation="Ensure related records are also soft-deleted to maintain consistency"
                )

        # Add recommendation
        await self.add_recommendation(
            memory,
            category="Data Cleanup",
            title="Implement orphan cleanup procedures",
            description="Create automated jobs to identify and clean orphaned records",
            priority=7,
            effort="medium",
            impact="high",
            implementation="Create a scheduled job that runs cleanup queries for identified orphans"
        )
