"""
Recommendation Agent - Consolidates all findings into actionable recommendations.
"""

from typing import Any, Dict, List
from .base_agent import BaseAgent
from ..manager.memory import SharedMemory, FindingSeverity


class RecommendationAgent(BaseAgent):
    """
    Consolidates findings and generates:
    - Structural changes
    - New FK recommendations
    - Index recommendations
    - Partitioning suggestions
    - Archiving strategies
    - Refactoring plans
    """

    async def analyze(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Generate consolidated recommendations."""
        self.log_info("Starting recommendation consolidation")

        # Get all findings from memory
        all_findings = await memory.get_findings()
        all_recommendations = await memory.get_recommendations()

        results = {
            'total_findings': len(all_findings),
            'critical_findings': len([f for f in all_findings if f['severity'] == 'critical']),
            'high_findings': len([f for f in all_findings if f['severity'] == 'high']),
            'action_plan': [],
            'quick_wins': [],
            'long_term': [],
        }

        # Analyze findings and generate action plan
        await self._analyze_security_findings(all_findings, memory, results)
        await self._analyze_performance_findings(all_findings, memory, results)
        await self._analyze_structural_findings(all_findings, catalog, schemas, memory, results)
        await self._generate_partitioning_recommendations(catalog, schemas, memory, results)
        await self._generate_archiving_recommendations(catalog, schemas, memory, results)
        await self._prioritize_action_plan(results)

        self.log_info(f"Recommendation consolidation complete. Generated {len(results['action_plan'])} actions")
        return results

    async def _analyze_security_findings(
        self,
        findings: List[Dict],
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze security-related findings."""
        security_findings = [f for f in findings if f['category'] in ('Roles', 'Authentication', 'Privileges', 'Connection')]

        critical_security = [f for f in security_findings if f['severity'] in ('critical', 'high')]

        if critical_security:
            await self.add_recommendation(
                memory,
                category="Security",
                title="Address critical security issues immediately",
                description=f"Found {len(critical_security)} high/critical security issues requiring immediate attention",
                priority=10,
                effort="varies",
                impact="critical",
                implementation="Review security findings and implement remediation steps"
            )
            results['action_plan'].append({
                'priority': 1,
                'category': 'Security',
                'action': 'Address critical security findings',
                'items': len(critical_security),
                'effort': 'immediate'
            })

    async def _analyze_performance_findings(
        self,
        findings: List[Dict],
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze performance-related findings."""
        perf_findings = [f for f in findings if f['category'] == 'Performance']

        # Sequential scans
        seq_scan_issues = [f for f in perf_findings if 'sequential scan' in f['title'].lower()]
        if seq_scan_issues:
            await self.add_recommendation(
                memory,
                category="Performance",
                title="Add indexes to reduce sequential scans",
                description=f"Found {len(seq_scan_issues)} tables with excessive sequential scans",
                priority=9,
                effort="low",
                impact="high",
                implementation="Create indexes on frequently queried columns"
            )
            results['quick_wins'].append({
                'action': 'Add indexes for sequential scan tables',
                'tables': [f['affected_objects'][0] for f in seq_scan_issues if f.get('affected_objects')]
            })

        # Bloat issues
        bloat_issues = [f for f in perf_findings if 'bloat' in f['title'].lower()]
        if bloat_issues:
            await self.add_recommendation(
                memory,
                category="Performance",
                title="Run VACUUM on bloated tables",
                description=f"Found {len(bloat_issues)} tables with significant bloat",
                priority=8,
                effort="low",
                impact="medium",
                implementation="VACUUM ANALYZE or VACUUM FULL for severe cases"
            )
            results['quick_wins'].append({
                'action': 'VACUUM bloated tables',
                'tables': [f['affected_objects'][0] for f in bloat_issues if f.get('affected_objects')]
            })

    async def _analyze_structural_findings(
        self,
        findings: List[Dict],
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze structural/normalization findings."""
        # Missing FKs
        fk_findings = [f for f in findings if 'Missing FK' in f['title']]
        if fk_findings:
            await self.add_recommendation(
                memory,
                category="Integrity",
                title="Add missing foreign key constraints",
                description=f"Found {len(fk_findings)} columns that should have FK constraints",
                priority=8,
                effort="medium",
                impact="high",
                implementation="Review and add FK constraints to maintain referential integrity"
            )
            results['action_plan'].append({
                'priority': 3,
                'category': 'Integrity',
                'action': 'Add missing foreign keys',
                'items': len(fk_findings),
                'effort': 'medium'
            })

        # Normalization issues
        norm_findings = [f for f in findings if f['category'] == 'Normalization']
        if norm_findings:
            await self.add_recommendation(
                memory,
                category="Normalization",
                title="Review table normalization",
                description=f"Found {len(norm_findings)} normalization issues",
                priority=5,
                effort="high",
                impact="medium",
                implementation="Plan schema refactoring to improve normalization"
            )
            results['long_term'].append({
                'action': 'Schema normalization refactoring',
                'issues': len(norm_findings),
                'effort': 'high'
            })

    async def _generate_partitioning_recommendations(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Generate table partitioning recommendations."""
        for schema in schemas:
            tables = self.get_tables_from_catalog(catalog, schema)

            for table in tables:
                table_name = table.get('table_name', '')
                row_count = table.get('row_count', 0)
                columns = table.get('columns', [])

                # Large tables with date columns are partitioning candidates
                if row_count > 10000000:  # 10M rows
                    date_cols = [c for c in columns if c.get('udt_name', '') in ('date', 'timestamp', 'timestamptz')]

                    if date_cols:
                        await self.add_recommendation(
                            memory,
                            category="Partitioning",
                            title=f"Partition large table: {table_name}",
                            description=f"Table has {row_count:,} rows and date columns suitable for partitioning",
                            priority=6,
                            effort="high",
                            impact="high",
                            implementation=f"CREATE TABLE {table_name}_partitioned PARTITION BY RANGE ({date_cols[0]['column_name']})"
                        )
                        results['long_term'].append({
                            'action': f'Partition table {table_name}',
                            'rows': row_count,
                            'effort': 'high'
                        })

    async def _generate_archiving_recommendations(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Generate data archiving recommendations."""
        for schema in schemas:
            tables = self.get_tables_from_catalog(catalog, schema)

            for table in tables:
                table_name = table.get('table_name', '')
                row_count = table.get('row_count', 0)
                columns = table.get('columns', [])

                # Look for tables with created_at or similar columns
                time_cols = [c for c in columns if c.get('column_name', '') in (
                    'created_at', 'created_date', 'timestamp', 'log_date'
                )]

                if row_count > 1000000 and time_cols:
                    await self.add_recommendation(
                        memory,
                        category="Archiving",
                        title=f"Consider archiving old data: {table_name}",
                        description=f"Table has {row_count:,} rows - archive old records to improve performance",
                        priority=5,
                        effort="medium",
                        impact="medium",
                        implementation=f"Move records older than X days to archive table"
                    )

    async def _prioritize_action_plan(self, results: Dict) -> None:
        """Prioritize and finalize action plan."""
        # Sort action plan by priority
        results['action_plan'].sort(key=lambda x: x.get('priority', 99))

        # Categorize quick wins
        if not results['quick_wins']:
            results['quick_wins'].append({
                'action': 'Run ANALYZE on all tables',
                'effort': 'low'
            })

        # Add standard long-term recommendations
        if not results['long_term']:
            results['long_term'].append({
                'action': 'Implement comprehensive monitoring',
                'effort': 'medium'
            })

        # Final summary recommendation
        total_actions = len(results['action_plan']) + len(results['quick_wins']) + len(results['long_term'])

        results['summary'] = {
            'immediate_actions': len([a for a in results['action_plan'] if a.get('priority', 99) <= 3]),
            'quick_wins': len(results['quick_wins']),
            'long_term_projects': len(results['long_term']),
            'total_actions': total_actions
        }
