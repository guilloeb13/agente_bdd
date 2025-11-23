"""
Data Quality Agent - Analyzes data quality issues.
"""

from typing import Any, Dict, List
from .base_agent import BaseAgent
from ..manager.memory import SharedMemory, FindingSeverity


class DataQualityAgent(BaseAgent):
    """
    Analyzes data quality including:
    - Duplicates
    - NULL distributions
    - Low cardinality columns
    - Suspicious patterns
    """

    async def analyze(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Perform data quality analysis."""
        self.log_info("Starting data quality analysis")

        results = {
            'tables_analyzed': 0,
            'columns_analyzed': 0,
            'quality_issues': [],
        }

        for schema in schemas:
            await self._analyze_null_distributions(catalog, schema, memory, results)
            await self._analyze_cardinality(catalog, schema, memory, results)
            await self._check_for_duplicates(catalog, schema, memory, results)
            await self._check_data_patterns(catalog, schema, memory, results)

        self.log_info(f"Data quality analysis complete. Found {len(results['quality_issues'])} issues")
        return results

    async def _analyze_null_distributions(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze NULL value distributions."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])
            row_count = table.get('row_count', 0)
            results['tables_analyzed'] += 1

            if row_count < 100:
                continue

            for col in columns:
                col_name = col.get('column_name', '')
                is_nullable = col.get('is_nullable', 'YES') == 'YES'
                results['columns_analyzed'] += 1

                if not is_nullable:
                    continue

                # Check NULL percentage
                query = f"""
                SELECT
                    COUNT(*) as total,
                    COUNT({col_name}) as non_null,
                    COUNT(*) - COUNT({col_name}) as null_count
                FROM {schema}.{table_name}
                """
                try:
                    result = await self.runner.execute_safe(query, description=f"NULL check {table_name}.{col_name}")
                    if result:
                        total = result[0].get('total', 0)
                        null_count = result[0].get('null_count', 0)

                        if total > 0:
                            null_pct = round(100.0 * null_count / total, 2)

                            # High NULL percentage
                            if null_pct > 90:
                                await self.add_finding(
                                    memory,
                                    category="Data Quality",
                                    title=f"High NULL: {table_name}.{col_name}",
                                    description=f"{null_pct}% of values are NULL ({null_count}/{total})",
                                    severity=FindingSeverity.MEDIUM,
                                    affected_objects=[f"{schema}.{table_name}.{col_name}"],
                                    remediation="Consider if column is needed or should have a default"
                                )
                                results['quality_issues'].append(f"high_null:{table_name}.{col_name}")

                            # Unexpected NULLs in important columns
                            if null_pct > 0 and col_name in ('name', 'email', 'created_at', 'status'):
                                await self.add_finding(
                                    memory,
                                    category="Data Quality",
                                    title=f"NULLs in key column: {table_name}.{col_name}",
                                    description=f"{null_count} NULL values in column that should be required",
                                    severity=FindingSeverity.HIGH,
                                    affected_objects=[f"{schema}.{table_name}.{col_name}"],
                                    remediation="Add NOT NULL constraint or clean up NULL values"
                                )
                except Exception:
                    pass

    async def _analyze_cardinality(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze column cardinality."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            row_count = table.get('row_count', 0)
            columns = table.get('columns', [])

            if row_count < 1000:
                continue

            for col in columns:
                col_name = col.get('column_name', '')
                udt_name = col.get('udt_name', '')

                # Skip certain types
                if udt_name in ('bool', 'boolean'):
                    continue

                query = f"""
                SELECT COUNT(DISTINCT {col_name}) as distinct_count
                FROM {schema}.{table_name}
                """
                try:
                    result = await self.runner.execute_safe(query, description=f"Cardinality {table_name}.{col_name}")
                    if result:
                        distinct = result[0].get('distinct_count', 0)
                        ratio = distinct / row_count if row_count > 0 else 0

                        # Very low cardinality (might be better as enum or separate table)
                        if distinct <= 10 and ratio < 0.001 and udt_name not in ('bool', 'boolean'):
                            await self.add_finding(
                                memory,
                                category="Data Quality",
                                title=f"Low cardinality: {table_name}.{col_name}",
                                description=f"Only {distinct} distinct values in {row_count} rows",
                                severity=FindingSeverity.INFO,
                                affected_objects=[f"{schema}.{table_name}.{col_name}"],
                                remediation="Consider using ENUM type or lookup table"
                            )

                        # Potential unique key not enforced
                        if ratio > 0.99 and distinct > 100:
                            await self.add_finding(
                                memory,
                                category="Data Quality",
                                title=f"Potential unique column: {table_name}.{col_name}",
                                description=f"Column appears to be unique ({distinct}/{row_count})",
                                severity=FindingSeverity.INFO,
                                affected_objects=[f"{schema}.{table_name}.{col_name}"],
                                remediation="Consider adding UNIQUE constraint"
                            )
                except Exception:
                    pass

    async def _check_for_duplicates(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check for duplicate records."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])
            pk = table.get('primary_key', [])

            # Get non-PK columns for duplicate check
            check_cols = [c.get('column_name', '') for c in columns if c.get('column_name', '') not in pk]

            if len(check_cols) < 2:
                continue

            # Check for full row duplicates (excluding PK)
            cols_str = ', '.join(check_cols[:5])  # Limit columns
            query = f"""
            SELECT {cols_str}, COUNT(*) as dupe_count
            FROM {schema}.{table_name}
            GROUP BY {cols_str}
            HAVING COUNT(*) > 1
            LIMIT 1
            """
            try:
                result = await self.runner.execute_safe(query, description=f"Duplicate check {table_name}")
                if result:
                    await self.add_finding(
                        memory,
                        category="Data Quality",
                        title=f"Duplicate records: {table_name}",
                        description="Table contains duplicate records (by non-PK columns)",
                        severity=FindingSeverity.MEDIUM,
                        affected_objects=[f"{schema}.{table_name}"],
                        remediation="Review duplicates and consider adding unique constraints"
                    )
                    results['quality_issues'].append(f"duplicates:{table_name}")
            except Exception:
                pass

    async def _check_data_patterns(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check for suspicious data patterns."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])

            for col in columns:
                col_name = col.get('column_name', '')
                udt_name = col.get('udt_name', '')

                # Check email columns for invalid patterns
                if col_name in ('email', 'email_address'):
                    query = f"""
                    SELECT COUNT(*) as invalid_count
                    FROM {schema}.{table_name}
                    WHERE {col_name} IS NOT NULL
                    AND {col_name} !~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{{2,}}$'
                    """
                    try:
                        result = await self.runner.execute_safe(query, description=f"Email validation {table_name}")
                        if result and result[0].get('invalid_count', 0) > 0:
                            count = result[0]['invalid_count']
                            await self.add_finding(
                                memory,
                                category="Data Quality",
                                title=f"Invalid emails: {table_name}.{col_name}",
                                description=f"{count} records have invalid email format",
                                severity=FindingSeverity.MEDIUM,
                                affected_objects=[f"{schema}.{table_name}.{col_name}"],
                                remediation="Clean invalid emails and add CHECK constraint"
                            )
                    except Exception:
                        pass

        # Add recommendation
        await self.add_recommendation(
            memory,
            category="Data Quality",
            title="Implement data validation constraints",
            description="Add CHECK constraints for email, phone, and other formatted fields",
            priority=6,
            effort="medium",
            impact="high",
            implementation="ALTER TABLE t ADD CONSTRAINT valid_email CHECK (email ~ '^[^@]+@[^@]+$')"
        )
