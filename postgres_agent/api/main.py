"""
FastAPI application for PostgreSQL Multi-Agent Analyzer.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    AuditRequest,
    AuditResponse,
    AuditStatus,
    AuditStatusEnum,
    AuditSummary,
    AuditType,
    ErrorResponse,
    Finding,
    HealthResponse,
    Recommendation,
    RecommendationReport,
    SchemaInfo,
    SecurityReport,
    Severity,
)
from ..engine import PGClient
from ..manager import AgentManager
from ..manager.task_router import TaskType

logger = logging.getLogger(__name__)

# Global state
_current_manager: Optional[AgentManager] = None
_audit_results: Dict[str, Any] = {}
_audit_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("PMA-Agent API starting up")
    yield
    logger.info("PMA-Agent API shutting down")
    # Cleanup
    global _current_manager
    if _current_manager and _current_manager.pg_client:
        await _current_manager.pg_client.disconnect()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    application = FastAPI(
        title="PostgreSQL Multi-Agent Analyzer",
        description="Comprehensive PostgreSQL database auditing system using multiple specialized AI agents",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return application


app = create_app()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.utcnow()
    )


@app.post("/audit/start", response_model=AuditStatus)
async def start_audit(request: AuditRequest, background_tasks: BackgroundTasks):
    """
    Start a new database audit.

    The audit runs in the background. Use /audit/status to check progress.
    """
    global _current_manager, _audit_task

    # Check if audit is already running
    if _current_manager and _current_manager.is_running:
        raise HTTPException(
            status_code=409,
            detail="An audit is already in progress"
        )

    try:
        # Create new manager with connection
        client = PGClient(
            host=request.connection.host,
            port=request.connection.port,
            database=request.connection.database,
            user=request.connection.user,
            password=request.connection.password,
            ssl=request.connection.ssl
        )
        await client.connect()

        # Test connection
        if not await client.test_connection():
            await client.disconnect()
            raise HTTPException(
                status_code=400,
                detail="Failed to connect to database"
            )

        # Create manager and register agents
        from ..manager.agent_manager import create_manager
        _current_manager = await create_manager(
            host=request.connection.host,
            port=request.connection.port,
            database=request.connection.database,
            user=request.connection.user,
            password=request.connection.password
        )

        # Map audit type to task type
        task_type_map = {
            AuditType.FULL: TaskType.FULL_AUDIT,
            AuditType.SECURITY: TaskType.SECURITY_AUDIT,
            AuditType.SCHEMA: TaskType.SCHEMA_ANALYSIS,
            AuditType.PERFORMANCE: TaskType.PERFORMANCE,
            AuditType.INTEGRITY: TaskType.FK_INTEGRITY,
        }
        task_type = task_type_map.get(request.audit_type, TaskType.FULL_AUDIT)

        # Start audit in background
        async def run_audit():
            global _audit_results
            try:
                if task_type == TaskType.FULL_AUDIT:
                    results = await _current_manager.run_full_audit(
                        schemas=request.schemas,
                        options=request.options
                    )
                else:
                    results = await _current_manager.run_specific_audit(
                        task_type=task_type,
                        schemas=request.schemas,
                        options=request.options
                    )
                _audit_results[results['audit_id']] = results
            except Exception as e:
                logger.error(f"Audit failed: {e}")

        _audit_task = asyncio.create_task(run_audit())

        return AuditStatus(
            status=AuditStatusEnum.RUNNING,
            audit_id=None,  # Will be assigned when audit starts
            start_time=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start audit: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start audit: {str(e)}"
        )


@app.get("/audit/status", response_model=AuditStatus)
async def get_audit_status():
    """Get current audit status."""
    global _current_manager

    if not _current_manager:
        return AuditStatus(status=AuditStatusEnum.IDLE)

    status = await _current_manager.get_status()

    return AuditStatus(
        status=AuditStatusEnum.RUNNING if status.get('status') == 'running' else AuditStatusEnum.IDLE,
        audit_id=status.get('audit_id'),
        agents_completed=status.get('agents_completed', 0),
        total_findings=status.get('total_findings', 0)
    )


@app.get("/audit/report")
async def get_audit_report(audit_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get complete audit report.

    If audit_id is not specified, returns the most recent audit.
    """
    global _audit_results, _current_manager

    if audit_id and audit_id in _audit_results:
        return _audit_results[audit_id]

    # Get from current manager
    if _current_manager:
        try:
            results = await _current_manager.memory.get_all_results()
            if results.get('audit_id'):
                return results
        except Exception:
            pass

    # Return most recent if available
    if _audit_results:
        latest_id = max(_audit_results.keys())
        return _audit_results[latest_id]

    raise HTTPException(
        status_code=404,
        detail="No audit results found"
    )


@app.get("/audit/summary", response_model=AuditSummary)
async def get_audit_summary():
    """Get summary of most recent audit."""
    global _current_manager

    if not _current_manager:
        raise HTTPException(
            status_code=404,
            detail="No audit has been run"
        )

    summary = await _current_manager.get_summary()

    return AuditSummary(
        audit_id=summary.get('audit_id', ''),
        total_findings=summary.get('total_findings', 0),
        total_recommendations=summary.get('total_recommendations', 0),
        agents_completed=summary.get('agents_completed', 0),
        severity_distribution=summary.get('severity_distribution', {}),
        category_distribution=summary.get('category_distribution', {}),
        findings_by_agent=summary.get('findings_by_agent', {}),
        decisions_made=summary.get('decisions_made', 0)
    )


@app.get("/audit/findings", response_model=List[Finding])
async def get_findings(
    severity: Optional[Severity] = None,
    agent: Optional[str] = None,
    category: Optional[str] = None
):
    """Get findings with optional filters."""
    global _current_manager

    if not _current_manager:
        raise HTTPException(
            status_code=404,
            detail="No audit has been run"
        )

    from ..manager.memory import FindingSeverity

    sev_filter = None
    if severity:
        sev_filter = FindingSeverity(severity.value)

    findings = await _current_manager.get_findings(
        severity=sev_filter,
        agent=agent,
        category=category
    )

    return [Finding(**f) for f in findings]


@app.get("/audit/recommendations", response_model=List[Recommendation])
async def get_recommendations(min_priority: int = 0):
    """Get recommendations sorted by priority."""
    global _current_manager

    if not _current_manager:
        raise HTTPException(
            status_code=404,
            detail="No audit has been run"
        )

    recommendations = await _current_manager.get_recommendations(min_priority)
    return [Recommendation(**r) for r in recommendations]


@app.get("/audit/schema")
async def get_schema_info() -> Dict[str, SchemaInfo]:
    """Get analyzed schema information."""
    global _current_manager

    if not _current_manager:
        raise HTTPException(
            status_code=404,
            detail="No audit has been run"
        )

    catalog = await _current_manager.memory.get_cached_catalog('full_catalog')
    if not catalog:
        raise HTTPException(
            status_code=404,
            detail="Schema information not available"
        )

    result = {}
    for schema_name, schema_data in catalog.get('schemas', {}).items():
        tables = schema_data.get('tables', [])
        result[schema_name] = SchemaInfo(
            schema_name=schema_name,
            tables=tables,
            views=schema_data.get('views', []),
            functions=schema_data.get('functions', []),
            total_size=sum(t.get('total_size', 0) for t in tables)
        )

    return result


@app.get("/audit/security", response_model=SecurityReport)
async def get_security_report():
    """Get security-focused report."""
    global _current_manager

    if not _current_manager:
        raise HTTPException(
            status_code=404,
            detail="No audit has been run"
        )

    # Get security agent results
    security_result = await _current_manager.memory.get_agent_result('security')

    # Get security-related findings
    from ..manager.memory import FindingSeverity

    all_findings = await _current_manager.get_findings()
    security_findings = [f for f in all_findings if f['agent'] == 'SecurityAgent']

    critical = [Finding(**f) for f in security_findings if f['severity'] == 'critical']
    high = [Finding(**f) for f in security_findings if f['severity'] == 'high']

    # Get security recommendations
    all_recs = await _current_manager.get_recommendations()
    security_recs = [Recommendation(**r) for r in all_recs if r['category'] == 'Security']

    return SecurityReport(
        roles_analyzed=security_result.get('result', {}).get('roles_analyzed', 0) if security_result else 0,
        issues_found=len(security_findings),
        critical_issues=critical,
        high_issues=high,
        recommendations=security_recs
    )


@app.get("/audit/ddl")
async def get_reconstructed_ddl():
    """Get reconstructed DDL statements."""
    global _current_manager

    if not _current_manager:
        raise HTTPException(
            status_code=404,
            detail="No audit has been run"
        )

    ddl = await _current_manager.memory.get_cached_catalog('reconstructed_ddl')
    if not ddl:
        raise HTTPException(
            status_code=404,
            detail="DDL not available"
        )

    return {"ddl": ddl}


@app.get("/audit/export")
async def export_results(format: str = "json"):
    """Export audit results in specified format."""
    global _current_manager

    if not _current_manager:
        raise HTTPException(
            status_code=404,
            detail="No audit has been run"
        )

    if format == "json":
        return await _current_manager.memory.get_all_results()

    raise HTTPException(
        status_code=400,
        detail=f"Unsupported format: {format}"
    )


@app.delete("/audit/cancel")
async def cancel_audit():
    """Cancel running audit."""
    global _audit_task

    if _audit_task and not _audit_task.done():
        _audit_task.cancel()
        return {"message": "Audit cancelled"}

    return {"message": "No audit running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
