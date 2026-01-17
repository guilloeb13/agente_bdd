"""
Security Agent - Analyzes database security configuration.
OWASP and CIS Benchmark compliance checks.
"""

from typing import Any, Dict, List
from .base_agent import BaseAgent
from ..manager.memory import SharedMemory, FindingSeverity


class SecurityAgent(BaseAgent):
    """
    Analyzes database security including:
    - Roles and permissions
    - Password policies
    - Connection security
    - SECURITY DEFINER functions
    - Excessive privileges
    """

    async def analyze(
        self,
        catalog: Dict[str, Any],
        schemas: List[str],
        memory: SharedMemory,
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Perform security analysis."""
        self.log_info("Starting security analysis")

        results = {
            'roles_analyzed': 0,
            'functions_analyzed': 0,
            'permissions_checked': 0,
            'issues': [],
        }

        # Analyze roles
        await self._analyze_roles(catalog, memory, results)

        # Analyze password policies
        await self._analyze_password_policies(memory, results)

        # Check SECURITY DEFINER functions
        for schema in schemas:
            await self._analyze_security_definer(catalog, schema, memory, results)

        # Check table ownership
        for schema in schemas:
            await self._analyze_ownership(catalog, schema, memory, results)

        # Check excessive privileges
        await self._analyze_privileges(memory, results)

        # Check connection security
        await self._analyze_connection_security(catalog, memory, results)

        # Check for public schema issues
        await self._analyze_public_schema(memory, results)

        self.log_info(f"Security analysis complete. Found {len(results['issues'])} issues")
        return results

    async def _analyze_roles(
        self,
        catalog: Dict[str, Any],
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze database roles for security issues."""
        roles = catalog.get('roles', [])
        results['roles_analyzed'] = len(roles)

        for role in roles:
            role_name = role.get('rolname', '')

            # Check superuser roles
            if role.get('rolsuper') and role_name != 'postgres':
                await self.add_finding(
                    memory,
                    category="Roles",
                    title=f"Superuser role: {role_name}",
                    description=f"Role '{role_name}' has superuser privileges which grants unrestricted access",
                    severity=FindingSeverity.HIGH,
                    affected_objects=[role_name],
                    remediation="Review if superuser privileges are necessary. Consider using more restrictive roles."
                )
                results['issues'].append(f"superuser:{role_name}")

            # Check roles that can create roles
            if role.get('rolcreaterole'):
                await self.add_finding(
                    memory,
                    category="Roles",
                    title=f"Role can create other roles: {role_name}",
                    description=f"Role '{role_name}' can create new roles, potential privilege escalation risk",
                    severity=FindingSeverity.MEDIUM,
                    affected_objects=[role_name],
                    remediation="Limit CREATEROLE privilege to administrative accounts only"
                )

            # Check roles with no connection limit
            if role.get('rolcanlogin') and role.get('rolconnlimit', -1) == -1:
                await self.add_finding(
                    memory,
                    category="Roles",
                    title=f"No connection limit: {role_name}",
                    description=f"Role '{role_name}' has no connection limit set",
                    severity=FindingSeverity.LOW,
                    affected_objects=[role_name],
                    remediation="Set appropriate connection limits with ALTER ROLE"
                )

            # Check for roles without password expiration
            if role.get('rolcanlogin') and not role.get('rolvaliduntil'):
                await self.add_finding(
                    memory,
                    category="Roles",
                    title=f"No password expiration: {role_name}",
                    description=f"Login role '{role_name}' has no password expiration date",
                    severity=FindingSeverity.MEDIUM,
                    affected_objects=[role_name],
                    remediation="Set password expiration with ALTER ROLE ... VALID UNTIL"
                )

            # Check for replication privilege
            if role.get('rolreplication') and role_name != 'postgres':
                await self.add_finding(
                    memory,
                    category="Roles",
                    title=f"Replication privilege: {role_name}",
                    description=f"Role '{role_name}' has replication privileges",
                    severity=FindingSeverity.INFO,
                    affected_objects=[role_name],
                    remediation="Verify replication access is required for this role"
                )

    async def _analyze_password_policies(
        self,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check password-related settings."""
        query = """
        SELECT name, setting
        FROM pg_settings
        WHERE name IN (
            'password_encryption',
            'db_user_namespace',
            'krb_caseins_users'
        )
        """
        settings = await self.runner.execute_safe(query, description="Check password settings")

        for setting in settings:
            if setting['name'] == 'password_encryption':
                if setting['setting'] != 'scram-sha-256':
                    await self.add_finding(
                        memory,
                        category="Authentication",
                        title="Weak password encryption",
                        description=f"Password encryption is set to '{setting['setting']}' instead of scram-sha-256",
                        severity=FindingSeverity.HIGH,
                        remediation="Set password_encryption = 'scram-sha-256' in postgresql.conf"
                    )
                    results['issues'].append("weak_encryption")

    async def _analyze_security_definer(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check for potentially dangerous SECURITY DEFINER functions."""
        functions = self.get_functions_from_catalog(catalog, schema)

        for func in functions:
            if func.get('security_definer'):
                results['functions_analyzed'] += 1
                source = func.get('source_code', '').lower()

                # Check for dangerous patterns
                dangerous_patterns = [
                    ('execute', 'Dynamic SQL execution'),
                    ('dblink', 'Database link usage'),
                    ('copy', 'COPY command'),
                ]

                for pattern, desc in dangerous_patterns:
                    if pattern in source:
                        await self.add_finding(
                            memory,
                            category="Functions",
                            title=f"Dangerous SECURITY DEFINER: {func['function_name']}",
                            description=f"Function uses {desc} with SECURITY DEFINER - potential SQL injection risk",
                            severity=FindingSeverity.HIGH,
                            affected_objects=[f"{schema}.{func['function_name']}"],
                            remediation="Review function for SQL injection vulnerabilities. Consider using SECURITY INVOKER."
                        )
                        results['issues'].append(f"dangerous_function:{func['function_name']}")

    async def _analyze_ownership(
        self,
        catalog: Dict[str, Any],
        schema: str,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check table ownership."""
        query = """
        SELECT
            n.nspname as schema,
            c.relname as table_name,
            pg_get_userbyid(c.relowner) as owner
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = $1
        AND c.relkind = 'r'
        """
        tables = await self.runner.execute_safe(query, (schema,), "Check table ownership")

        for table in tables:
            owner = table.get('owner', '')
            if owner == 'postgres':
                await self.add_finding(
                    memory,
                    category="Ownership",
                    title=f"Table owned by postgres: {table['table_name']}",
                    description=f"Table {schema}.{table['table_name']} is owned by postgres superuser",
                    severity=FindingSeverity.LOW,
                    affected_objects=[f"{schema}.{table['table_name']}"],
                    remediation="Consider transferring ownership to application-specific role"
                )

    async def _analyze_privileges(
        self,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check for excessive privileges."""
        # Check for PUBLIC grants on sensitive tables
        query = """
        SELECT
            grantee,
            table_schema,
            table_name,
            string_agg(privilege_type, ', ') as privileges
        FROM information_schema.table_privileges
        WHERE grantee = 'PUBLIC'
        GROUP BY grantee, table_schema, table_name
        """
        public_grants = await self.runner.execute_safe(query, description="Check PUBLIC grants")

        for grant in public_grants:
            results['permissions_checked'] += 1
            await self.add_finding(
                memory,
                category="Privileges",
                title=f"PUBLIC access on {grant['table_name']}",
                description=f"Table {grant['table_schema']}.{grant['table_name']} grants {grant['privileges']} to PUBLIC",
                severity=FindingSeverity.MEDIUM,
                affected_objects=[f"{grant['table_schema']}.{grant['table_name']}"],
                remediation="REVOKE unnecessary privileges from PUBLIC role"
            )
            results['issues'].append(f"public_grant:{grant['table_name']}")

    async def _analyze_connection_security(
        self,
        catalog: Dict[str, Any],
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Analyze connection and SSL settings."""
        settings = catalog.get('settings', [])

        ssl_enabled = False
        for setting in settings:
            if setting.get('name') == 'ssl' and setting.get('setting') == 'on':
                ssl_enabled = True
                break

        if not ssl_enabled:
            await self.add_finding(
                memory,
                category="Connection",
                title="SSL not enabled",
                description="SSL is not enabled for database connections",
                severity=FindingSeverity.HIGH,
                remediation="Enable SSL in postgresql.conf and configure certificates"
            )
            results['issues'].append("ssl_disabled")

    async def _analyze_public_schema(
        self,
        memory: SharedMemory,
        results: Dict
    ) -> None:
        """Check public schema security."""
        query = """
        SELECT has_schema_privilege('PUBLIC', 'public', 'CREATE') as can_create
        """
        result = await self.runner.execute_safe(query, description="Check public schema privileges")

        if result and result[0].get('can_create'):
            await self.add_finding(
                memory,
                category="Schema",
                title="PUBLIC can create in public schema",
                description="Any user can create objects in the public schema",
                severity=FindingSeverity.MEDIUM,
                remediation="REVOKE CREATE ON SCHEMA public FROM PUBLIC"
            )
            results['issues'].append("public_create")

        # Recommendation for security hardening
        await self.add_recommendation(
            memory,
            category="Security",
            title="Implement role-based access control",
            description="Create application-specific roles with minimal required privileges",
            priority=8,
            effort="medium",
            impact="high",
            implementation="CREATE ROLE app_readonly; GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly;"
        )
