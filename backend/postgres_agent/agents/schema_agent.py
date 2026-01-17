"""
Schema Agent - Analyzes database schema structure and consistency.
"""

from typing import Any, Dict, List
from .base_agent import BaseAgent
from ..manager.memory import SharedMemory, FindingSeverity


class SchemaAgent(BaseAgent):
    """
    Analyzes database schema including:
    - Table structures
    - Column types and domains
    - Type consistency
    - Naming conventions
    - Physical model assessment
    """

    async def analyze(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Perform schema analysis."""
        self.log_info("Starting schema analysis")

        results = {
            'tables_analyzed': 0,
            'columns_analyzed': 0,
            'schema_summary': {},
            'issues': [],
        }

        for schema in schemas:
            schema_results = await self._analyze_schema(catalog, schema, memory)
            results['schema_summary'][schema] = schema_results
            results['tables_analyzed'] += schema_results['table_count']
            results['columns_analyzed'] += schema_results['column_count']

        self.log_info(f"Schema analysis complete. Analyzed {results['tables_analyzed']} tables")
        return results

    async def _analyze_schema(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory
    ) -> Dict[str, Any]:
        """Analyze a single schema."""
        tables = self.get_tables_from_catalog(catalog, schema)

        schema_results = {
            'table_count': len(tables),
            'column_count': 0,
            'tables': [],
        }

        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])
            schema_results['column_count'] += len(columns)

            table_analysis = {
                'name': table_name,
                'columns': len(columns),
                'size': table.get('total_size', 0),
                'row_count': table.get('row_count', 0),
            }
            schema_results['tables'].append(table_analysis)

            # Analyze column types
            await self._analyze_columns(table_name, columns, schema, memory)

            # Check naming conventions
            await self._check_naming_conventions(table_name, columns, schema, memory)

            # Check for missing primary keys
            if not table.get('primary_key'):
                await self.add_finding(
                    memory,
                    category="Schema",
                    title=f"Missing primary key: {table_name}",
                    description=f"Table {schema}.{table_name} has no primary key defined",
                    severity=FindingSeverity.HIGH,
                    affected_objects=[f"{schema}.{table_name}"],
                    remediation="Add a primary key constraint to ensure data integrity"
                )

            # Check for wide tables
            if len(columns) > 30:
                await self.add_finding(
                    memory,
                    category="Schema",
                    title=f"Wide table: {table_name}",
                    description=f"Table has {len(columns)} columns which may indicate design issues",
                    severity=FindingSeverity.MEDIUM,
                    affected_objects=[f"{schema}.{table_name}"],
                    remediation="Consider normalizing into multiple related tables"
                )

        return schema_results

    async def _analyze_columns(
        self,
        table_name: str,
        columns: List[Dict],
        schema: str,
        memory: SharedMemory
    ) -> None:
        """Analyze column definitions for issues."""
        for col in columns:
            col_name = col.get('column_name', '')
            data_type = col.get('data_type', '')
            udt_name = col.get('udt_name', '')

            # Check for varchar without length
            if data_type == 'character varying' and not col.get('character_maximum_length'):
                await self.add_finding(
                    memory,
                    category="Columns",
                    title=f"Unbounded varchar: {table_name}.{col_name}",
                    description=f"Column uses varchar without length limit",
                    severity=FindingSeverity.LOW,
                    affected_objects=[f"{schema}.{table_name}.{col_name}"],
                    remediation="Consider using TEXT type or specifying maximum length"
                )

            # Check for boolean stored as varchar
            if data_type in ('character varying', 'character') and col_name.lower() in (
                'is_active', 'is_deleted', 'enabled', 'flag', 'active', 'status'
            ):
                await self.add_finding(
                    memory,
                    category="Columns",
                    title=f"Boolean as varchar: {table_name}.{col_name}",
                    description=f"Column appears to store boolean but uses {data_type}",
                    severity=FindingSeverity.MEDIUM,
                    affected_objects=[f"{schema}.{table_name}.{col_name}"],
                    remediation="Use BOOLEAN data type for true/false values"
                )

            # Check for JSON inflation
            if udt_name in ('json', 'jsonb'):
                await self.add_finding(
                    memory,
                    category="Columns",
                    title=f"JSON column: {table_name}.{col_name}",
                    description=f"JSON column may need structure review for normalization",
                    severity=FindingSeverity.INFO,
                    affected_objects=[f"{schema}.{table_name}.{col_name}"],
                    remediation="Review if JSON data should be normalized into relational tables"
                )

            # Check for timestamp without timezone
            if udt_name == 'timestamp':
                await self.add_finding(
                    memory,
                    category="Columns",
                    title=f"Timestamp without timezone: {table_name}.{col_name}",
                    description=f"Timestamp column lacks timezone information",
                    severity=FindingSeverity.MEDIUM,
                    affected_objects=[f"{schema}.{table_name}.{col_name}"],
                    remediation="Use TIMESTAMPTZ (timestamp with time zone) for unambiguous timestamps"
                )

            # Check for serial vs identity
            default = col.get('column_default', '') or ''
            if 'nextval' in default.lower():
                await self.add_finding(
                    memory,
                    category="Columns",
                    title=f"Serial column: {table_name}.{col_name}",
                    description=f"Uses SERIAL instead of IDENTITY (modern PostgreSQL)",
                    severity=FindingSeverity.INFO,
                    affected_objects=[f"{schema}.{table_name}.{col_name}"],
                    remediation="Consider using GENERATED AS IDENTITY for new tables"
                )

    async def _check_naming_conventions(
        self,
        table_name: str,
        columns: List[Dict],
        schema: str,
        memory: SharedMemory
    ) -> None:
        """Check naming conventions."""
        # Check table name conventions
        if table_name != table_name.lower():
            await self.add_finding(
                memory,
                category="Naming",
                title=f"Mixed case table name: {table_name}",
                description=f"Table name uses mixed case which requires quoting",
                severity=FindingSeverity.LOW,
                affected_objects=[f"{schema}.{table_name}"],
                remediation="Use lowercase names with underscores for consistency"
            )

        # Check column names
        for col in columns:
            col_name = col.get('column_name', '')
            if col_name != col_name.lower():
                await self.add_finding(
                    memory,
                    category="Naming",
                    title=f"Mixed case column: {table_name}.{col_name}",
                    description=f"Column name uses mixed case",
                    severity=FindingSeverity.LOW,
                    affected_objects=[f"{schema}.{table_name}.{col_name}"],
                    remediation="Use snake_case for column names"
                )

        # Add recommendations
        await self.add_recommendation(
            memory,
            category="Schema",
            title="Document table relationships",
            description="Add comments to tables and columns describing their purpose",
            priority=5,
            effort="low",
            impact="medium",
            implementation="COMMENT ON TABLE table_name IS 'Description';"
        )
