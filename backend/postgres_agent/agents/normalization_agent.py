"""
Normalization Agent - Analyzes database normalization (1NF, 2NF, 3NF, BCNF).
"""

from typing import Any, Dict, List, Set
from .base_agent import BaseAgent
from ..manager.memory import SharedMemory, FindingSeverity


class NormalizationAgent(BaseAgent):
    """
    Analyzes database normalization including:
    - 1NF violations (atomic values)
    - 2NF violations (partial dependencies)
    - 3NF violations (transitive dependencies)
    - BCNF violations
    - Denormalization recommendations
    """

    async def analyze(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Perform normalization analysis."""
        self.log_info("Starting normalization analysis")

        results = {
            'tables_analyzed': 0,
            '1nf_violations': [],
            '2nf_violations': [],
            '3nf_violations': [],
            'bcnf_violations': [],
            'refactoring_suggestions': [],
        }

        for schema in schemas:
            await self._check_1nf(catalog, schema, memory, results)
            await self._check_2nf(catalog, schema, memory, results)
            await self._check_3nf(catalog, schema, memory, results)
            await self._check_bcnf(catalog, schema, memory, results)
            await self._analyze_denormalization(catalog, schema, memory, results)

        self.log_info(f"Normalization analysis complete. Found {len(results['1nf_violations'])} 1NF issues")
        return results

    async def _check_1nf(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check for 1NF violations (atomic values, repeating groups)."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])
            results['tables_analyzed'] += 1

            # Check for array types
            for col in columns:
                col_name = col.get('column_name', '')
                data_type = col.get('data_type', '').upper()
                udt_name = col.get('udt_name', '')

                if 'ARRAY' in data_type or udt_name.startswith('_'):
                    await self.add_finding(
                        memory,
                        category="Normalization",
                        title=f"1NF: Array column {table_name}.{col_name}",
                        description="Array column violates 1NF (non-atomic values)",
                        severity=FindingSeverity.MEDIUM,
                        affected_objects=[f"{schema}.{table_name}.{col_name}"],
                        remediation="Consider creating a junction table for the array values"
                    )
                    results['1nf_violations'].append(f"{table_name}.{col_name}")

            # Check for repeating column groups (e.g., phone1, phone2, phone3)
            col_names = [c.get('column_name', '') for c in columns]
            repeating_patterns = self._find_repeating_groups(col_names)

            for pattern, cols in repeating_patterns.items():
                if len(cols) > 1:
                    await self.add_finding(
                        memory,
                        category="Normalization",
                        title=f"1NF: Repeating group in {table_name}",
                        description=f"Columns {', '.join(cols)} appear to be a repeating group",
                        severity=FindingSeverity.MEDIUM,
                        affected_objects=[f"{schema}.{table_name}.{c}" for c in cols],
                        remediation=f"Create separate table for {pattern} data"
                    )
                    results['1nf_violations'].append(f"{table_name}:{pattern}")

    def _find_repeating_groups(self, columns: List[str]) -> Dict[str, List[str]]:
        """Find repeating column groups like col1, col2, col3."""
        import re
        patterns: Dict[str, List[str]] = {}

        for col in columns:
            match = re.match(r'(.+?)(\d+)$', col)
            if match:
                base = match.group(1).rstrip('_')
                if base not in patterns:
                    patterns[base] = []
                patterns[base].append(col)

        return {k: v for k, v in patterns.items() if len(v) > 1}

    async def _check_2nf(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check for 2NF violations (partial dependencies on composite keys)."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            pk = table.get('primary_key', [])
            columns = table.get('columns', [])

            # Only applies to composite primary keys
            if len(pk) <= 1:
                continue

            # Look for columns that might depend on only part of the PK
            non_pk_cols = [c.get('column_name', '') for c in columns if c.get('column_name', '') not in pk]

            # Heuristic: columns named after a PK component suggest partial dependency
            for pk_col in pk:
                base_name = pk_col.replace('_id', '')
                suspicious = [c for c in non_pk_cols if c.startswith(base_name) and c != pk_col]

                if suspicious:
                    await self.add_finding(
                        memory,
                        category="Normalization",
                        title=f"2NF: Potential partial dependency in {table_name}",
                        description=f"Columns {suspicious} may depend only on {pk_col}",
                        severity=FindingSeverity.MEDIUM,
                        affected_objects=[f"{schema}.{table_name}"],
                        remediation=f"Extract {suspicious} into a table keyed by {pk_col}"
                    )
                    results['2nf_violations'].append(f"{table_name}:{pk_col}")

    async def _check_3nf(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check for 3NF violations (transitive dependencies)."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])

            col_names = [c.get('column_name', '') for c in columns]

            # Look for patterns that suggest transitive dependencies
            # e.g., customer_id, customer_name, customer_email in an orders table
            prefixes: Dict[str, List[str]] = {}
            for col in col_names:
                parts = col.split('_')
                if len(parts) > 1:
                    prefix = parts[0]
                    if prefix not in prefixes:
                        prefixes[prefix] = []
                    prefixes[prefix].append(col)

            for prefix, cols in prefixes.items():
                # If we have an _id column and other related columns, likely transitive
                id_col = f"{prefix}_id"
                if id_col in cols and len(cols) > 2:
                    other_cols = [c for c in cols if c != id_col]
                    await self.add_finding(
                        memory,
                        category="Normalization",
                        title=f"3NF: Transitive dependency in {table_name}",
                        description=f"Columns {other_cols} likely depend on {id_col}, not the primary key",
                        severity=FindingSeverity.MEDIUM,
                        affected_objects=[f"{schema}.{table_name}.{c}" for c in cols],
                        remediation=f"Move {other_cols} to a {prefix} table"
                    )
                    results['3nf_violations'].append(f"{table_name}:{prefix}")

    async def _check_bcnf(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check for BCNF violations."""
        # BCNF requires every determinant to be a candidate key
        # This is hard to detect without explicit functional dependencies
        # We'll look for common patterns

        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            constraints = table.get('foreign_keys', [])

            # Multiple FKs to the same table might indicate BCNF issues
            fk_targets: Dict[str, List[str]] = {}
            for fk in constraints:
                target = fk.get('foreign_table', '')
                col = fk.get('column_name', '')
                if target not in fk_targets:
                    fk_targets[target] = []
                fk_targets[target].append(col)

            for target, cols in fk_targets.items():
                if len(cols) > 1:
                    await self.add_finding(
                        memory,
                        category="Normalization",
                        title=f"BCNF: Multiple FKs to {target} in {table_name}",
                        description=f"Table has multiple foreign keys ({cols}) to the same table",
                        severity=FindingSeverity.INFO,
                        affected_objects=[f"{schema}.{table_name}"],
                        remediation="Review if this creates functional dependency issues"
                    )

    async def _analyze_denormalization(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Identify denormalization for performance."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])
            row_count = table.get('row_count', 0)

            # Look for calculated/aggregated columns
            calc_patterns = ['_total', '_count', '_sum', '_avg', '_cached', '_denorm']
            for col in columns:
                col_name = col.get('column_name', '')
                if any(p in col_name.lower() for p in calc_patterns):
                    await self.add_finding(
                        memory,
                        category="Normalization",
                        title=f"Denormalized column: {table_name}.{col_name}",
                        description="Column appears to store calculated/cached data",
                        severity=FindingSeverity.INFO,
                        affected_objects=[f"{schema}.{table_name}.{col_name}"],
                        remediation="Ensure denormalized data stays synchronized with source"
                    )

        # Add refactoring recommendations
        if results['3nf_violations']:
            await self.add_recommendation(
                memory,
                category="Normalization",
                title="Normalize transitive dependencies",
                description="Extract transitively dependent columns into separate tables",
                priority=7,
                effort="high",
                impact="high",
                implementation="Create new tables for identified transitive dependency groups"
            )
