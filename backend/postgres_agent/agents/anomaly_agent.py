"""
Anomaly Agent - Detects statistical anomalies and outliers.
"""

from typing import Any, Dict, List
from .base_agent import BaseAgent
from ..manager.memory import SharedMemory, FindingSeverity


class AnomalyAgent(BaseAgent):
    """
    Detects anomalies including:
    - Statistical outliers
    - Distribution anomalies
    - Temporal pattern issues
    """

    async def analyze(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Perform anomaly detection analysis."""
        self.log_info("Starting anomaly detection analysis")

        results = {
            'tables_analyzed': 0,
            'anomalies_found': [],
            'statistical_summary': {},
        }

        for schema in schemas:
            await self._detect_numeric_outliers(catalog, schema, memory, results)
            await self._detect_temporal_anomalies(catalog, schema, memory, results)
            await self._detect_distribution_issues(catalog, schema, memory, results)

        self.log_info(f"Anomaly detection complete. Found {len(results['anomalies_found'])} anomalies")
        return results

    async def _detect_numeric_outliers(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Detect outliers in numeric columns using IQR method."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])
            row_count = table.get('row_count', 0)
            results['tables_analyzed'] += 1

            if row_count < 100:
                continue

            # Check numeric columns
            numeric_cols = [c for c in columns if c.get('udt_name', '') in (
                'int2', 'int4', 'int8', 'float4', 'float8', 'numeric', 'decimal'
            )]

            for col in numeric_cols:
                col_name = col.get('column_name', '')

                # Calculate quartiles and outliers
                query = f"""
                WITH stats AS (
                    SELECT
                        percentile_cont(0.25) WITHIN GROUP (ORDER BY {col_name}) as q1,
                        percentile_cont(0.50) WITHIN GROUP (ORDER BY {col_name}) as median,
                        percentile_cont(0.75) WITHIN GROUP (ORDER BY {col_name}) as q3,
                        avg({col_name}) as mean,
                        stddev({col_name}) as stddev
                    FROM {schema}.{table_name}
                    WHERE {col_name} IS NOT NULL
                ),
                bounds AS (
                    SELECT
                        q1, q3, median, mean, stddev,
                        q1 - 1.5 * (q3 - q1) as lower_bound,
                        q3 + 1.5 * (q3 - q1) as upper_bound
                    FROM stats
                )
                SELECT
                    b.*,
                    (SELECT COUNT(*) FROM {schema}.{table_name}
                     WHERE {col_name} < b.lower_bound OR {col_name} > b.upper_bound) as outlier_count,
                    (SELECT COUNT(*) FROM {schema}.{table_name} WHERE {col_name} IS NOT NULL) as total_count
                FROM bounds b
                """
                try:
                    result = await self.runner.execute_safe(query, description=f"Outlier check {table_name}.{col_name}")
                    if result:
                        stats = result[0]
                        outlier_count = stats.get('outlier_count', 0)
                        total_count = stats.get('total_count', 0)

                        if total_count > 0:
                            outlier_pct = round(100.0 * outlier_count / total_count, 2)

                            # Store stats
                            results['statistical_summary'][f"{table_name}.{col_name}"] = {
                                'mean': float(stats.get('mean', 0) or 0),
                                'median': float(stats.get('median', 0) or 0),
                                'stddev': float(stats.get('stddev', 0) or 0),
                                'outlier_pct': outlier_pct
                            }

                            if outlier_pct > 5:
                                await self.add_finding(
                                    memory,
                                    category="Anomalies",
                                    title=f"High outlier rate: {table_name}.{col_name}",
                                    description=f"{outlier_pct}% of values are statistical outliers ({outlier_count} records)",
                                    severity=FindingSeverity.MEDIUM if outlier_pct < 10 else FindingSeverity.HIGH,
                                    affected_objects=[f"{schema}.{table_name}.{col_name}"],
                                    metadata={'outlier_count': outlier_count, 'bounds': [stats.get('lower_bound'), stats.get('upper_bound')]}
                                )
                                results['anomalies_found'].append(f"outliers:{table_name}.{col_name}")
                except Exception:
                    pass

    async def _detect_temporal_anomalies(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Detect anomalies in timestamp columns."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])

            # Check timestamp columns
            time_cols = [c for c in columns if c.get('udt_name', '') in (
                'timestamp', 'timestamptz', 'date'
            )]

            for col in time_cols:
                col_name = col.get('column_name', '')

                # Check for future dates or very old dates
                query = f"""
                SELECT
                    MIN({col_name}) as min_date,
                    MAX({col_name}) as max_date,
                    COUNT(*) FILTER (WHERE {col_name} > NOW()) as future_count,
                    COUNT(*) FILTER (WHERE {col_name} < '1990-01-01') as ancient_count,
                    COUNT(*) as total
                FROM {schema}.{table_name}
                WHERE {col_name} IS NOT NULL
                """
                try:
                    result = await self.runner.execute_safe(query, description=f"Temporal check {table_name}.{col_name}")
                    if result:
                        stats = result[0]
                        future_count = stats.get('future_count', 0)
                        ancient_count = stats.get('ancient_count', 0)

                        if future_count > 0:
                            await self.add_finding(
                                memory,
                                category="Anomalies",
                                title=f"Future dates: {table_name}.{col_name}",
                                description=f"{future_count} records have dates in the future",
                                severity=FindingSeverity.HIGH,
                                affected_objects=[f"{schema}.{table_name}.{col_name}"],
                                remediation="Investigate and correct records with future dates"
                            )
                            results['anomalies_found'].append(f"future_dates:{table_name}.{col_name}")

                        if ancient_count > 0:
                            await self.add_finding(
                                memory,
                                category="Anomalies",
                                title=f"Ancient dates: {table_name}.{col_name}",
                                description=f"{ancient_count} records have dates before 1990",
                                severity=FindingSeverity.MEDIUM,
                                affected_objects=[f"{schema}.{table_name}.{col_name}"],
                                remediation="Review records with very old dates"
                            )
                except Exception:
                    pass

    async def _detect_distribution_issues(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Detect unusual value distributions."""
        tables = self.get_tables_from_catalog(catalog, schema)

        for table in tables:
            table_name = table.get('table_name', '')
            columns = table.get('columns', [])
            row_count = table.get('row_count', 0)

            if row_count < 100:
                continue

            # Check for columns with single dominant value
            for col in columns:
                col_name = col.get('column_name', '')

                query = f"""
                SELECT
                    {col_name} as value,
                    COUNT(*) as count,
                    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct
                FROM {schema}.{table_name}
                GROUP BY {col_name}
                ORDER BY count DESC
                LIMIT 1
                """
                try:
                    result = await self.runner.execute_safe(query, description=f"Distribution check {table_name}.{col_name}")
                    if result:
                        top_pct = result[0].get('pct', 0)

                        # Single value dominates
                        if top_pct > 95 and result[0].get('count', 0) > 100:
                            await self.add_finding(
                                memory,
                                category="Anomalies",
                                title=f"Skewed distribution: {table_name}.{col_name}",
                                description=f"Single value accounts for {top_pct}% of records",
                                severity=FindingSeverity.INFO,
                                affected_objects=[f"{schema}.{table_name}.{col_name}"],
                                remediation="Review if this column provides useful information"
                            )
                except Exception:
                    pass

        # Add recommendation
        await self.add_recommendation(
            memory,
            category="Data Quality",
            title="Implement data validation rules",
            description="Add CHECK constraints to prevent invalid data entry",
            priority=7,
            effort="medium",
            impact="high",
            implementation="Add constraints like CHECK (date_col <= CURRENT_DATE)"
        )
