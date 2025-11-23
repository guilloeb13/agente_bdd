"""
FK Integrity Agent - Analyzes foreign key relationships and referential integrity.
"""

from typing import Any, Dict, List
from .base_agent import BaseAgent
from ..manager.memory import SharedMemory, FindingSeverity


class FKIntegrityAgent(BaseAgent):
    """
    Analyzes foreign key integrity including:
    - Missing foreign keys
    - Inconsistent constraints
    - Relationship modeling issues
    - Hidden violations
    """

    async def analyze(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Perform FK integrity analysis."""
        self.log_info("Starting FK integrity analysis")

        results = {
            'fks_analyzed': 0,
            'potential_fks': [],
            'violations': [],
            'relationship_graph': {},
        }

        for schema in schemas:
            await self._analyze_foreign_keys(catalog, schema, memory, results)
            await self._detect_missing_fks(catalog, schema, memory, results)
            await self._check_fk_violations(schema, memory, results)
            await self._analyze_cascade_rules(catalog, schema, memory, results)

        self.log_info(f"FK integrity analysis complete. Found {len(results['violations'])} issues")
        return results

    async def _analyze_foreign_keys(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze existing foreign keys."""
        constraints = self.get_constraints_from_catalog(catalog, schema)

        fk_constraints = [c for c in constraints if c.get('constraint_type') == 'FOREIGN KEY']
        results['fks_analyzed'] = len(fk_constraints)

        # Build relationship graph
        for fk in fk_constraints:
            table = fk.get('table_name', '')
            ref_table = fk.get('foreign_table_name', '')

            if table not in results['relationship_graph']:
                results['relationship_graph'][table] = {'references': [], 'referenced_by': []}
            if ref_table not in results['relationship_graph']:
                results['relationship_graph'][ref_table] = {'references': [], 'referenced_by': []}

            results['relationship_graph'][table]['references'].append(ref_table)
            results['relationship_graph'][ref_table]['referenced_by'].append(table)

    async def _detect_missing_fks(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Detect columns that should have FK but don't."""
        tables = self.get_tables_from_catalog(catalog, schema)
        constraints = self.get_constraints_from_catalog(catalog, schema)

        # Get existing FK columns
        fk_columns = set()
        for c in constraints:
            if c.get('constraint_type') == 'FOREIGN KEY':
                fk_columns.add((c.get('table_name'), c.get('column_name')))

        # Check for _id columns without FK
        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])

            for col in columns:
                col_name = col.get('column_name', '')

                # Check naming patterns that suggest FK
                if col_name.endswith('_id') and (table_name, col_name) not in fk_columns:
                    # Try to find referenced table
                    potential_ref = col_name[:-3]  # Remove _id

                    # Check if referenced table exists
                    table_names = [t.get('table_name', '') for t in tables]
                    matches = [t for t in table_names if t == potential_ref or t == f"{potential_ref}s"]

                    if matches:
                        await self.add_finding(
                            memory,
                            category="Integrity",
                            title=f"Missing FK: {table_name}.{col_name}",
                            description=f"Column appears to reference {matches[0]} but has no FK constraint",
                            severity=FindingSeverity.HIGH,
                            affected_objects=[f"{schema}.{table_name}.{col_name}"],
                            remediation=f"ALTER TABLE {table_name} ADD FOREIGN KEY ({col_name}) REFERENCES {matches[0]}(id)"
                        )
                        results['potential_fks'].append({
                            'table': table_name,
                            'column': col_name,
                            'references': matches[0]
                        })

    async def _check_fk_violations(
        self,
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check for actual FK violations in data."""
        # Get FKs and check for orphaned references
        query = """
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = $1
        """
        fks = await self.runner.execute_safe(query, (schema,), "Get FKs for violation check")

        for fk in fks:
            # Check for orphaned references (if FK is not enforced or deferred)
            check_query = f"""
            SELECT COUNT(*) as orphan_count
            FROM {schema}.{fk['table_name']} t
            LEFT JOIN {schema}.{fk['foreign_table_name']} f
                ON t.{fk['column_name']} = f.{fk['foreign_column_name']}
            WHERE t.{fk['column_name']} IS NOT NULL
            AND f.{fk['foreign_column_name']} IS NULL
            """
            try:
                result = await self.runner.execute_safe(check_query, description="Check FK violations")
                if result and result[0].get('orphan_count', 0) > 0:
                    count = result[0]['orphan_count']
                    await self.add_finding(
                        memory,
                        category="Integrity",
                        title=f"Orphaned references in {fk['table_name']}",
                        description=f"{count} rows reference non-existent records in {fk['foreign_table_name']}",
                        severity=FindingSeverity.CRITICAL,
                        affected_objects=[f"{schema}.{fk['table_name']}"],
                        metadata={'orphan_count': count}
                    )
                    results['violations'].append({
                        'table': fk['table_name'],
                        'count': count
                    })
            except Exception:
                pass  # Skip if query fails

    async def _analyze_cascade_rules(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze FK cascade rules."""
        constraints = self.get_constraints_from_catalog(catalog, schema)

        for c in constraints:
            if c.get('constraint_type') != 'FOREIGN KEY':
                continue

            delete_rule = c.get('delete_rule', 'NO ACTION')
            update_rule = c.get('update_rule', 'NO ACTION')

            # Warn about CASCADE DELETE
            if delete_rule == 'CASCADE':
                await self.add_finding(
                    memory,
                    category="Integrity",
                    title=f"CASCADE DELETE on {c.get('constraint_name')}",
                    description=f"FK {c.get('table_name')}.{c.get('column_name')} cascades deletes - may cause data loss",
                    severity=FindingSeverity.MEDIUM,
                    affected_objects=[f"{schema}.{c.get('table_name')}"],
                    remediation="Consider using SET NULL or RESTRICT for safer data handling"
                )

            # Check for NO ACTION (default) which may cause issues
            if delete_rule == 'NO ACTION' and update_rule == 'NO ACTION':
                await self.add_finding(
                    memory,
                    category="Integrity",
                    title=f"Default FK rules: {c.get('constraint_name')}",
                    description=f"FK uses default NO ACTION rules - explicit rules recommended",
                    severity=FindingSeverity.INFO,
                    affected_objects=[f"{schema}.{c.get('table_name')}"],
                    remediation="Explicitly define ON DELETE and ON UPDATE rules"
                )

        # Add recommendation
        await self.add_recommendation(
            memory,
            category="Integrity",
            title="Create missing foreign keys",
            description="Add FK constraints for all identified relationship columns",
            priority=9,
            effort="medium",
            impact="high",
            implementation="Review potential_fks list and create appropriate constraints"
        )
