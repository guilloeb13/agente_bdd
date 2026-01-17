"""
DDL Reconstruction Agent - Reconstructs complete DDL from database.
"""

from typing import Any, Dict, List
from .base_agent import BaseAgent
from ..manager.memory import SharedMemory, FindingSeverity


class DDLReconstructionAgent(BaseAgent):
    """
    Reconstructs DDL including:
    - CREATE TABLE statements
    - Indexes
    - Constraints
    - Functions
    - Triggers
    - Views
    """

    async def analyze(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Reconstruct DDL from database."""
        self.log_info("Starting DDL reconstruction")

        results = {
            'ddl_statements': [],
            'objects_processed': 0,
        }

        for schema in schemas:
            # Generate DDL in dependency order
            await self._generate_schema_ddl(schema, results)
            await self._generate_type_ddl(catalog, schema, results)
            await self._generate_sequence_ddl(catalog, schema, results)
            await self._generate_table_ddl(catalog, schema, results)
            await self._generate_index_ddl(catalog, schema, results)
            await self._generate_function_ddl(catalog, schema, results)
            await self._generate_trigger_ddl(catalog, schema, results)
            await self._generate_view_ddl(catalog, schema, results)

        # Store DDL in memory for reporting
        ddl_text = '\n\n'.join(results['ddl_statements'])
        await memory.cache_catalog('reconstructed_ddl', ddl_text)

        self.log_info(f"DDL reconstruction complete. Generated {len(results['ddl_statements'])} statements")
        return results

    async def _generate_schema_ddl(self, schema: str, results: Dict) -> None:
        """Generate CREATE SCHEMA statement."""
        if schema != 'public':
            ddl = f"CREATE SCHEMA IF NOT EXISTS {schema};"
            results['ddl_statements'].append(ddl)
            results['objects_processed'] += 1

    async def _generate_type_ddl(
        self,
        catalog: Dict[str, Any],
        schema: str,
        results: Dict
    ) -> None:
        """Generate CREATE TYPE statements."""
        types = catalog.get('schemas', {}).get(schema, {}).get('types', [])

        for t in types:
            type_name = t.get('type_name', '')
            type_type = t.get('type_type', '')

            if type_type == 'e':  # Enum
                query = f"""
                SELECT string_agg(quote_literal(enumlabel), ', ' ORDER BY enumsortorder) as labels
                FROM pg_enum
                WHERE enumtypid = $1::regtype
                """
                try:
                    result = await self.runner.execute_safe(
                        query, (f"{schema}.{type_name}",),
                        description=f"Get enum values for {type_name}"
                    )
                    if result and result[0].get('labels'):
                        ddl = f"CREATE TYPE {schema}.{type_name} AS ENUM ({result[0]['labels']});"
                        results['ddl_statements'].append(ddl)
                        results['objects_processed'] += 1
                except Exception:
                    pass

    async def _generate_sequence_ddl(
        self,
        catalog: Dict[str, Any],
        schema: str,
        results: Dict
    ) -> None:
        """Generate CREATE SEQUENCE statements."""
        sequences = catalog.get('schemas', {}).get(schema, {}).get('sequences', [])

        for seq in sequences:
            seq_name = seq.get('sequence_name', '')
            start = seq.get('start_value', 1)
            increment = seq.get('increment', 1)
            min_val = seq.get('minimum_value', 1)
            max_val = seq.get('maximum_value', 9223372036854775807)
            cycle = 'CYCLE' if seq.get('cycle_option', 'NO') == 'YES' else 'NO CYCLE'

            ddl = f"""CREATE SEQUENCE {schema}.{seq_name}
    START WITH {start}
    INCREMENT BY {increment}
    MINVALUE {min_val}
    MAXVALUE {max_val}
    {cycle};"""
            results['ddl_statements'].append(ddl)
            results['objects_processed'] += 1

    async def _generate_table_ddl(
        self,
        catalog: Dict[str, Any],
        schema: str,
        results: Dict
    ) -> None:
        """Generate CREATE TABLE statements."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')

            if table.get('table_type') != 'BASE TABLE':
                continue

            # Use pg_get_tabledef if available, otherwise construct manually
            query = f"""
            SELECT
                'CREATE TABLE {schema}.{table_name} (' || E'\n' ||
                string_agg(
                    '    ' || column_name || ' ' ||
                    CASE
                        WHEN domain_name IS NOT NULL THEN domain_name
                        ELSE data_type ||
                            CASE
                                WHEN character_maximum_length IS NOT NULL
                                THEN '(' || character_maximum_length || ')'
                                WHEN numeric_precision IS NOT NULL AND data_type != 'integer'
                                THEN '(' || numeric_precision || ',' || COALESCE(numeric_scale, 0) || ')'
                                ELSE ''
                            END
                    END ||
                    CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END ||
                    CASE WHEN column_default IS NOT NULL THEN ' DEFAULT ' || column_default ELSE '' END,
                    ',' || E'\n'
                    ORDER BY ordinal_position
                ) || E'\n);' as ddl
            FROM information_schema.columns
            WHERE table_schema = $1 AND table_name = $2
            """
            try:
                result = await self.runner.execute_safe(query, (schema, table_name), f"DDL for {table_name}")
                if result and result[0].get('ddl'):
                    results['ddl_statements'].append(result[0]['ddl'])
                    results['objects_processed'] += 1

                    # Add constraints
                    await self._add_table_constraints(schema, table_name, results)
            except Exception as e:
                self.log_warning(f"Could not generate DDL for {table_name}: {e}")

    async def _add_table_constraints(
        self,
        schema: str,
        table_name: str,
        results: Dict
    ) -> None:
        """Add ALTER TABLE statements for constraints."""
        # Primary key
        pk_query = """
        SELECT
            tc.constraint_name,
            string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as columns
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_schema = $1
        AND tc.table_name = $2
        AND tc.constraint_type = 'PRIMARY KEY'
        GROUP BY tc.constraint_name
        """
        pk_result = await self.runner.execute_safe(pk_query, (schema, table_name), f"PK for {table_name}")

        for pk in pk_result:
            ddl = f"ALTER TABLE {schema}.{table_name} ADD CONSTRAINT {pk['constraint_name']} PRIMARY KEY ({pk['columns']});"
            results['ddl_statements'].append(ddl)

        # Foreign keys
        fk_query = """
        SELECT
            tc.constraint_name,
            kcu.column_name,
            ccu.table_schema as ref_schema,
            ccu.table_name as ref_table,
            ccu.column_name as ref_column,
            rc.update_rule,
            rc.delete_rule
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name
        JOIN information_schema.referential_constraints rc
            ON rc.constraint_name = tc.constraint_name
        WHERE tc.table_schema = $1
        AND tc.table_name = $2
        AND tc.constraint_type = 'FOREIGN KEY'
        """
        fk_result = await self.runner.execute_safe(fk_query, (schema, table_name), f"FKs for {table_name}")

        for fk in fk_result:
            ddl = f"""ALTER TABLE {schema}.{table_name}
    ADD CONSTRAINT {fk['constraint_name']}
    FOREIGN KEY ({fk['column_name']})
    REFERENCES {fk['ref_schema']}.{fk['ref_table']}({fk['ref_column']})
    ON UPDATE {fk['update_rule']} ON DELETE {fk['delete_rule']};"""
            results['ddl_statements'].append(ddl)

    async def _generate_index_ddl(
        self,
        catalog: Dict[str, Any],
        schema: str,
        results: Dict
    ) -> None:
        """Generate CREATE INDEX statements."""
        indexes = self.get_indexes_from_catalog(catalog, schema)

        for idx in indexes:
            indexdef = idx.get('indexdef', '')
            if indexdef and 'pkey' not in idx.get('indexname', ''):
                # Skip primary key indexes, they're created with table
                results['ddl_statements'].append(indexdef + ';')
                results['objects_processed'] += 1

    async def _generate_function_ddl(
        self,
        catalog: Dict[str, Any],
        schema: str,
        results: Dict
    ) -> None:
        """Generate CREATE FUNCTION statements."""
        functions = self.get_functions_from_catalog(catalog, schema)

        for func in functions:
            func_name = func.get('function_name', '')

            query = f"""
            SELECT pg_get_functiondef(p.oid) as funcdef
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = $1 AND p.proname = $2
            LIMIT 1
            """
            try:
                result = await self.runner.execute_safe(query, (schema, func_name), f"Function DDL {func_name}")
                if result and result[0].get('funcdef'):
                    results['ddl_statements'].append(result[0]['funcdef'] + ';')
                    results['objects_processed'] += 1
            except Exception:
                pass

    async def _generate_trigger_ddl(
        self,
        catalog: Dict[str, Any],
        schema: str,
        results: Dict
    ) -> None:
        """Generate CREATE TRIGGER statements."""
        triggers = catalog.get('schemas', {}).get(schema, {}).get('triggers', [])

        for trig in triggers:
            trig_name = trig.get('trigger_name', '')
            table_name = trig.get('event_object_table', '')

            query = f"""
            SELECT pg_get_triggerdef(t.oid) as trigdef
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = $1 AND t.tgname = $2
            """
            try:
                result = await self.runner.execute_safe(query, (schema, trig_name), f"Trigger DDL {trig_name}")
                if result and result[0].get('trigdef'):
                    results['ddl_statements'].append(result[0]['trigdef'] + ';')
                    results['objects_processed'] += 1
            except Exception:
                pass

    async def _generate_view_ddl(
        self,
        catalog: Dict[str, Any],
        schema: str,
        results: Dict
    ) -> None:
        """Generate CREATE VIEW statements."""
        views = catalog.get('schemas', {}).get(schema, {}).get('views', [])

        for view in views:
            view_name = view.get('view_name', '')
            definition = view.get('view_definition', '')

            if definition:
                ddl = f"CREATE OR REPLACE VIEW {schema}.{view_name} AS\n{definition}"
                results['ddl_statements'].append(ddl)
                results['objects_processed'] += 1

        # Materialized views
        mat_views = catalog.get('schemas', {}).get(schema, {}).get('materialized_views', [])

        for mv in mat_views:
            mv_name = mv.get('matviewname', '')
            definition = mv.get('definition', '')

            if definition:
                ddl = f"CREATE MATERIALIZED VIEW {schema}.{mv_name} AS\n{definition}"
                results['ddl_statements'].append(ddl)
                results['objects_processed'] += 1
