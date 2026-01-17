"""
Servidor FastAPI para PMA-Agent Web App
Backend para la aplicación web de análisis de PostgreSQL
"""

import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import logging

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from postgres_agent.engine import PGClient
from postgres_agent.manager.agent_manager import create_manager
from postgres_agent.manager.task_router import TaskType
from postgres_agent.reports.generators import generate_report

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear app FastAPI
app = FastAPI(
    title="PMA-Agent Web API",
    description="API para análisis de bases de datos PostgreSQL",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directorios para archivos
OUTPUTS_DIR = Path("outputs")
OUTPUTS_DIR.mkdir(exist_ok=True)

# Estado global
active_audits: Dict[str, dict] = {}
websocket_connections: Dict[str, WebSocket] = {}


# === MODELOS PYDANTIC ===

class ConnectionConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    database: str
    user: str = "postgres"
    password: str = ""


class TestConnectionRequest(BaseModel):
    connection: ConnectionConfig


class AnalyzeRequest(BaseModel):
    connection: ConnectionConfig
    schemas: List[str] = ["public"]
    agents: List[str] = []  # Lista de agentes a ejecutar (vacío = todos)


class AnalyzeResponse(BaseModel):
    audit_id: str
    message: str
    status: str


class StatusResponse(BaseModel):
    audit_id: str
    status: str
    progress: Optional[dict] = None
    error: Optional[str] = None


# === ENDPOINTS ===

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "PMA-Agent Web API",
        "version": "1.0.0",
        "status": "operativo"
    }


@app.post("/connect")
async def test_connection(request: TestConnectionRequest):
    """
    Probar conexión a la base de datos
    """
    try:
        client = PGClient(
            host=request.connection.host,
            port=request.connection.port,
            database=request.connection.database,
            user=request.connection.user,
            password=request.connection.password
        )

        await client.connect()

        # Probar conexión
        is_connected = await client.test_connection()

        if not is_connected:
            await client.disconnect()
            raise HTTPException(
                status_code=400,
                detail="No se pudo conectar a la base de datos"
            )

        # Obtener información básica
        version = await client.get_version()
        db_name = await client.get_current_database()
        db_size = await client.get_database_size()

        await client.disconnect()

        return {
            "success": True,
            "message": "Conexión exitosa",
            "info": {
                "database": db_name,
                "version": version,
                "size_bytes": db_size
            }
        }

    except Exception as e:
        logger.error(f"Error al conectar: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Error de conexión: {str(e)}"
        )


@app.post("/analyze", response_model=AnalyzeResponse)
async def start_analysis(request: AnalyzeRequest):
    """
    Iniciar análisis de la base de datos
    """
    audit_id = str(uuid.uuid4())[:8]

    # Guardar configuración del análisis
    active_audits[audit_id] = {
        "status": "iniciando",
        "connection": request.connection.dict(),
        "schemas": request.schemas,
        "agents": request.agents,
        "start_time": datetime.now().isoformat(),
        "logs": [],
        "progress": 0
    }

    # Ejecutar análisis en background
    asyncio.create_task(run_analysis(audit_id, request))

    return AnalyzeResponse(
        audit_id=audit_id,
        message=f"Análisis iniciado con ID: {audit_id}",
        status="iniciando"
    )


async def run_analysis(audit_id: str, request: AnalyzeRequest):
    """
    Ejecutar el análisis completo
    """
    try:
        audit_state = active_audits[audit_id]

        # Log inicial
        await send_log(audit_id, "🔍 Iniciando análisis de base de datos...")
        audit_state["status"] = "conectando"

        # Crear manager
        await send_log(audit_id, "🔌 Conectando a la base de datos...")
        manager = await create_manager(
            host=request.connection.host,
            port=request.connection.port,
            database=request.connection.database,
            user=request.connection.user,
            password=request.connection.password
        )

        await send_log(audit_id, "✅ Conexión establecida")
        audit_state["status"] = "analizando"
        audit_state["progress"] = 10

        # Ejecutar auditoría
        await send_log(audit_id, f"📊 Analizando esquemas: {', '.join(request.schemas)}")
        await send_log(audit_id, "⚙️ Ejecutando agentes especializados...")

        results = await manager.run_full_audit(
            schemas=request.schemas,
            options={}
        )

        audit_state["progress"] = 80
        await send_log(audit_id, "📝 Generando reportes...")

        # Generar reportes
        md_report = generate_report(results, format='markdown')
        html_report = generate_report(results, format='html')
        json_report = generate_report(results, format='json')

        # Guardar reportes
        report_dir = OUTPUTS_DIR / audit_id
        report_dir.mkdir(exist_ok=True)

        (report_dir / "reporte.md").write_text(md_report, encoding='utf-8')
        (report_dir / "reporte.html").write_text(html_report, encoding='utf-8')
        (report_dir / "reporte.json").write_text(json_report, encoding='utf-8')

        audit_state["progress"] = 100
        audit_state["status"] = "completado"
        audit_state["results"] = results
        audit_state["reports"] = {
            "markdown": str(report_dir / "reporte.md"),
            "html": str(report_dir / "reporte.html"),
            "json": str(report_dir / "reporte.json")
        }

        await send_log(audit_id, "✅ Análisis completado exitosamente")

        # Cerrar conexión
        if manager.pg_client:
            await manager.pg_client.disconnect()

    except Exception as e:
        logger.error(f"Error en análisis {audit_id}: {e}")
        active_audits[audit_id]["status"] = "error"
        active_audits[audit_id]["error"] = str(e)
        await send_log(audit_id, f"❌ Error: {str(e)}")


async def send_log(audit_id: str, message: str):
    """
    Enviar log a través de WebSocket si está conectado
    """
    if audit_id in active_audits:
        active_audits[audit_id]["logs"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message
        })

    # Si hay WebSocket conectado, enviar mensaje
    if audit_id in websocket_connections:
        try:
            await websocket_connections[audit_id].send_json({
                "type": "log",
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass


@app.get("/status/{audit_id}", response_model=StatusResponse)
async def get_status(audit_id: str):
    """
    Obtener estado del análisis
    """
    if audit_id not in active_audits:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")

    audit_state = active_audits[audit_id]

    return StatusResponse(
        audit_id=audit_id,
        status=audit_state["status"],
        progress={
            "percent": audit_state.get("progress", 0),
            "logs": audit_state.get("logs", [])[-20:]  # Últimos 20 logs
        },
        error=audit_state.get("error")
    )


@app.get("/results/{audit_id}")
async def get_results(audit_id: str):
    """
    Obtener resultados del análisis
    """
    if audit_id not in active_audits:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")

    audit_state = active_audits[audit_id]

    if audit_state["status"] != "completado":
        raise HTTPException(
            status_code=400,
            detail=f"El análisis no está completado. Estado: {audit_state['status']}"
        )

    return audit_state.get("results", {})


@app.get("/download/{audit_id}/{format}")
async def download_report(audit_id: str, format: str):
    """
    Descargar reporte en formato especificado
    """
    if audit_id not in active_audits:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")

    audit_state = active_audits[audit_id]

    if audit_state["status"] != "completado":
        raise HTTPException(status_code=400, detail="El análisis no está completado")

    if format not in ["markdown", "html", "json"]:
        raise HTTPException(status_code=400, detail="Formato no válido")

    file_path = audit_state["reports"].get(format)

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    extensions = {"markdown": "md", "html": "html", "json": "json"}

    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        filename=f"reporte_pma_{audit_id}.{extensions[format]}"
    )


@app.websocket("/ws/{audit_id}")
async def websocket_endpoint(websocket: WebSocket, audit_id: str):
    """
    WebSocket para logs en tiempo real
    """
    await websocket.accept()
    websocket_connections[audit_id] = websocket

    try:
        # Enviar logs existentes
        if audit_id in active_audits:
            for log in active_audits[audit_id].get("logs", []):
                await websocket.send_json({
                    "type": "log",
                    "message": log["message"],
                    "timestamp": log["timestamp"]
                })

        # Mantener conexión abierta
        while True:
            # Recibir mensajes (mantener conexión)
            data = await websocket.receive_text()

            # Enviar estado actual
            if audit_id in active_audits:
                await websocket.send_json({
                    "type": "status",
                    "status": active_audits[audit_id]["status"],
                    "progress": active_audits[audit_id].get("progress", 0)
                })

    except WebSocketDisconnect:
        if audit_id in websocket_connections:
            del websocket_connections[audit_id]


@app.delete("/audit/{audit_id}")
async def delete_audit(audit_id: str):
    """
    Eliminar análisis y archivos asociados
    """
    if audit_id not in active_audits:
        raise HTTPException(status_code=404, detail="Análisis no encontrado")

    # Eliminar archivos
    report_dir = OUTPUTS_DIR / audit_id
    if report_dir.exists():
        import shutil
        shutil.rmtree(report_dir)

    # Eliminar del estado
    del active_audits[audit_id]

    return {"message": "Análisis eliminado"}


@app.get("/audits")
async def list_audits():
    """
    Listar todos los análisis
    """
    return {
        "audits": [
            {
                "audit_id": audit_id,
                "status": data["status"],
                "start_time": data["start_time"],
                "schemas": data["schemas"]
            }
            for audit_id, data in active_audits.items()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
