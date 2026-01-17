"""
Pydantic schemas for API request/response models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class DatabaseConnection(BaseModel):
    """Database connection configuration."""
    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    database: str = Field(..., description="Database name")
    user: str = Field(default="postgres", description="Database user")
    password: str = Field(default="", description="Database password")
    ssl: Optional[str] = Field(default=None, description="SSL mode")

    class Config:
        json_schema_extra = {
            "example": {
                "host": "localhost",
                "port": 5432,
                "database": "myapp",
                "user": "postgres",
                "password": "secret"
            }
        }


class AuditType(str, Enum):
    """Types of audit that can be performed."""
    FULL = "full_audit"
    SECURITY = "security_audit"
    SCHEMA = "schema_analysis"
    PERFORMANCE = "performance"
    INTEGRITY = "fk_integrity"


class AuditRequest(BaseModel):
    """Request to start an audit."""
    connection: DatabaseConnection
    audit_type: AuditType = Field(default=AuditType.FULL, description="Type of audit")
    schemas: List[str] = Field(default=["public"], description="Schemas to analyze")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Additional options")

    class Config:
        json_schema_extra = {
            "example": {
                "connection": {
                    "host": "localhost",
                    "port": 5432,
                    "database": "myapp",
                    "user": "postgres",
                    "password": "secret"
                },
                "audit_type": "full_audit",
                "schemas": ["public", "app"]
            }
        }


class Severity(str, Enum):
    """Finding severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Finding(BaseModel):
    """Individual finding from audit."""
    id: int
    agent: str
    category: str
    title: str
    description: str
    severity: Severity
    affected_objects: List[str] = []
    remediation: str = ""
    metadata: Dict[str, Any] = {}
    timestamp: datetime


class Recommendation(BaseModel):
    """Recommendation from audit."""
    id: int
    agent: str
    category: str
    title: str
    description: str
    priority: int = Field(ge=1, le=10)
    effort: str
    impact: str
    implementation: str
    timestamp: datetime


class AuditStatusEnum(str, Enum):
    """Audit status values."""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditStatus(BaseModel):
    """Current audit status."""
    status: AuditStatusEnum
    audit_id: Optional[str] = None
    progress: Optional[Dict[str, Any]] = None
    start_time: Optional[datetime] = None
    agents_completed: int = 0
    total_findings: int = 0


class AuditSummary(BaseModel):
    """Summary of audit results."""
    audit_id: str
    total_findings: int
    total_recommendations: int
    agents_completed: int
    severity_distribution: Dict[str, int]
    category_distribution: Dict[str, int]
    findings_by_agent: Dict[str, int]
    decisions_made: int


class AuditResponse(BaseModel):
    """Complete audit response."""
    audit_id: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    metrics: Dict[str, Any]
    findings: List[Finding]
    recommendations: List[Recommendation]
    agent_results: Dict[str, Any]
    decisions: List[Dict[str, Any]]


class SchemaInfo(BaseModel):
    """Schema information."""
    schema_name: str
    tables: List[Dict[str, Any]]
    views: List[Dict[str, Any]]
    functions: List[Dict[str, Any]]
    total_size: int


class SecurityReport(BaseModel):
    """Security-focused report."""
    roles_analyzed: int
    issues_found: int
    critical_issues: List[Finding]
    high_issues: List[Finding]
    recommendations: List[Recommendation]


class RecommendationReport(BaseModel):
    """Recommendations report."""
    total_recommendations: int
    by_category: Dict[str, List[Recommendation]]
    quick_wins: List[Dict[str, Any]]
    long_term: List[Dict[str, Any]]
    action_plan: List[Dict[str, Any]]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: str
    timestamp: datetime
