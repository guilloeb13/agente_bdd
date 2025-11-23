# PostgreSQL Multi-Agent Analyzer (PMA-Agent)

A comprehensive multi-agent system for PostgreSQL database auditing, security analysis, performance optimization, and schema normalization.

## Features

### Specialized Agents

PMA-Agent includes 11 specialized agents, each focused on a specific aspect of database analysis:

1. **Security Agent** - Analyzes roles, permissions, password policies, SECURITY DEFINER functions (OWASP/CIS compliance)
2. **Schema Agent** - Analyzes table structures, column types, naming conventions, physical model
3. **FK Integrity Agent** - Detects missing foreign keys, constraint issues, relationship modeling problems
4. **Orphan Checker Agent** - Finds orphaned data, broken hierarchies, soft-delete inconsistencies
5. **Normalization Agent** - Checks 1NF, 2NF, 3NF, BCNF compliance and suggests refactoring
6. **Performance Agent** - Analyzes sequential scans, bloat, cache efficiency, vacuum status
7. **Indexing Agent** - Recommends B-Tree, GIN, GiST, partial, and covering indexes
8. **Data Quality Agent** - Detects duplicates, NULL distributions, low cardinality issues
9. **Anomaly Agent** - Finds statistical outliers, temporal anomalies, distribution issues
10. **DDL Reconstruction Agent** - Generates complete DDL from database catalog
11. **Recommendation Agent** - Consolidates findings into prioritized action plans

### Core Capabilities

- Comprehensive PostgreSQL catalog extraction
- Parallel agent execution for faster analysis
- Shared memory for inter-agent communication
- Multiple report formats (Markdown, HTML, JSON)
- REST API with FastAPI
- Docker support

## Installation

### Requirements

- Python 3.11+
- PostgreSQL 12+
- pip

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd postgres_agent

# Install dependencies
pip install -r infra/requirements.txt
```

### Docker Setup

```bash
cd infra
docker-compose up -d
```

This will start:
- PMA-Agent API on port 8000
- Test PostgreSQL database on port 5433

## Usage

### API Endpoints

#### Start an Audit

```bash
curl -X POST http://localhost:8000/audit/start \
  -H "Content-Type: application/json" \
  -d '{
    "connection": {
      "host": "localhost",
      "port": 5432,
      "database": "mydb",
      "user": "postgres",
      "password": "secret"
    },
    "audit_type": "full_audit",
    "schemas": ["public"]
  }'
```

#### Check Audit Status

```bash
curl http://localhost:8000/audit/status
```

#### Get Full Report

```bash
curl http://localhost:8000/audit/report
```

#### Get Security Report

```bash
curl http://localhost:8000/audit/security
```

#### Get Findings by Severity

```bash
curl http://localhost:8000/audit/findings?severity=high
```

#### Get Recommendations

```bash
curl http://localhost:8000/audit/recommendations?min_priority=7
```

#### Get Schema Information

```bash
curl http://localhost:8000/audit/schema
```

#### Get Reconstructed DDL

```bash
curl http://localhost:8000/audit/ddl
```

### Programmatic Usage

```python
import asyncio
from postgres_agent.manager.agent_manager import create_manager

async def run_audit():
    # Create manager with all agents
    manager = await create_manager(
        host="localhost",
        port=5432,
        database="mydb",
        user="postgres",
        password="secret"
    )

    # Run full audit
    results = await manager.run_full_audit(
        schemas=["public", "app"],
        options={}
    )

    # Get findings
    critical_findings = await manager.get_findings(severity="critical")

    # Get recommendations
    recommendations = await manager.get_recommendations(min_priority=8)

    return results

# Run
results = asyncio.run(run_audit())
```

### Report Generation

```python
from postgres_agent.reports.generators import generate_report

# Generate Markdown report
md_report = generate_report(results, format='markdown')
with open('audit_report.md', 'w') as f:
    f.write(md_report)

# Generate HTML report
html_report = generate_report(results, format='html')
with open('audit_report.html', 'w') as f:
    f.write(html_report)

# Generate JSON report
json_report = generate_report(results, format='json')
```

## Architecture

```
postgres_agent/
├── manager/
│   ├── agent_manager.py    # Central orchestrator
│   ├── task_router.py      # Routes tasks to agents
│   └── memory.py           # Shared memory store
├── agents/
│   ├── base_agent.py       # Base class for all agents
│   ├── security_agent.py
│   ├── schema_agent.py
│   ├── fk_integrity_agent.py
│   ├── orphan_checker_agent.py
│   ├── normalization_agent.py
│   ├── performance_agent.py
│   ├── indexing_agent.py
│   ├── data_quality_agent.py
│   ├── anomaly_agent.py
│   ├── ddl_reconstruction_agent.py
│   └── recommendation_agent.py
├── engine/
│   ├── pg_client.py        # PostgreSQL connection pool
│   ├── query_runner.py     # Safe query execution
│   └── metrics_collector.py # Catalog extraction
├── api/
│   ├── main.py             # FastAPI application
│   └── schemas.py          # Pydantic models
├── reports/
│   └── generators.py       # Report generation
├── infra/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
└── tests/
    ├── test_security.py
    ├── test_schema.py
    ├── test_integrity.py
    └── test_agent_manager.py
```

## Agent Execution Flow

1. **Initialization**: Manager creates connection pool and registers agents
2. **Catalog Collection**: MetricsCollector extracts full database catalog
3. **Parallel Execution**: Agents run in optimized parallel groups:
   - Group 1: Schema Agent (foundation)
   - Group 2: Security + Integrity Agents
   - Group 3: Orphans + Normalization + Performance + Data Quality + DDL
   - Group 4: Indexing + Anomaly Agents
   - Group 5: Recommendation Agent (consolidation)
4. **Results**: All findings and recommendations consolidated in shared memory
5. **Reports**: Generated in requested format

## Configuration

### Environment Variables

- `LOG_LEVEL`: Logging level (default: INFO)
- `MAX_CONNECTIONS`: Database pool size (default: 10)

### Audit Options

```python
options = {
    "skip_large_tables": True,      # Skip tables > 1M rows for some checks
    "sample_size": 10000,           # Sample size for statistical analysis
    "include_system_schemas": False # Analyze pg_catalog, etc.
}
```

## Safety Features

- **Read-only**: All queries are verified to be read-only
- **No modifications**: System never alters database
- **Query sanitization**: SQL injection prevention
- **Timeout protection**: Query timeout limits
- **Connection pooling**: Efficient resource usage

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=postgres_agent

# Run specific test file
pytest tests/test_security.py -v
```

## Example Audit Output

### Findings

| Severity | Category | Title |
|----------|----------|-------|
| HIGH | Security | Superuser role: admin_user |
| HIGH | Integrity | Missing FK: orders.customer_id |
| MEDIUM | Performance | High sequential scans: events |
| MEDIUM | Normalization | 3NF violation in customers |
| LOW | Schema | Timestamp without timezone |

### Recommendations

| Priority | Category | Action |
|----------|----------|--------|
| 10 | Security | Address critical security issues |
| 9 | Performance | Add indexes for sequential scans |
| 8 | Integrity | Add missing foreign keys |
| 7 | Data Quality | Implement validation constraints |

## Contributing

1. Fork the repository
2. Create your feature branch
3. Write tests for new functionality
4. Submit a pull request

## License

MIT License

## Support

For issues and feature requests, please use the GitHub issue tracker.
